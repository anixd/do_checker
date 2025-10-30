from flask import (
    Blueprint, render_template, request, redirect,
    url_for, Response, jsonify, flash
)
from datetime import datetime
import threading
import shutil
import os
from engine.orchestrator import start_run, get_run_state, start_dns_run
from config.loader import ConfigStore
from providers.soax import CatalogStore, refresh_catalog_data
from logging_.engine_logger import get_engine_logger

log = get_engine_logger()

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
        log.warning("Run rejected: No URLs provided.")
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
        log.warning("Run rejected: Country is required.")
        return Response("Country is required", status=400)

    log.info(
        f"Accepted /run request. URLs: {len(urls)}. "
        f"Country: {run_params.get('country')}. Starting run..."
    )

    run_id = start_run(run_params)
    log.info(f"[{run_id}] Returning HTTP 202 to client.")

    return jsonify({"run_id": run_id}), 202 # 202 Accepted


@bp.get("/catalog")
def catalog():
    # используем get_countries() для загрузки всего кеша
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


@bp.post("/catalog/update-list")
def catalog_update_list():
    """
    Handles adding new countries and removing existing ones from the catalog JSON.
    """
    try:
        new_countries_str = request.form.get("new_countries", "")
        existing_countries_keep = request.form.getlist("countries_to_keep")

        # 1. Process new countries (lowercase, split by any whitespace, remove blanks)
        new_countries_list = [
            code.strip().lower()
            for code in new_countries_str.split()
            if code.strip()
        ]

        # 2. Merge lists, preserving order and removing duplicates
        final_codes_list = []
        seen_codes = set()

        # Add "kept" countries first
        for code in existing_countries_keep:
            if code not in seen_codes:
                final_codes_list.append(code)
                seen_codes.add(code)

        # Add "new" countries if they weren't already in the "kept" list
        for code in new_countries_list:
            if code not in seen_codes:
                final_codes_list.append(code)
                seen_codes.add(code)

        # 3. Save to CatalogStore
        CatalogStore.update_country_list(final_codes_list)

        flash("Catalog country list updated successfully.", "info")  # 'info' for blue flash

    except Exception as e:
        log.error(f"Failed to update catalog list: {e}", exc_info=True)
        flash(f"Error updating catalog: {e}", "error")

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
    return jsonify(CatalogStore.get_isps(country))


@bp.post("/logs/clear")
def clear_logs():
    """Удаляет содержимое /logs"""
    cfg = ConfigStore.get()
    logs_dir = os.path.abspath(cfg.paths.logs_dir)

    log.warning(f"Attempting to clear contents of log directory: {logs_dir}")

    # Проверка, что /logs существует и это действительно директория
    if not os.path.isdir(logs_dir):
        log.error(f"Log directory not found or is not a directory: {logs_dir}")
        flash("Error: Log directory not found.", "error")
        return jsonify({"success": False, "message": "Log directory not found"}), 500

    if 'logs' not in logs_dir.split(os.path.sep)[-2:]:  # Проверим последние два компонента пути
        log.error(f"Safety check failed: Log directory path seems unsafe: {logs_dir}")
        flash("Error: Log directory path seems unsafe.", "error")
        return jsonify({"success": False, "message": "Unsafe log directory path"}), 500

    try:
        # Удаляем все внутри /logs
        for filename in os.listdir(logs_dir):
            file_path = os.path.join(logs_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                log.error(f"Failed to delete {file_path}. Reason: {e}")

        log.info(f"Successfully cleared contents of log directory: {logs_dir}")
        flash("Logs cleared successfully.", "success")
        return jsonify({"success": True}), 200

    except Exception as e:
        log.error(f"Failed to clear log directory {logs_dir}: {e}", exc_info=True)
        flash(f"Error clearing logs: {e}", "error")
        return jsonify({"success": False, "message": str(e)}), 500


@bp.get("/dns-checker")
def dns_checker_page():
    """Renders the DNS checker page."""
    return render_template("dns_checker.html")


@bp.post("/check-dns")
def launch_dns_run():
    """Handles the form submission from the DNS checker page."""
    domains_raw = (request.form.get("domains") or "").strip()
    domains = [d.strip() for d in domains_raw.splitlines() if d.strip()]

    if not domains:
        log.warning("DNS check rejected: No domains provided.")
        # Можно вернуть ошибку JSON, если JS будет ее обрабатывать
        return jsonify({"error": "No domains provided"}), 400

    log.info(
        f"Accepted /check-dns request. Domains: {len(domains)}. Starting DNS run..."
    )

    run_id = start_dns_run(domains)

    log.info(f"[{run_id}] Returning HTTP 202 for DNS run.")

    return jsonify({"run_id": run_id}), 202  # Accepted

