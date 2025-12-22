FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget ca-certificates gnupg2 fonts-liberation libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libxss1 libxkbcommon0 libasound2 libgbm1 libpangocairo-1.0-0 libgtk-3-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && playwright install chromium || true

COPY . /app

CMD ["python", "-m", "app"]
