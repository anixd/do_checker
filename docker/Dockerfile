FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Ставим системные зависимости, нужные Playwright ДЛЯ УСТАНОВКИ и ЗАПУСКА
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget gnupg ca-certificates fonts-liberation libnss3 libxkbcommon0 \
    libxcomposite1 libxrandr2 libasound2 libxdamage1 libxfixes3 \
    libgtk-3-0 libdrm2 libgbm1 libpango-1.0-0 libwoff1 xvfb git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# качаем браузер Playwright
# используем playwright download, чтобы кешировать браузер отдельно
# RUN python -m playwright install --with-deps chromium || true
RUN python -m playwright install chromium

FROM python:3.12-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    TZ="UTC"
    # говорим Playwright, где искать браузеры (важно!)

# ставим ТОЛЬКО те зависимости, что нужны для ЗАПУСКА chromium
# (меньший набор, чем в builder stage)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates fonts-liberation libnss3 libxkbcommon0 \
    libxcomposite1 libxrandr2 libasound2 libxdamage1 libxfixes3 \
    libgtk-3-0 libdrm2 libgbm1 libpango-1.0-0 libwoff1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

COPY --from=builder /root/.cache/ms-playwright /opt/ms-playwright
# путь /root/.cache/ms-playwright может отличаться.
# если сборка упадет здесь, нужно глянуть, куда Playwright скачал браузер в builder stage.

WORKDIR /app

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY . /app

EXPOSE ${APP_PORT:-8088}
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:${APP_PORT:-8088}", "--access-logfile", "/dev/null", "server:app"]
