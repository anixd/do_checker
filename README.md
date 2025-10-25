## How to run the project

```bash
cp .env.example .env
docker compose up --build
```

Open http://127.0.0.1:8088

---

## Logs

- Логи и скриншоты: `./logs/YYYY-MM-DD/HH-MM-SS_domain.md(.png)`

- Сводка запуска: `./logs/YYYY-MM-DD/HH-MM-SS_run-summary.md`

- App tech log: `./logs/engine.log`

- Config: `./data/config/app.yaml`

- SOAX geos & regions (cached): `./data/catalog/soax_geo.json`

Screenshots are disabled by default. Enable by checking the box at startup.

