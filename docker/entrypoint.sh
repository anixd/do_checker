#!/bin/sh

set -e

mkdir -p "${LOG_DIR:-/logs}"
mkdir -p "${DATA_DIR:-/data}"
mkdir -p "${DATA_DIR:-/data}/config"
mkdir -p "${DATA_DIR:-/data}/catalog"

APP_YAML="${DATA_DIR:-/data}/config/app.yaml"
if [ ! -f "$APP_YAML" ]; then
  cat > "$APP_YAML" <<'YAML'
app:
  host: 127.0.0.1
  port: ${APP_PORT:-8888}
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
  timeout_sec: 30
soax:
  host: proxy.soax.com
  port_default_port: 9000
  port_login: ""
  port_sticky: 5000
  package_id: null
  session_password: null
  api_key: null
  package_key: null
http_client:
  user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
  accept: "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
  accept_language: "en-US,en;q=0.5"
YAML
fi

SOAX_JSON="${DATA_DIR:-/data}/catalog/soax_geo.json"
if [ ! -f "$SOAX_JSON" ]; then
  # Pre-fill soax_geo.json with the specified country list
  cat > "$SOAX_JSON" <<'JSON'
{
  "version": 1,
  "generated_at": "2025-10-25T00:00:00Z",
  "countries": [
    {"code": "kz", "name": "Kazakhstan", "regions":[{"code":"kz-ala","name":"Almaty"}], "isps":["Kazakhtelecom"]},
    {"code": "az", "name": "Azerbaijan", "regions":[], "isps":[]},
    {"code": "in", "name": "India", "regions":[], "isps":[]},
    {"code": "uz", "name": "Uzbekistan", "regions":[], "isps":[]},
    {"code": "bd", "name": "Bangladesh", "regions":[], "isps":[]},
    {"code": "ru", "name": "Russia", "regions":[], "isps":[]},
    {"code": "tr", "name": "Turkey", "regions":[{"code":"tr-35","name":"Izmir Province"}], "isps":["Turk Telekom","Vodafone TR","Turkcell"]},
    {"code": "kg", "name": "Kyrgyzstan", "regions":[], "isps":[]},
    {"code": "ca", "name": "Canada", "regions":[], "isps":[]},
    {"code": "tj", "name": "Tajikistan", "regions":[], "isps":[]}
  ]
}
JSON
fi

exec "$@"
