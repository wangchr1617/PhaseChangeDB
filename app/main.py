import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import extraction, mvp, workflow
from app.core.config import get_settings
from app.domain.workflow import WorkflowDomainError
from app.infrastructure.database import session_factory

settings = get_settings()
app = FastAPI(
    title="PhaseChangeDB API",
    version="0.2.0-mvp",
    summary="面向相变材料的证据化数据与发现 API。",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(mvp.router)
app.include_router(workflow.router)
app.include_router(extraction.router)

# 兼容前端在无 Nginx 反代直连场景（直接请求 /api/v1/*）
app.include_router(mvp.router, prefix="/api")
app.include_router(workflow.router, prefix="/api")
app.include_router(extraction.router, prefix="/api")


STATUS_TITLE_MAP = {
    400: "请求参数错误",
    401: "未授权或凭据无效",
    403: "禁止访问",
    404: "资源不存在",
    409: "数据冲突或非法流转",
    412: "前置条件不满足或版本过期",
    422: "请求校验失败",
    503: "服务不可用或未就绪",
}


def _resolve_request_id(request: Request) -> str:
    """提取或生成统一的 Request ID。"""
    req_id = getattr(request.state, "request_id", None)
    if not req_id:
        req_id = request.headers.get("X-Request-ID")
    if not req_id or not req_id.strip():
        req_id = str(uuid4())
        request.state.request_id = req_id
    return req_id


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = _resolve_request_id(request)
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(WorkflowDomainError)
async def domain_error_handler(request: Request, exc: WorkflowDomainError) -> JSONResponse:
    request_id = _resolve_request_id(request)
    title = STATUS_TITLE_MAP.get(exc.status_code, "业务逻辑错误")
    return JSONResponse(
        status_code=exc.status_code,
        media_type="application/problem+json",
        headers={"X-Request-ID": request_id},
        content={
            "type": "about:blank",
            "title": title,
            "status": exc.status_code,
            "detail": exc.message,
            "request_id": request_id,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = _resolve_request_id(request)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        media_type="application/problem+json",
        headers={"X-Request-ID": request_id},
        content={
            "type": "about:blank",
            "title": "请求校验失败",
            "status": 422,
            "detail": "提交的请求载荷未能通过模型校验。",
            "errors": [
                {
                    "loc": [str(loc_item) for loc_item in err.get("loc", [])],
                    "msg": err.get("msg"),
                    "type": err.get("type"),
                }
                for err in exc.errors()
            ],
            "request_id": request_id,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = _resolve_request_id(request)
    title = STATUS_TITLE_MAP.get(exc.status_code, "HTTP 请求错误")
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        media_type="application/problem+json",
        headers={"X-Request-ID": request_id},
        content={
            "type": "about:blank",
            "title": title,
            "status": exc.status_code,
            "detail": detail,
            "request_id": request_id,
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    request_id = _resolve_request_id(request)
    return JSONResponse(
        status_code=409,
        media_type="application/problem+json",
        headers={"X-Request-ID": request_id},
        content={
            "type": "about:blank",
            "title": "数据冲突",
            "status": 409,
            "detail": "提交的数据违反唯一性或引用完整性约束。",
            "request_id": request_id,
        },
    )


@app.get("/health", tags=["system"], summary="存活探针（Liveness Probe）")
async def health() -> dict[str, str]:
    """系统存活探针，返回应用进程正常存活状态。"""
    return {"status": "ok"}


@app.get("/ready", tags=["system"], summary="就绪探针（Readiness Probe）")
async def ready(response: Response) -> dict[str, str]:
    """系统就绪探针，探测核心数据库真实可用性。"""
    if os.environ.get("PCM_DEMO_MODE") == "1":
        return {"status": "ready", "database": "demo_mode"}
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": "unavailable"}


# 挂载前端预编译静态页面（开箱即用，免 Nginx / Node.js）
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
