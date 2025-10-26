from __future__ import annotations
import os, socket, time, urllib.parse
import requests
from datetime import datetime
from typing import Any
from providers.soax import get_session
from config.loader import ConfigStore
from logging_.md_writer import ensure_day_dir, unique_file_path, render_md_card
from logging_.engine_logger import get_engine_logger

try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None

log = get_engine_logger()


def _normalize_url(raw: str) -> tuple[str, str]:
    if "://" not in raw:
        return raw, f"http://{raw}"
    return urllib.parse.urlsplit(raw).netloc, raw


def _requests_proxies(ps: ProxySession, dns_mode: str) -> dict:
    """
    Собирает словарь прокси для `requests`
    ps: dataclass ProxySession
    dns_mode: 'proxy' или 'local'
    """
    auth = f"{ps.username}:{ps.password}@"

    if ps.type == "socks5":
        # SOCKS5 → запросы уходят через socks5h://
        # DNS-режим: `via proxy` или `local`.
        # requests[socks] использует 'socks5h://' для DNS через прокси
        # и 'socks5://' для локального DNS.
        scheme = "socks5h" if dns_mode == "proxy" else "socks5"
    else:
        # По умолчанию HTTP
        scheme = "http"

    proxy_url = f"{scheme}://{auth}{ps.host}:{ps.port}"

    # requests использует ключи 'http' и 'https' для *всех* типов прокси
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

        redirects = []
        for r in resp.history:
            redirects.append((r.status_code, r.url, r.headers.get('Location', '')))
        if resp.url != url and not resp.history:
            redirects.append((http_status, url, resp.url))
        elif resp.history:
            redirects.append((resp.status_code, resp.request.url, resp.url))
            if len(redirects) > 1 and redirects[-1][1] == redirects[-2][2]:
                redirects.pop(-2)
                redirects[-1] = (redirects[-1][0], redirects[-2][1], redirects[-1][2])

    except requests.exceptions.RequestException as e:
        end = time.time()
        timings["total_ms"] = int((end - start) * 1000)
        raise e

    end = time.time()
    timings["total_ms"] = int((end - start) * 1000)

    return http_status, bytes_count, redirects, timings


def _classify(exc: Exception | None, http_status: int | None, timeout_sec: int) -> str:
    # ... (без изменений) ...
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


def _take_screenshot(ps, url: str, out_path: str, timeout_ms: int, width: int, height: int):
    if not sync_playwright:
        return False, "playwright not installed"

    cfg = ConfigStore.get()  # <-- Получаем конфиг

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": width, "height": height},
                user_agent=cfg.http_client.user_agent
            )
            page = ctx.new_page()
            page.set_default_navigation_timeout(timeout_ms)
            page.goto(url, wait_until="load")
            page.screenshot(path=out_path, full_page=True)
            browser.close()
        return True, None
    except Exception as e:
        return False, str(e)


def execute_check(run_params: dict[str, Any]) -> dict:
    cfg = ConfigStore.get()
    logs_dir = cfg.paths.logs_dir
    day_dir = ensure_day_dir(logs_dir)

    url = run_params["url"]
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
        ps = get_session(run_params)
        debug_data = ps.debug_info
        proxies = _requests_proxies(ps, dns_mode)
        http_status, bytes_count, redirects, timings = _measure_http(url_full, proxies, timeout_sec)

    except Exception as e:
        exc = e
        notes = str(e)
        if debug_data is None:
            debug_data = {"error": str(e)}

    result = _classify(exc, http_status, timeout_sec)

    if make_screenshot and result == "success":
        png_path = unique_file_path(day_dir, base_name, "png")
        ok, s_err = _take_screenshot(ps, url_full, png_path, timeout_sec * 1000, cfg.screenshots.width,
                                     cfg.screenshots.height)
        if not ok:
            png_path = None
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
        dns_mode=run_params.get("dns_mode"),
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
