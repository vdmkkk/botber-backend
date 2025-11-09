from celery import Celery
from app.core.config import settings
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration

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
    include=[
        "app.tasks.billing",
        "app.tasks.health",
        "app.tasks.kb",
    ],
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

# Route families to named queues (optional but nice)
celery_app.conf.task_routes = {
    "app.tasks.health.*":  {"queue": "health"},
    "app.tasks.kb.*":      {"queue": "kb"},
    "app.tasks.billing.*": {"queue": "billing"},
}

# Beat schedule unchanged
celery_app.conf.beat_schedule = {
    "billing-tick": {
        "task": "app.tasks.billing.process_due",
        "schedule": float(settings.BILLING_TICK_SECONDS),
    },
    "health-scan": {
        "task": "app.tasks.health.scan_and_dispatch",
        "schedule": float(settings.HEALTH_POLL_INTERVAL_SECONDS),
    },
    "kb-scan": {
        "task": "app.tasks.kb.scan_and_dispatch",
        "schedule": float(settings.KB_POLL_INTERVAL_SECONDS),
    },
}
