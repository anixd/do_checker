import os, socket, time, urllib.parse
import requests
from datetime import datetime
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
    # как договорились: если схемы нет — отправляем с http://
    if "://" not in raw:
        return raw, f"http://{raw}"
    return urllib.parse.urlsplit(raw).netloc, raw

def _requests_proxies(ps, scheme: str):
    # Для HTTP/SOCKS5 в requests прокси указываем в словаре.
    # SOCKS5 потребует pysocks; здесь оставим как http (SOCKS будет позже при необходимости).
    auth = f"{ps.username}:{ps.password}@"
    proxy_url = f"{scheme}://{auth}{ps.host}:{ps.port}"
    return {"http": proxy_url, "https": proxy_url}

def _measure_http(url: str, proxies: dict, timeout_sec: int, max_redirects: int = 5):
    timings = {"dns_ms": None, "tcp_ms": None, "tls_ms": None, "ttfb_ms": None, "total_ms": None}
    redirects = []
    http_status = None
    bytes_count = None

    sess = requests.Session()
    sess.max_redirects = max_redirects
    start = time.time()

    # Простой замер ttfb: первый chunk после отправки
    try:
        resp = sess.get(url, proxies=proxies, timeout=timeout_sec, stream=True, allow_redirects=True)
        http_status = resp.status_code
        # Заглушка таймингов (подробный DNS/TCP/TLS потребует другой стек, здесь дашь базовый total/ttfb)
        first_chunk = next(resp.iter_content(chunk_size=1024), b"")
        ttfb = time.time() - start
        timings["ttfb_ms"] = int(ttfb * 1000)
        content = first_chunk + resp.content  # дочитаем остальное
        bytes_count = len(content)
        # redirect history
        for r in resp.history:
            redirects.append((r.status_code, r.url, resp.url))
    except requests.exceptions.RequestException as e:
        # Классификацию сделаем в вызывающем коде
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

def _take_screenshot(ps, url: str, out_path: str, timeout_ms: int, width: int, height: int):
    if not sync_playwright:
        return False, "playwright not installed"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Для SOAX часто достаточно прокси на уровне запросов страницы;
            # если потребуется системный уровень — доработаем.
            ctx = browser.new_context(viewport={"width":width,"height":height})
            page = ctx.new_page()
            page.set_default_navigation_timeout(timeout_ms)
            page.goto(url, wait_until="load")
            page.screenshot(path=out_path, full_page=True)
            browser.close()
        return True, None
    except Exception as e:
        return False, str(e)

def execute_check(
    url: str, country: str, region_code: str | None, isp: str | None,
    proxy_type: str, dns_mode: str, sticky: bool, sticky_ttl_sec: int,
    timeout_sec: int, make_screenshot: bool, run_id: str
) -> dict:
    cfg = ConfigStore.get()
    logs_dir = cfg.paths.logs_dir
    day_dir = ensure_day_dir(logs_dir)

    domain, url_full = _normalize_url(url)
    ts = datetime.now().strftime("%H-%M-%S")
    base_name = f"{ts}_{domain}"

    md_path = unique_file_path(day_dir, base_name, "md")
    png_path = None

    # Прокси-сессия SOAX
    ps = get_session(country, region_code, isp, sticky, sticky_ttl_sec, proxy_type, dns_mode)
    scheme = "http" if proxy_type == "http" else "http"  # SOCKS5 прокинем позже с pysocks
    proxies = _requests_proxies(ps, scheme)

    http_status = None
    bytes_count = None
    redirects = []
    timings = {}
    notes = None
    exc = None

    try:
        http_status, bytes_count, redirects, timings = _measure_http(url_full, proxies, timeout_sec)
    except Exception as e:
        exc = e
        notes = str(e)

    result = _classify(exc, http_status, timeout_sec)

    # Скриншот
    if make_screenshot and result == "success":
        png_path = unique_file_path(day_dir, base_name, "png")
        ok, s_err = _take_screenshot(ps, url_full, png_path, timeout_sec*1000, cfg.screenshots.width, cfg.screenshots.height)
        if not ok:
            png_path = None
            if notes:
                notes += f" | screenshot: {s_err}"
            else:
                notes = f"screenshot: {s_err}"

    # Markdown карточка
    geo_str = f"{country or '-'} / {region_code or '(any)'} / ISP: {isp or '(any)'} (fallback: on)"  # fallback пометим позже реальным
    proxy_str = f"SOAX {proxy_type.upper()}, sticky: {'on' if sticky else 'off'} (ttl={sticky_ttl_sec}), ext_ip: {ps.ext_ip or '-'}"
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
        notes=notes
    )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)

    return {
        "classification": result,
        "http_code": http_status,
        "bytes_count": bytes_count,
        "timings": timings,
        "redirects": redirects,
        "proxy_ext_ip": ps.ext_ip,
        "md_path": md_path,
        "png_path": png_path
    }
