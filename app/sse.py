from flask import Blueprint, Response
from engine.orchestrator import sse_subscribe
from logging_.engine_logger import get_engine_logger

log = get_engine_logger()

bp = Blueprint("sse", __name__, url_prefix="/events")

@bp.get("/<run_id>")
def events(run_id: str):
    log.info(f"[{run_id}] Client connected to SSE stream.")

    def stream():
        q = sse_subscribe(run_id)
        while True:
            msg = q.get()  # блокирующе ждем сообщение или None

            # проверяем на None
            if msg is None:
                log.debug(f"[{run_id}] Received None sentinel, closing SSE stream.")
                break  # Выходим из цикла, если пришел None

            yield f"data: {msg}\n\n"

    return Response(stream(), mimetype="text/event-stream")
