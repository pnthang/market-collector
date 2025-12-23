import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import pandas as pd
import numpy as np
import yfinance as yf
import joblib
import ta
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

from .db import SessionLocal, init_db
from .models import IndexIndicator, IndexPrediction
from .models import IndexPrice

LOG = logging.getLogger("ml")
MODELS_DIR = os.getenv("ML_MODELS_DIR", "models")
os.makedirs(MODELS_DIR, exist_ok=True)


def get_stock_data(symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
    try:
        df = yf.download(symbol, period=period, progress=False)
        if df is None or df.empty:
            return None
        # handle MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        required_cols = ["Open", "High", "Low", "Close", "Volume"]
        if not all(c in df.columns for c in required_cols):
            return None
        df = df.dropna(how="all")
        return df
    except Exception:
        LOG.exception("Failed to download data for %s", symbol)
        return None


def calculate_technical_indicators(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    if df is None or df.empty:
        return None
    df = df.copy()

    # Moving averages
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()

    # Exponential moving averages
    df['EMA_12'] = df['Close'].ewm(span=12).mean()
    df['EMA_26'] = df['Close'].ewm(span=26).mean()

    # MACD
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_histogram'] = df['MACD'] - df['MACD_signal']

    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # Bollinger Bands
    df['BB_middle'] = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_upper'] = df['BB_middle'] + (bb_std * 2)
    df['BB_lower'] = df['BB_middle'] - (bb_std * 2)

    # Volume indicators
    df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
    df['Volume_ratio'] = df['Volume'] / df['Volume'].rolling(window=20).mean()

    # Price-based indicators
    df['High_Low_Pct'] = (df['High'] - df['Low']) / df['Close'] * 100
    df['Price_Change'] = df['Close'] - df['Open']
    df['Price_Change_Pct'] = (df['Close'] - df['Open']) / df['Open'] * 100

    # Volatility / ATR
    df['High_Low'] = df['High'] - df['Low']
    df['High_Close'] = (df['High'] - df['Close'].shift()).abs()
    df['Low_Close'] = (df['Low'] - df['Close'].shift()).abs()
    df['True_Range'] = df[['High_Low', 'High_Close', 'Low_Close']].max(axis=1)
    df['ATR'] = df['True_Range'].rolling(window=14).mean()

    # Stochastic Oscillator
    low_14 = df['Low'].rolling(window=14).min()
    high_14 = df['High'].rolling(window=14).max()
    df['Stoch_K'] = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
    df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()

    # Additional indicators from ta library
    try:
        df['Williams_R'] = ta.momentum.williams_r(df['High'], df['Low'], df['Close'])
        df['CCI'] = ta.trend.cci(df['High'], df['Low'], df['Close'])
        df['OBV'] = ta.volume.on_balance_volume(df['Close'], df['Volume'])
        df['CMF'] = ta.volume.chaikin_money_flow(df['High'], df['Low'], df['Close'], df['Volume'])
        df['ROC'] = ta.momentum.roc(df['Close'], window=10)
        df['TSI'] = ta.momentum.tsi(df['Close'])
        df['UO'] = ta.momentum.ultimate_oscillator(df['High'], df['Low'], df['Close'])

        ichimoku = ta.trend.IchimokuIndicator(df['High'], df['Low'])
        df['Ichimoku_A'] = ichimoku.ichimoku_a()
        df['Ichimoku_B'] = ichimoku.ichimoku_b()
        df['Ichimoku_Base'] = ichimoku.ichimoku_base_line()
        df['Ichimoku_Conversion'] = ichimoku.ichimoku_conversion_line()

        df['PSAR'] = ta.trend.PSARIndicator(df['High'], df['Low'], df['Close']).psar()

        keltner = ta.volatility.KeltnerChannel(df['High'], df['Low'], df['Close'])
        df['Keltner_High'] = keltner.keltner_channel_hband()
        df['Keltner_Low'] = keltner.keltner_channel_lband()

        donchian = ta.volatility.DonchianChannel(df['High'], df['Low'], df['Close'])
        df['Donchian_High'] = donchian.donchian_channel_hband()
        df['Donchian_Low'] = donchian.donchian_channel_lband()

        aroon = ta.trend.AroonIndicator(df['High'], df['Low'], df['Close'])
        df['Aroon_Up'] = aroon.aroon_up()
        df['Aroon_Down'] = aroon.aroon_down()

        df['VWAP'] = ta.volume.volume_weighted_average_price(df['High'], df['Low'], df['Close'], df['Volume'])
        df['AD'] = ta.volume.acc_dist_index(df['High'], df['Low'], df['Close'], df['Volume'])
        df['Chaikin_Osc'] = ta.volume.chaikin_oscillator(df['High'], df['Low'], df['Close'], df['Volume'])
        df['Force_Index'] = ta.volume.force_index(df['Close'], df['Volume'])
        df['EOM'] = ta.volume.ease_of_movement(df['High'], df['Low'], df['Volume'])
    except Exception as e:
        LOG = logging.getLogger('ml')
        LOG.debug("Error calculating some ta indicators: %s", e)

    # Do not drop NaNs here; let callers decide. Return DataFrame with indicators appended.
    return df


def save_latest_indicators(symbol: str, period: str = "1y") -> Optional[Dict]:
    init_db()
    df = get_stock_data(symbol, period)
    if df is None or df.empty:
        LOG.info("No data for %s to compute indicators", symbol)
        return None
    ind = calculate_technical_indicators(df)
    if ind is None or ind.empty:
        return None
    latest = ind.iloc[-1].to_dict()
    ts = ind.index[-1]
    index_code = f"US:{symbol}"
    session = SessionLocal()
    try:
        row = IndexIndicator(index_code=index_code, timestamp=ts.to_pydatetime() if hasattr(ts, 'to_pydatetime') else ts, data=latest)
        session.add(row)
        session.commit()
        LOG.info("Saved latest indicators for %s at %s", symbol, ts)
        return latest
    except Exception:
        session.rollback()
        LOG.exception("Failed to save indicators for %s", symbol)
        return None
    finally:
        session.close()


def save_indicators_series(symbol: str, period: str = "1y") -> int:
    """Compute indicators for the historical series and save each timestamp to `index_indicators`.

    Returns number of rows inserted.
    """
    init_db()
    df = get_stock_data(symbol, period)
    if df is None or df.empty:
        LOG.info("No historical data for %s", symbol)
        return 0
    ind = calculate_technical_indicators(df)
    if ind is None or ind.empty:
        return 0
    index_code = f"US:{symbol}"
    session = SessionLocal()
    inserted = 0
    try:
        objs = []
        for ts, row in ind.iterrows():
            try:
                data = row.to_dict()
                objs.append(IndexIndicator(index_code=index_code, timestamp=ts.to_pydatetime() if hasattr(ts, 'to_pydatetime') else ts, data=data))
            except Exception:
                continue
        session.bulk_save_objects(objs)
        session.commit()
        inserted = len(objs)
        LOG.info("Saved %d indicator rows for %s", inserted, symbol)
        return inserted
    except Exception:
        session.rollback()
        LOG.exception("Failed saving indicators series for %s", symbol)
        return 0
    finally:
        session.close()


def save_history_to_db(symbol: str, period: str = "1y") -> int:
    """Save historical Close prices to `index_prices` table from yfinance DataFrame.

    Returns number of rows inserted.
    """
    init_db()
    df = get_stock_data(symbol, period)
    if df is None or df.empty:
        LOG.info("No historical data for %s to save", symbol)
        return 0
    index_code = f"US:{symbol}"
    session = SessionLocal()
    try:
        objs = []
        for ts, row in df.iterrows():
            try:
                objs.append({
                    'index_code': index_code,
                    'source': 'yahoo',
                    'price': float(row['Close']),
                    'change': float(row['Close'] - row['Open']) if not pd.isna(row['Open']) else None,
                    'change_percent': float((row['Close'] - row['Open'])/row['Open']*100) if not pd.isna(row['Open']) and row['Open'] != 0 else None,
                    'timestamp': ts.to_pydatetime() if hasattr(ts, 'to_pydatetime') else ts,
                })
            except Exception:
                continue
        # dedupe with existing timestamps
        codes = [o['index_code'] for o in objs]
        timestamps = [o['timestamp'] for o in objs]
        existing = set()
        if codes and timestamps:
            qres = session.query(IndexPrice.index_code, IndexPrice.timestamp).filter(IndexPrice.index_code.in_(codes), IndexPrice.timestamp.in_(timestamps)).all()
            existing = {(c, t) for c, t in qres}
        new_objs = [IndexPrice(**o) for o in objs if (o['index_code'], o['timestamp']) not in existing]
        if not new_objs:
            LOG.info("No new historical price rows to insert for %s", symbol)
            return 0
        session.bulk_save_objects(new_objs)
        session.commit()
        LOG.info("Inserted %d historical price rows for %s", len(new_objs), symbol)
        return len(new_objs)
    except Exception:
        session.rollback()
        LOG.exception("Failed saving historical prices for %s", symbol)
        return 0
    finally:
        session.close()


def run_pipeline(symbol: str, period: str = '2y', train: bool = True, predict_days: int = 3) -> Dict:
    """Run end-to-end pipeline: save history -> indicators -> train -> predict.

    Returns a brief result summary.
    """
    init_db()
    result = {'symbol': symbol}
    saved = save_history_to_db(symbol, period)
    result['history_rows'] = saved
    ind_rows = save_indicators_series(symbol, period)
    result['indicator_rows'] = ind_rows
    model_info = None
    if train:
        model_info = train_and_save_model(symbol, period=period)
        result['trained'] = bool(model_info)
        result['model_info'] = model_info or {}
    pred = predict_and_save(symbol, days=predict_days)
    result['predictions'] = pred.get('predictions') if pred else []
    result['model_version'] = pred.get('model_version') if pred else None
    return result


def train_and_save_model(symbol: str, period: str = "2y") -> Optional[Dict]:
    init_db()
    df = get_stock_data(symbol, period)
    if df is None or len(df) < 120:
        LOG.info("Insufficient data to train model for %s", symbol)
        return None
    ind = calculate_technical_indicators(df)
    # prepare features
    features = [c for c in ind.columns if c not in ["Close", "Adj Close"]]
    X = ind[features].copy()
    y = ind["Close"].shift(-1).dropna()
    X = X.iloc[:-1]
    # drop rows with NaN
    mask = X.notna().all(axis=1)
    X = X.loc[mask]
    y = y.loc[mask.index.intersection(y.index)]
    if X.shape[0] < 50:
        LOG.info("Not enough feature rows after cleaning for %s", symbol)
        return None
    # split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    y_pred_test = model.predict(X_test)
    test_mse = float(mean_squared_error(y_test, y_pred_test))
    test_r2 = float(r2_score(y_test, y_pred_test))
    # save
    model_name = f"{symbol}_rf_{int(datetime.utcnow().timestamp())}.pkl"
    model_path = os.path.join(MODELS_DIR, model_name)
    joblib.dump(model, model_path)
    LOG.info("Trained model for %s saved to %s", symbol, model_path)
    return {
        'model_path': model_path,
        'metrics': {'test_mse': test_mse, 'test_r2': test_r2},
        'features': features
    }


def predict_and_save(symbol: str, days: int = 1) -> Optional[Dict]:
    init_db()
    # find latest model file for symbol
    files = [f for f in os.listdir(MODELS_DIR) if f.startswith(symbol + "_") and f.endswith('.pkl')]
    files.sort(reverse=True)
    model = None
    model_version = None
    if files:
        model_path = os.path.join(MODELS_DIR, files[0])
        try:
            model = joblib.load(model_path)
            model_version = files[0]
        except Exception:
            LOG.exception("Failed to load model %s", model_path)
            model = None
    else:
        # try training on the fly
        res = train_and_save_model(symbol)
        if res and res.get('model_path'):
            try:
                model = joblib.load(res['model_path'])
                model_version = os.path.basename(res['model_path'])
            except Exception:
                LOG.exception("Failed to load newly trained model for %s", symbol)
                model = None
    # get latest data
    df = get_stock_data(symbol, '1y')
    if df is None or df.empty:
        LOG.info("No data to predict for %s", symbol)
        return None
    ind = calculate_technical_indicators(df)
    if ind is None or ind.empty:
        return None
    current_price = float(ind['Close'].iloc[-1])
    preds = []
    temp_df = ind.copy()
    for day in range(1, max(1, int(days)) + 1):
        pred = None
        if model is not None:
            feat = temp_df.iloc[-1:].drop(['Close', 'Adj Close'], axis=1, errors='ignore')
            if feat.isna().any(axis=1).any():
                # cannot predict with NaNs
                pred = None
            else:
                try:
                    pred = float(model.predict(feat)[0])
                except Exception:
                    LOG.exception("Model prediction failed for %s", symbol)
                    pred = None
        if pred is None:
            # fallback: mean return
            returns = temp_df['Close'].pct_change().dropna()
            mean_ret = float(returns.mean()) if not returns.empty else 0.0
            pred = float(current_price * (1 + mean_ret))
        change_pct = ((pred - current_price) / current_price) * 100 if current_price else None
        preds.append({'day': day, 'predicted_price': float(pred), 'change_percent': float(change_pct) if change_pct is not None else None})
        # append synthetic row
        try:
            last_idx = temp_df.index[-1]
            try:
                next_idx = last_idx + timedelta(days=1)
            except Exception:
                next_idx = last_idx
            synthetic = temp_df.iloc[-1:].copy()
            synthetic.iloc[0]['Open'] = pred
            synthetic.iloc[0]['High'] = pred
            synthetic.iloc[0]['Low'] = pred
            synthetic.iloc[0]['Close'] = pred
            synthetic.index = [next_idx]
            temp_df = pd.concat([temp_df, synthetic])
            current_price = pred
        except Exception:
            break
    # save predictions to DB
    session = SessionLocal()
    try:
        index_code = f"US:{symbol}"
        for p in preds:
            row = IndexPrediction(index_code=index_code, horizon_days=int(p['day']), predicted_price=float(p['predicted_price']), change_percent=float(p['change_percent']) if p['change_percent'] is not None else None, model_version=model_version, metadata={'method': 'rf' if model is not None else 'fallback'})
            session.add(row)
        session.commit()
        LOG.info("Saved %d predictions for %s", len(preds), symbol)
    except Exception:
        session.rollback()
        LOG.exception("Failed to save predictions for %s", symbol)
    finally:
        session.close()
    return {'symbol': symbol, 'current_price': float(ind['Close'].iloc[-1]), 'predictions': preds, 'model_version': model_version}
