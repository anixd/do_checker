from flask import (
    Blueprint, render_template, request, redirect,
    url_for, Response, jsonify, flash
)
from datetime import datetime
import threading
from engine.orchestrator import start_run, get_run_state
from config.loader import ConfigStore
from providers.soax import CatalogStore, refresh_catalog_data
from logging_.engine_logger import get_engine_logger

bp = Blueprint("routes", __name__)


@bp.get("/")
def index():
    cfg = ConfigStore.get()

    countries = CatalogStore.get_countries()

    return render_template(
        "index.html",
        countries=countries,
        defaults=dict(
            # Proxy defaults
            proxy_type=cfg.proxy.type,
            dns_mode=cfg.proxy.dns_mode,
            # Soax defaults
            soax_host=cfg.soax.host,
            soax_port_default=cfg.soax.port_default_port,
            # Sticky defaults
            sticky_policy=cfg.proxy.sticky_policy,
            sticky_ttl_sec=cfg.proxy.sticky_ttl_sec,
            # Execution defaults
            timeout_sec=cfg.execution.timeout_sec,
            screenshots_enabled=cfg.screenshots.enabled_default,
        ),
        logs_dir=cfg.paths.logs_dir,
    )


@bp.post("/run")
def launch_run():
    urls_raw = (request.form.get("urls") or "").strip()
    urls = [u.strip() for u in urls_raw.splitlines() if u.strip()]
    if not urls:
        return Response("No URLs provided", status=400)

    # Собираем все параметры запуска в один словарь
    run_params = {
        "urls": urls,

        # Geo
        "country": request.form.get("country") or "",
        "region_code": request.form.get("region") or None,
        "city": request.form.get("city") or None,
        "isp": request.form.get("isp") or None,

        # Proxy
        "proxy_type": request.form.get("proxy_type") or "http",
        "dns_mode": request.form.get("dns_mode") or "proxy",
        "connection_type": request.form.get("connection_type") or "wifi",

        # Overrides
        "proxy_host": request.form.get("proxy_host") or None,
        "proxy_port": request.form.get("proxy_port") or None,

        # Execution
        "timeout_sec": int(request.form.get("timeout_sec") or 60),
        "make_screenshot": bool(request.form.get("make_screenshot")),
        "debug_mode": bool(request.form.get("debug_mode")),

        # Sticky (пока не используется в Port-режиме, но передаем)
        "sticky_policy": request.form.get("sticky_policy") or "auto",
        "sticky_ttl_sec": int(request.form.get("sticky_ttl_sec") or 360),
    }

    if not run_params["country"]:
        return Response("Country is required", status=400)

    run_id = start_run(run_params)
    return jsonify({"run_id": run_id}), 202 # 202 Accepted


@bp.get("/catalog")
def catalog():
    # Используем get_countries() для загрузки всего кэша
    return render_template("catalog.html", catalog=CatalogStore._load_or_cache(force_reload=True))


@bp.post("/catalog/refresh")
def catalog_refresh():
    """
    Запускает обновление каталога в фоновом потоке.
    """
    log = get_engine_logger()
    log.info("Received request to refresh catalog. Starting background thread...")

    # запускаем тяжелую задачу в отдельном потоке
    thread = threading.Thread(
        target=refresh_catalog_data,
        daemon=True
    )
    thread.start()

    flash("Catalog refresh started in the background. It may take a minute.", "info")

    return redirect(url_for("routes.catalog"))


@bp.get("/settings")
def settings():
    yaml = ConfigStore.raw_yaml()
    return render_template("settings.html", yaml=yaml)


@bp.post("/settings")
def settings_save():
    yaml_text = request.form.get("yaml") or ""
    ConfigStore.save_yaml(yaml_text)
    return redirect(url_for("routes.settings"))


@bp.get("/api/geo/regions")
def api_get_regions():
    country = request.args.get("country")
    if not country:
        return jsonify([])
    return jsonify(CatalogStore.get_regions(country))


@bp.get("/api/geo/cities")
def api_get_cities():
    country = request.args.get("country")
    region = request.args.get("region")
    if not country:
        return jsonify([])
    # TBD: Наша структура JSON пока не поддерживает города ВНУТРИ региона.
    # Мы вернем города на уровне страны, если они есть.
    return jsonify(CatalogStore.get_cities(country, region))


@bp.get("/api/geo/isps")
def api_get_isps():
    country = request.args.get("country")
    if not country:
        return jsonify([])
    # Возвращаем список строк
    return jsonify(CatalogStore.get_isps(country))
