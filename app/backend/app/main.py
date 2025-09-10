from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, bots, instances, admin, users
from app.core.config import settings
from app.db.session import AsyncSessionLocal

app = FastAPI(title="Bots Shop API", version="0.1.0")

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
