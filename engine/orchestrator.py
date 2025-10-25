import json, queue, threading, uuid, os, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Any
from config.loader import ConfigStore
from logging_.engine_logger import get_engine_logger
from logging_.summary_writer import write_run_summary
from .worker import execute_check

_engine_logger = get_engine_logger()

_runs_state: Dict[str, Dict[str, Any]] = {}
_sse_queues: Dict[str, "queue.Queue[str]"] = {}
_lock = threading.Lock()

def _sse_emit(run_id: str, payload: dict):
    msg = json.dumps(payload, ensure_ascii=False)
    with _lock:
        q = _sse_queues.get(run_id)
    if q:
        q.put(msg)

def sse_subscribe(run_id: str) -> "queue.Queue[str]":
    q: "queue.Queue[str]" = queue.Queue()
    with _lock:
        _sse_queues[run_id] = q
    return q

def get_run_state(run_id: str):
    with _lock:
        return _runs_state.get(run_id, {"total":0,"done":0})

def start_run(
    urls: list[str],
    country: str, region_code: str | None, isp: str | None,
    proxy_type: str, dns_mode: str, sticky_policy: str,
    sticky_ttl_sec: int, timeout_sec: int, make_screenshot: bool
) -> str:
    cfg = ConfigStore.get()
    run_id = uuid.uuid4().hex[:12]
    total = len(urls)

    state = {
        "run_id": run_id,
        "total": total,
        "done": 0,
        "rows": [],
        "started_at": time.time(),
    }
    with _lock:
        _runs_state[run_id] = state

    settings = dict(
        proxy_type=proxy_type, dns_mode=dns_mode,
        sticky_policy=sticky_policy, sticky_ttl_sec=sticky_ttl_sec,
        timeout_sec=timeout_sec, make_screenshot=make_screenshot,
        country=country, region=region_code, isp=isp,
    )
    _sse_emit(run_id, {"type":"run_started","run_id":run_id,"ts":datetime.now().isoformat(timespec="seconds"),"settings":settings})

    # sticky включаем для всего run, если policy=auto и url>1
    sticky = (sticky_policy=="on") or (sticky_policy=="auto" and len(urls)>1)

    def worker_task(u: str):
        _sse_emit(run_id, {"type":"check_started","run_id":run_id,"url":u,"country":country,"region":region_code,"isp":isp})
        res = execute_check(
            url=u, country=country, region_code=region_code, isp=isp,
            proxy_type=proxy_type, dns_mode=dns_mode, sticky=sticky,
            sticky_ttl_sec=sticky_ttl_sec, timeout_sec=timeout_sec,
            make_screenshot=make_screenshot, run_id=run_id
        )
        row = {
            "url": u,
            "result": res["classification"],
            "http_code": res.get("http_code"),
            "ttfb_ms": res.get("timings",{}).get("ttfb_ms"),
            "ext_ip": res.get("proxy_ext_ip") or "-",
            "md_name": os.path.basename(res["md_path"]),
            "png_name": os.path.basename(res["png_path"]) if res.get("png_path") else "",
        }
        _sse_emit(run_id, {"type":"check_finished","run_id":run_id, **row})
        return row

    with ThreadPoolExecutor(max_workers=cfg.execution.max_concurrency) as pool:
        futs = [pool.submit(worker_task, u) for u in urls]
        for fut in as_completed(futs):
            row = fut.result()
            with _lock:
                st = _runs_state[run_id]
                st["rows"].append(row)
                st["done"] += 1

    # summary
    st = _runs_state[run_id]
    summary_path = write_run_summary(cfg.paths.logs_dir, st["rows"])
    _sse_emit(run_id, {"type":"run_finished","run_id":run_id,"totals":{"ok": sum(1 for r in st["rows"] if r["result"]=="success"),
                                                                      "err": sum(1 for r in st["rows"] if r["result"]!="success"),
                                                                      "time_ms": int((time.time()-st["started_at"])*1000)},
                         "summary": os.path.basename(summary_path)})
    return run_id
