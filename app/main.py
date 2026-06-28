import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import HTTP_REQUEST_LATENCY
from app.core.security import require_api_key
from app.db.session import init_db
from app.schemas.status import ServiceStatus, build_service_status


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    init_db()
    yield


app = FastAPI(
    title="D-Lens",
    description="LLM reliability and root-cause-analysis microservice.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    HTTP_REQUEST_LATENCY.labels(method=request.method, path=request.url.path).observe(elapsed)
    return response


@app.get("/health", response_model=ServiceStatus, tags=["health"])
def health() -> ServiceStatus:
    return build_service_status()


@app.get("/status", response_model=ServiceStatus, tags=["health"])
def service_status() -> ServiceStatus:
    return build_service_status()


@app.get("/metrics", dependencies=[Depends(require_api_key)], tags=["metrics"])
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(api_router)
