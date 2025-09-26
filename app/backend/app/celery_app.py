import asyncio
from celery import Celery
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from app.core.config import settings

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[CeleryIntegration()],
        traces_sample_rate=0.2,
        environment=settings.ENV,
        release=settings.GIT_SHA,
    )

celery_app = Celery(
    "app",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    timezone=settings.CELERY_TIMEZONE,
    task_default_queue="default",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)

# Beat schedule (periodic tasks)
celery_app.conf.beat_schedule = {
    "billing-tick": {
        "task": "app.tasks.billing.process_due",
        "schedule": 300.0,  # 5 min
    },
    "health-scan": {
        "task": "app.tasks.health.scan_and_dispatch",
        "schedule": 3600.0,  # 60 min
    },
    "kb-scan": {
        "task": "app.tasks.kb.scan_and_dispatch",
        "schedule": 30.0,    # 30 sec
    },
}
