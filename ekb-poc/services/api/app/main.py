import json
import logging
import time
import uuid

from fastapi import FastAPI, Request

from .bootstrap import bootstrap
from .pipeline.run import resume_pipeline
from .routers import admin, documents, query, tasks


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record), "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        if hasattr(record, "trace_id"):
            payload["trace_id"] = record.trace_id
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
log = logging.getLogger("ekb.api")

app = FastAPI(title="Enterprise Knowledge Base API", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    bootstrap()
    resume_pipeline()


@app.middleware("http")
async def trace(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex[:16]
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["x-trace-id"] = trace_id
    if request.url.path != "/api/health":
        log.info(
            "%s %s %s %dms",
            request.method,
            request.url.path,
            response.status_code,
            int((time.perf_counter() - t0) * 1000),
            extra={"trace_id": trace_id},
        )
    return response


for r in (admin.router, documents.router, tasks.router, query.router):
    app.include_router(r)
