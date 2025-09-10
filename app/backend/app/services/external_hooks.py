# Placeholder external API call when a new instance is created.
import httpx

async def notify_instance_created(instance_id: int, payload: dict) -> None:
    # TODO: fill real URL & auth later
    url = "https://placeholder.external.api/instances"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json={"instance_id": instance_id, **payload})
    except Exception:
        pass  # swallow for now
