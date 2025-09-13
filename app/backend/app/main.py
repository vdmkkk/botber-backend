from fastapi import FastAPI, Request, status
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.schemas.common import ErrorResponse
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode

from app.api.routes import auth, bots, instances, admin, users
from app.core.config import settings
from app.db.session import AsyncSessionLocal

import asyncio, contextlib
from app.services.billing import process_due_instances

app = FastAPI(title="BotBeri API", version="0.1.0")

stop_billing = asyncio.Event()

async def _billing_loop():
    try:
        while not stop_billing.is_set():
            await process_due_instances()
            try:
                await asyncio.wait_for(stop_billing.wait(), timeout=settings.BILLING_TICK_SECONDS)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        pass

@app.on_event("startup")
async def _start_billing():
    app.state._billing_task = asyncio.create_task(_billing_loop())

@app.on_event("shutdown")
async def _stop_billing():
    stop_billing.set()
    task = getattr(app.state, "_billing_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(Exception):
            await task

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    payload = exc.detail if isinstance(exc.detail, dict) else {}
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=payload.get("error_code", ErrorCode.INTERNAL_ERROR),
            user_message=payload.get("user_message"),
            details=payload.get("details"),
        ).model_dump(),
    )

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error_code=ErrorCode.VALIDATION_ERROR,
            user_message="Invalid request data",
            details={"errors": exc.errors()},
        ).model_dump(),
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Map plain HTTPExceptions (if any) into our envelope
    code_map = {
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        409: ErrorCode.CONFLICT,
        429: ErrorCode.RATE_LIMITED,
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=code_map.get(exc.status_code, ErrorCode.BAD_REQUEST),
            user_message=str(exc.detail) if exc.detail else None,
        ).model_dump(),
    )

@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    # Try to distinguish unique constraint violations
    msg = str(exc.orig).lower() if exc.orig else ""
    if "unique" in msg or "duplicate" in msg:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ErrorResponse(
                error_code=ErrorCode.UNIQUE_CONSTRAINT_VIOLATION,
                user_message="Unique constraint violated",
                details={"db_message": msg},
            ).model_dump(),
        )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error_code=ErrorCode.DATABASE_ERROR,
            user_message="Database error",
            details={"db_message": msg},
        ).model_dump(),
    )

@app.exception_handler(SQLAlchemyError)
async def sa_error_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error_code=ErrorCode.DATABASE_ERROR,
            user_message="Database error",
        ).model_dump(),
    )

@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error_code=ErrorCode.INTERNAL_ERROR,
            user_message="Internal server error",
        ).model_dump(),
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in prod (or read from env)
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(bots.router)
app.include_router(instances.router)
app.include_router(admin.router)
app.include_router(users.router)

scheduler: AsyncIOScheduler | None = None

@app.on_event("startup")
async def on_startup():
    # daily billing at 03:10 UTC
    global scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_billing_job, CronTrigger(hour=3, minute=10, timezone="UTC"))
    scheduler.start()

async def _billing_job():
    from app.services.billing import run_daily_billing
    async with AsyncSessionLocal() as db:
        await run_daily_billing(db)
