
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
import logging
import time
from prometheus_client import Histogram, Counter, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from .auth import require_roles, validate_auth_configuration
from .control_routes import router as control_router
from .data_pipeline import ensure_runtime_state
from .hardware_routes import router as hardware_router
from .mcp_routes import router as mcp_router
from .routes import router


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("app.http")

FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


# Prometheus metrics
REQUEST_TIME = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "status_code"]
)
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_host = request.client.host if request.client is not None else "unknown"
        logger.info(f"{request.method} {request.url.path} from {client_host}")
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        endpoint = request.url.path
        status_code = str(response.status_code)
        REQUEST_TIME.labels(request.method, endpoint, status_code).observe(duration)
        REQUEST_COUNT.labels(request.method, endpoint, status_code).inc()
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "img-src 'self' blob: data:; "
            "style-src 'self'; "
            "style-src-elem 'self'; "
            # TODO: Remove this allowance after the remaining React inline style props
            # are migrated to CSS classes or a nonce/hash-based strategy.
            "style-src-attr 'unsafe-inline'; "
            "script-src 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'none';"
        )
        return response


def _resolve_frontend_asset(request_path: str) -> Path | None:
    normalized_path = request_path.strip("/")
    if not normalized_path:
        return FRONTEND_DIST_DIR / "index.html"

    candidate = (FRONTEND_DIST_DIR / normalized_path).resolve()
    try:
        candidate.relative_to(FRONTEND_DIST_DIR)
    except ValueError:
        return None

    if candidate.is_file():
        return candidate
    return None


def _frontend_bundle_available() -> bool:
    return FRONTEND_DIST_DIR.is_dir() and (FRONTEND_DIST_DIR / "index.html").is_file()



@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_auth_configuration()
    yield


app = FastAPI(lifespan=lifespan)
# Prime runtime state once at import time so existing tests and direct app consumers
# can access app.state.settings before the first request.
ensure_runtime_state(app)
app.add_middleware(LoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Prometheus metrics endpoint
@app.get("/metrics")
def metrics(user=Depends(require_roles("admin"))):
    del user
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    headers = getattr(exc, 'headers', None)
    if exc.status_code == 401:
        # Ensure WWW-Authenticate header is present for 401
        if not headers:
            headers = {"WWW-Authenticate": "Basic"}
        elif "WWW-Authenticate" not in headers:
            headers = dict(headers)
            headers["WWW-Authenticate"] = "Basic"
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail or str(exc)},
        headers=headers,
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled application error for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

@app.get("/")
def read_root(request: Request):
    if "text/html" in request.headers.get("accept", "").lower() and _frontend_bundle_available():
        return RedirectResponse(url="/app")

    return {
        "message": "Welcome to the Dental Practice Financial Dashboard",
        "app_url": "/app" if _frontend_bundle_available() else None,
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Mount each router once. Root-backed handlers own any required /api compatibility aliases.
app.include_router(router)
app.include_router(control_router)
app.include_router(hardware_router)
app.include_router(mcp_router)


@app.get("/app", include_in_schema=False)
@app.get("/app/{request_path:path}", include_in_schema=False)
def serve_frontend_app(request_path: str = ""):
    if not _frontend_bundle_available():
        raise HTTPException(
            status_code=503,
            detail="Frontend assets are unavailable. Run 'npm run build' to generate frontend/dist, or 'npm run dev' for the merged local watcher.",
        )

    asset_path = _resolve_frontend_asset(request_path)
    if asset_path is not None:
        return FileResponse(asset_path)

    if "." in Path(request_path).name:
        raise HTTPException(status_code=404, detail="Frontend asset not found")

    return FileResponse(FRONTEND_DIST_DIR / "index.html")
