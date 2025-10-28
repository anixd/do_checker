from __future__ import annotations
import os
import socket
import time
import urllib.parse
import requests
import threading
from datetime import datetime
from typing import Any
from providers.soax import get_session, ProxySession
from config.loader import ConfigStore
from logging_.md_writer import ensure_day_dir, unique_file_path, render_md_card
from logging_.engine_logger import get_engine_logger

try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None

log = get_engine_logger()

# create global semaphore
screenshot_semaphore: threading.Semaphore | None = None
_semaphore_lock = threading.Lock()  # lock для инициализации семафора


def _normalize_url(raw: str) -> tuple[str, str]:
    """
    Ensures a URL has a scheme and extracts a clean netloc (domain)
    for use in filenames.

    Returns:
        tuple[str, str]: (domain, full_url_for_request)
    """
    url_full = raw
    if "://" not in raw:
        url_full = f"http://{raw}"

    # Now that we guaranteed a scheme, parse it
    parsed = urllib.parse.urlsplit(url_full)
    domain = parsed.netloc

    return domain, url_full


def _requests_proxies(ps: ProxySession, dns_mode: str) -> dict:
    auth = f"{ps.username}:{ps.password}@"
    if ps.type == "socks5":
        scheme = "socks5h" if dns_mode == "proxy" else "socks5"
    else:
        scheme = "http"
    proxy_url = f"{scheme}://{auth}{ps.host}:{ps.port}"
    return {"http": proxy_url, "https": proxy_url}


def _measure_http(url: str, proxies: dict, timeout_sec: int, max_redirects: int = 5):
    timings = {"dns_ms": None, "tcp_ms": None, "tls_ms": None, "ttfb_ms": None, "total_ms": None}
    redirects = []
    http_status = None
    bytes_count = None
    cfg = ConfigStore.get()
    headers = {
        "User-Agent": cfg.http_client.user_agent,
        "Accept": cfg.http_client.accept,
        "Accept-Language": cfg.http_client.accept_language,
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
    }
    sess = requests.Session()
    sess.max_redirects = max_redirects
    sess.headers.update(headers)
    start = time.time()
    try:
        resp = sess.get(url, proxies=proxies, timeout=timeout_sec, stream=True, allow_redirects=True)
        http_status = resp.status_code
        first_chunk = next(resp.iter_content(chunk_size=1024), b"")
        ttfb = time.time() - start
        timings["ttfb_ms"] = int(ttfb * 1000)
        content = first_chunk + resp.content
        bytes_count = len(content)

        # берем историю редиректов из 'resp.history'.
        # каждый 'r' в 'history' - это Response-объект редиректа.
        redirects = []
        for r in resp.history:
            redirects.append((r.status_code, r.url, r.headers.get('Location', '')))

    except requests.exceptions.RequestException as e:
        end = time.time()
        timings["total_ms"] = int((end - start) * 1000)
        raise e
    end = time.time()
    timings["total_ms"] = int((end - start) * 1000)
    return http_status, bytes_count, redirects, timings


def _classify(exc: Exception | None, http_status: int | None, timeout_sec: int) -> str:
    if exc:
        s = str(exc).lower()
        if "name or service not known" in s or "nodename nor servname" in s or "dns" in s:
            return "dns_error"
        if "timed out" in s or "timeout" in s:
            return "timeout"
        if "ssl" in s or "tls" in s:
            return "tls_error"
        return "connect_error"
    if http_status is None:
        return "connect_error"
    if 200 <= http_status < 400:
        return "success"
    if 400 <= http_status < 600:
        return "http_error"
    return "http_error"


def _take_screenshot(
        ps: ProxySession, url: str, out_path: str, screenshot_timeout_sec: int, width: int, height: int
) -> tuple[bool, str | None]:
    if not sync_playwright:
        return False, "playwright not installed or failed to import"

    cfg = ConfigStore.get()

    playwright_proxy = {
        "server": f"{ps.type}://{ps.host}:{ps.port}",
        "username": ps.username,
        "password": ps.password
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": width, "height": height},
                user_agent=cfg.http_client.user_agent,
                proxy=playwright_proxy
            )
            page = ctx.new_page()
            # Use screenshot timeout (convert to ms)
            page.set_default_navigation_timeout(screenshot_timeout_sec * 1000)
            page.goto(url, wait_until="load")
            page.screenshot(path=out_path) # делаем скрин _видимой_ части страницы.
            # full_page=True делает скрин ВСЕЙ высоты страницы (если нужно)
            browser.close()
        return True, None
    except Exception as e:
        log.error(f"Screenshot failed for {url}: {e}")
        return False, str(e)


