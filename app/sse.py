from flask import Blueprint, Response
from engine.orchestrator import sse_subscribe

bp = Blueprint("sse", __name__, url_prefix="/events")

@bp.get("/<run_id>")
def events(run_id: str):
    def stream():
        q = sse_subscribe(run_id)
        while True:
            msg = q.get()  # блокирующе
            yield f"data: {msg}\n\n"
            if '"type":"run_finished"' in msg:
                break
    return Response(stream(), mimetype="text/event-stream")
