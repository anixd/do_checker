FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Системные зависимости для Playwright/Chromium
RUN apt-get update && apt-get install -y \
    curl wget gnupg ca-certificates fonts-liberation libnss3 libxkbcommon0 libxcomposite1 libxrandr2 \
    libasound2 libxdamage1 libxfixes3 libgtk-3-0 libdrm2 libgbm1 libpango-1.0-0 libwoff1 \
    xvfb git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Установить браузеры Playwright (без этого скриншоты будут отключены автоматически)
RUN python -m playwright install --with-deps chromium || true

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY . /app

EXPOSE 8088
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8088", "--threads", "8", "server:app"]
