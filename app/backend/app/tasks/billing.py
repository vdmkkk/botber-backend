import asyncio
from app.celery_app import celery_app
from app.services.billing import process_due_instances

@celery_app.task(name="app.tasks.billing.process_due")
def process_due():
    asyncio.run(process_due_instances())
