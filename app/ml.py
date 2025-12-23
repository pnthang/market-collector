
"""Compatibility wrapper: expose ML core from `app.ml.core`."""
from .ml.core import *  # noqa: F401,F403

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


# Celery task wrapper to run training in background and persist metadata
@celery.task(name='ml.train_model')
def train_model_task(symbol: str, period: str = "2y"):
    try:
        res = train_and_save_model(symbol, period=period)
        if res and res.get('model_path'):
            session = SessionLocal()
            try:
                mm = ModelMetadata(
                    symbol=symbol,
                    model_path=res.get('model_path'),
                    model_name=os.path.basename(res.get('model_path')) if res.get('model_path') else None,
                    metrics=res.get('metrics'),
                    features=res.get('features'),
                )
                session.add(mm)
                session.commit()
            except Exception:
                session.rollback()
                LOG.exception("Failed to save model metadata for %s", symbol)
            finally:
                session.close()
        return res
    except Exception:
        LOG.exception("Background training task failed for %s", symbol)
        return None


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