def execute_check(run_params: dict[str, Any]) -> dict:
    global screenshot_semaphore
    cfg = ConfigStore.get()

    # initialize semaphore if needed
    if screenshot_semaphore is None:
        with _semaphore_lock:  # prevent race condition on first init
            if screenshot_semaphore is None:
                max_workers = cfg.screenshots.max_workers
                log.info(f"Initializing screenshot semaphore with max_workers={max_workers}")
                screenshot_semaphore = threading.Semaphore(max_workers)
    # end semaphore init

    logs_dir = cfg.paths.logs_dir
    day_dir = ensure_day_dir(logs_dir)

    run_id_for_log = run_params.get('run_id', 'NO_RUN_ID')
    url = run_params["url"]
    log.debug(f"[{run_id_for_log}] execute_check started for {url}")
    
    timeout_sec = run_params["timeout_sec"]
    make_screenshot = run_params["make_screenshot"]
    debug_mode = run_params.get("debug_mode", False)
    dns_mode = run_params.get("dns_mode", "proxy")

    domain, url_full = _normalize_url(url)
    ts = datetime.now().strftime("%H-%M-%S")
    base_name = f"{ts}_{domain}"

    md_path = unique_file_path(day_dir, base_name, "md")
    png_path = None

    ps = None
    debug_data = None
    http_status = None
    bytes_count = None
    redirects = []
    timings = {}
    notes = None
    exc = None

    try:
        log.debug(f"[{run_id_for_log}] Calling get_session for {url}...")
        ps = get_session(run_params)
        debug_data = ps.debug_info

        proxies = _requests_proxies(ps, dns_mode)
        log.debug(f"[{run_id_for_log}] Calling _measure_http for {url}...")
        http_status, bytes_count, redirects, timings = _measure_http(url_full, proxies, timeout_sec)
    except Exception as e:
        exc = e
        notes = str(e)
        if debug_data is None:
            debug_data = {"error": str(e)}

        log.warning(f"[{run_id_for_log}] _measure_http failed for {url}: {e}")

    result = _classify(exc, http_status, timeout_sec)
    log.debug(f"[{run_id_for_log}] Result for {url}: {result}")

    # логика скриншота, с семафором
    if make_screenshot and result == "success":
        png_path = unique_file_path(day_dir, base_name, "png")
        screenshot_timeout = cfg.screenshots.timeout_sec

        log.info(f"Acquiring screenshot semaphore for {url}...")
        with screenshot_semaphore:
            log.info(f"[{run_id_for_log}] Semaphore acquired for {url}. Taking screenshot...")
            ok, s_err = _take_screenshot(
                ps, url_full, png_path, screenshot_timeout,
                cfg.screenshots.width, cfg.screenshots.height
            )
            log.info(f"[{run_id_for_log}] Semaphore released for {url}.")

        if not ok:
            png_path = None  # don't link to failed screenshot !!!
            if notes:
                notes += f" | screenshot: {s_err}"
            else:
                notes = f"screenshot: {s_err}"

    geo_str = f"{run_params.get('country') or '-'} / {run_params.get('region_code') or '(any)'} / {run_params.get('city') or '(any)'} / ISP: {run_params.get('isp') or '(any)'}"
    proxy_str = f"SOAX Port-Mode, ext_ip: {ps.ext_ip if ps else '-'}"
    md_text = render_md_card(
        domain=domain,
        started=datetime.now().isoformat(timespec="seconds"),
        geo_str=geo_str,
        proxy_str=proxy_str,
        dns_mode=dns_mode,
        timeout_sec=timeout_sec,
        url_show=url_full,
        redirects=redirects,
        timings=timings,
        http_status=http_status,
        bytes_count=bytes_count,
        result=result,
        screenshot_name=os.path.basename(png_path) if png_path else None,
        notes=notes,
        debug_info=debug_data if debug_mode else None
    )

    log.debug(f"[{run_id_for_log}] Writing .md log for {url} to {md_path}")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)

    return {
        "classification": result,
        "http_code": http_status,
        "bytes_count": bytes_count,
        "timings": timings,
        "redirects": redirects,
        "proxy_ext_ip": ps.ext_ip if ps else None,
        "md_path": md_path,
        "png_path": png_path,
        "notes": notes
    }
