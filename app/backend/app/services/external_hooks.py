import httpx
import uuid

# Placeholder: create the remote instance and return its instance_id.
# Later you'll implement actual HTTP call with activation_code + config.
async def create_remote_instance(*, activation_code: str, config: dict) -> str:
    # TODO: replace this with a real API call:
    # async with httpx.AsyncClient(timeout=10) as client:
    #     r = await client.post("https://foreign.api/instances", json={"activation_code": activation_code, "config": config})
    #     r.raise_for_status()
    #     return r.json()["instance_id"]
    return f"stub-{uuid.uuid4()}"

# Optional: keep the fire-and-forget notifier
async def notify_instance_created(instance_id: int, payload: dict) -> None:
    url = "https://placeholder.external.api/instances"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json={"instance_id": instance_id, **payload})
    except Exception:
        pass
