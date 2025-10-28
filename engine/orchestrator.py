from __future__ import annotations
import json, queue, threading, uuid, os, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Any
from config.loader import ConfigStore
from logging_.engine_logger import get_engine_logger
from .worker import execute_check

_engine_logger = get_engine_logger()

_runs_state: Dict[str, Dict[str, Any]] = {}
_sse_queues: Dict[str, "queue.Queue[str]"] = {}
_lock = threading.Lock()


def _sse_emit(run_id: str, payload: dict):
    msg = json.dumps(payload, ensure_ascii=False)

    _engine_logger.debug(
        f"[{run_id}] Emitting SSE event type: {payload.get('type')}, "
        f"URL: {payload.get('url', 'N/A')}"
    )

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

    _engine_logger.info(f"[{run_id}] Background thread started.")

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
        # log: задача взята в пул.
        _engine_logger.info(f"[{run_id}] Task started for URL: {u}")

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

        try:
            # log: Перед блокирующим вызовом
            _engine_logger.debug(f"[{run_id}] Calling execute_check for {u}...")
            res = execute_check(task_specific_params)
            _engine_logger.debug(f"[{run_id}] execute_check finished for {u}.")
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

        png_relative_path = None
        if res.get("png_path"):
            # Получаем относительный путь от базовой директории логов
            # Например, /app/logs/2025-10-26/img.png -> 2025-10-26/img.png
            try:
                png_relative_path = os.path.relpath(res["png_path"], cfg.paths.logs_dir)
                png_relative_path = png_relative_path.replace(os.path.sep, '/')
            except ValueError:
                _engine_logger.error(f"[{run_id}] Could not get relative path for screenshot: {res['png_path']}")
                png_relative_path = os.path.basename(res["png_path"])  # fallback на старое поведение

        row = {
            "url": u,
            "result": res["classification"],
            "http_code": res.get("http_code"),
            "ttfb_ms": res.get("timings", {}).get("ttfb_ms"),
            "ext_ip": res.get("proxy_ext_ip") or "-",
            "md_name": os.path.basename(res["md_path"]),
            "png_name": png_relative_path if png_relative_path else "",
            "notes": res.get("notes")  # Передаем 'notes' в UI
        }
        _sse_emit(run_id, {"type": "check_finished", "run_id": run_id, **row})
        return row

    # пул потоков для проверок
    with ThreadPoolExecutor(max_workers=cfg.execution.max_concurrency) as pool:
        _engine_logger.debug(
            f"[{run_id}] Submitting {len(urls)} tasks to ThreadPoolExecutor (max_workers={cfg.execution.max_concurrency}).")
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

    # завершение запуска
    _engine_logger.info(f"[{run_id}] All tasks finished.")
    st = _runs_state[run_id]

    # try:
        # summary_path = write_run_summary(cfg.paths.logs_dir, st["rows"])
        # summary_name = os.path.basename(summary_path) # если понадобится summary-лог, раскомментировать это и импорт
    # except Exception as e:
    #     _engine_logger.error(f"[{run_id}] Failed to write summary: {e}", exc_info=True)
    #     summary_name = "error.md"
    summary_name = None

    _sse_emit(run_id, {"type": "run_finished", "run_id": run_id,
                       "totals": {"ok": sum(1 for r in st["rows"] if r["result"] == "success"),
                                  "err": sum(1 for r in st["rows"] if r["result"] != "success"),
                                  "time_ms": int((time.time() - st["started_at"]) * 1000)},
                       "summary": summary_name})

    _engine_logger.info(f"[{run_id}] 'run_finished' emitted. Unsubscribing SSE.")

    # отписываемся от SSE, чтобы позволить Response() завершиться
    sse_unsubscribe(run_id)


def start_run(run_params: dict[str, Any]) -> str:
    """
    Вызывается из /run (HTTP).
    Должен вернуться НЕМЕДЛЕННО.
    """
    run_id = uuid.uuid4().hex[:12]
    total = len(run_params.get("urls", []))

    _engine_logger.info(f"[{run_id}] Creating run state (Total: {total} URLs).")

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

    # Создаем очередь SSE _до_ запуска потока
    sse_subscribe(run_id)

    _sse_emit(run_id, {"type": "run_started", "run_id": run_id, "ts": datetime.now().isoformat(timespec="seconds"),
                       "settings": settings_for_sse})

    # запук в фоновом потоке
    _engine_logger.info(f"[{run_id}] Spawning background thread...")
    thread = threading.Thread(
        target=_run_checks_async,
        args=(run_params, run_id),
        daemon=True  # Поток умрет, если gunicorn (главный поток) умрет
    )
    thread.start()

    return run_id
