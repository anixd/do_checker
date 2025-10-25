#!/usr/bin/env bash
set -e

# Директории
mkdir -p "${LOG_DIR:-/logs}"
mkdir -p "${DATA_DIR:-/data}"
mkdir -p "${DATA_DIR:-/data}/config"
mkdir -p "${DATA_DIR:-/data}/catalog"

# Инициализация конфигов при первом запуске
APP_YAML="${DATA_DIR:-/data}/config/app.yaml"
if [ ! -f "$APP_YAML" ]; then
  cat > "$APP_YAML" <<'YAML'
app:
  host: 127.0.0.1
  port: 8088
paths:
  logs_dir: /logs
  data_dir: /data
execution:
  max_concurrency: 3
  timeout_sec: 60
proxy:
  type: http
  dns_mode: proxy
  sticky_policy: auto
  sticky_ttl_sec: 360
screenshots:
  enabled_default: false
  max_workers: 1
  width: 1366
  height: 768
YAML
fi

SOAX_JSON="${DATA_DIR:-/data}/catalog/soax_geo.json"
if [ ! -f "$SOAX_JSON" ]; then
  cat > "$SOAX_JSON" <<'JSON'
{"version":1,"generated_at":null,"countries":[]}
JSON
fi

exec "$@"
