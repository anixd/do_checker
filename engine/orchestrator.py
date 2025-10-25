from __future__ import annotations
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
        try:
            q.put(msg, block=False)
        except queue.Full:
            _engine_logger.warning(f"SSE queue full for run_id {run_id}")


def sse_subscribe(run_id: str) -> "queue.Queue[str]":
    """Вызывается UI (SSE) для подписки на события."""
    q: "queue.Queue[str]" = queue.Queue(maxsize=100)
    with _lock:
        _sse_queues[run_id] = q
    return q


def sse_unsubscribe(run_id: str):
    """Вызывается, когда SSE-поток завершен."""
    with _lock:
        _sse_queues.pop(run_id, None)


def get_run_state(run_id: str):
    with _lock:
        return _runs_state.get(run_id, {"total": 0, "done": 0})


def _run_checks_async(run_params: dict[str, Any], run_id: str):
    """
    Эта функция выполняется в отдельном потоке (Thread)
    и делает всю тяжелую работу.
    """
    cfg = ConfigStore.get()
    urls = run_params.get("urls", [])

    # Определяем sticky для всего запуска
    sticky_policy = run_params.get("sticky_policy", "auto")
    sticky = (sticky_policy == "on") or (sticky_policy == "auto" and len(urls) > 1)

    # Добавляем run_id и sticky в params для воркера
    task_params = run_params.copy()
    task_params["run_id"] = run_id
    task_params["sticky"] = sticky

    def worker_task(u: str):
        # Передаем копию словаря + URL в воркер
        task_specific_params = task_params.copy()
        task_specific_params["url"] = u

        _sse_emit(run_id, {
            "type": "check_started",
            "run_id": run_id, "url": u,
            "country": task_params.get("country"),
            "region": task_params.get("region_code"),
            "isp": task_params.get("isp")
        })

        # --- ВЫПОЛНЕНИЕ ПРОВЕРКИ ---
        try:
            res = execute_check(task_specific_params)
        except Exception as e:
            _engine_logger.error(f"[{run_id}] Unhandled exception in execute_check for {u}: {e}", exc_info=True)
            res = {  # Создаем 'error' результат
                "classification": "connect_error",
                "notes": f"Worker failed: {e}",
                "timings": {},
                "md_path": "error.md",
                "proxy_ext_ip": None,
                "png_path": None,
            }

        row = {
            "url": u,
            "result": res["classification"],
            "http_code": res.get("http_code"),
            "ttfb_ms": res.get("timings", {}).get("ttfb_ms"),
            "ext_ip": res.get("proxy_ext_ip") or "-",
            "md_name": os.path.basename(res["md_path"]),
            "png_name": os.path.basename(res["png_path"]) if res.get("png_path") else "",
            "notes": res.get("notes")  # Передаем 'notes' в UI
        }
        _sse_emit(run_id, {"type": "check_finished", "run_id": run_id, **row})
        return row

    # --- ПУЛ ПОТОКОВ ДЛЯ ПРОВЕРОК ---
    with ThreadPoolExecutor(max_workers=cfg.execution.max_concurrency) as pool:
        futs = [pool.submit(worker_task, u) for u in urls]
        for fut in as_completed(futs):
            try:
                row = fut.result()
                with _lock:
                    st = _runs_state[run_id]
                    st["rows"].append(row)
                    st["done"] += 1
            except Exception as e:
                _engine_logger.error(f"[{run_id}] Future failed: {e}", exc_info=True)

    # --- ЗАВЕРШЕНИЕ ЗАПУСКА ---
    st = _runs_state[run_id]
    try:
        summary_path = write_run_summary(cfg.paths.logs_dir, st["rows"])
        summary_name = os.path.basename(summary_path)
    except Exception as e:
        _engine_logger.error(f"[{run_id}] Failed to write summary: {e}", exc_info=True)
        summary_name = "error.md"

    _sse_emit(run_id, {"type": "run_finished", "run_id": run_id,
                       "totals": {"ok": sum(1 for r in st["rows"] if r["result"] == "success"),
                                  "err": sum(1 for r in st["rows"] if r["result"] != "success"),
                                  "time_ms": int((time.time() - st["started_at"]) * 1000)},
                       "summary": summary_name})

    # Отписываемся от SSE, чтобы позволить Response() завершиться
    sse_unsubscribe(run_id)


def start_run(run_params: dict[str, Any]) -> str:
    """
    Вызывается из /run (HTTP).
    Должен вернуться НЕМЕДЛЕННО.
    """
    run_id = uuid.uuid4().hex[:12]
    total = len(run_params.get("urls", []))

    state = {
        "run_id": run_id,
        "total": total,
        "done": 0,
        "rows": [],
        "started_at": time.time(),
    }
    with _lock:
        _runs_state[run_id] = state

    # Удаляем 'urls' из настроек, которые пойдут в SSE
    settings_for_sse = {k: v for k, v in run_params.items() if k != 'urls'}

    # Создаем очередь SSE *до* запуска потока
    sse_subscribe(run_id)

    _sse_emit(run_id, {"type": "run_started", "run_id": run_id, "ts": datetime.now().isoformat(timespec="seconds"),
                       "settings": settings_for_sse})

    # --- ЗАПУСК В ФОНОВОМ ПОТОКЕ ---
    thread = threading.Thread(
        target=_run_checks_async,
        args=(run_params, run_id),
        daemon=True  # Поток умрет, если Gunicorn (главный поток) умрет
    )
    thread.start()

    return run_id
