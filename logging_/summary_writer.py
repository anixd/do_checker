import os
from datetime import datetime

def write_run_summary(logs_dir: str, rows: list[dict]) -> str:
    day_dir = os.path.join(logs_dir, datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(day_dir, exist_ok=True)
    base = datetime.now().strftime("%H-%M-%S") + "_run-summary"
    path = os.path.join(day_dir, base + ".md")
    lines = []
    lines.append(f"# Run summary ({datetime.now().isoformat(timespec='seconds')})")
    lines.append("")
    lines.append("| # | URL | Result | HTTP | TTFB (ms) | Proxy IP | File | Screenshot |")
    lines.append("|---|-----|--------|------|-----------|----------|------|------------|")
    for i, r in enumerate(rows, start=1):
        lines.append(f"| {i} | {r.get('url','')} | {r.get('result','')} | {r.get('http_code','-')} | {r.get('ttfb_ms','-')} | {r.get('ext_ip','-')} | {r.get('md_name','')} | {r.get('png_name','')} |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
