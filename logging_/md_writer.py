import os, json
from datetime import datetime

def ensure_day_dir(logs_dir: str) -> str:
    day = datetime.now().strftime("%Y-%m-%d")
    d = os.path.join(logs_dir, day)
    os.makedirs(d, exist_ok=True)
    return d

def unique_file_path(base_dir: str, name: str, ext: str) -> str:
    path = os.path.join(base_dir, f"{name}.{ext}")
    if not os.path.exists(path):
        return path
    i = 2
    while True:
        path2 = os.path.join(base_dir, f"{name}-{i}.{ext}")
        if not os.path.exists(path2):
            return path2
        i += 1

def render_md_card(
    domain: str, started: str, geo_str: str, proxy_str: str, dns_mode: str,
    timeout_sec: int, url_show: str, redirects: list, timings: dict,
    http_status: int | None, bytes_count: int | None, result: str,
    screenshot_name: str | None, notes: str | None,
    debug_info: dict | None = None # <-- ДОБАВЛЕНО
) -> str:
    lines = []
    lines.append(f"# {domain}")
    lines.append(f"Started: {started}")
    lines.append(f"Geo: {geo_str}")
    lines.append(f"Proxy: {proxy_str}")
    lines.append(f"DNS mode: {dns_mode}")
    lines.append(f"Timeout: {timeout_sec}s")
    lines.append(f"URL: {url_show}")
    lines.append("")
    lines.append("## Redirect chain")
    if redirects:
        for i,(code,frm,to) in enumerate(redirects, start=1):
            lines.append(f"{i}) {code} → {to}")
    else:
        lines.append("—")
    lines.append("")
    lines.append("## Timings")
    t = timings or {}
    lines.append(f"DNS: {t.get('dns_ms','-')}ms | TCP: {t.get('tcp_ms','-')}ms | TLS: {t.get('tls_ms','-')}ms | TTFB: {t.get('ttfb_ms','-')}ms | Total: {t.get('total_ms','-')}ms")
    lines.append("")
    lines.append("## HTTP")
    lines.append(f"Status: {http_status if http_status is not None else '-'}")
    lines.append(f"Bytes: {bytes_count if bytes_count is not None else '-'}")
    lines.append("Important headers: –")
    lines.append("")
    lines.append("## Result")
    emoji = "✅" if result=="success" else "❌"
    lines.append(f"{emoji} {result}")
    if screenshot_name:
        lines.append(f"Screenshot: {screenshot_name}")
    lines.append(f"Notes: {notes or '—'}")

    if debug_info:
        lines.append("")
        lines.append("## Debug Info")
        lines.append("```json")
        lines.append(json.dumps(debug_info, indent=2))
        lines.append("```")

    return "\n".join(lines)
