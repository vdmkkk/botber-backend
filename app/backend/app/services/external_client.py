import httpx
from typing import Any, Dict
from app.core.config import settings

def _client(base: str, token: str | None) -> httpx.AsyncClient:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.AsyncClient(base_url=base.rstrip("/"), headers=headers, timeout=10)

# ---------- Instances API ----------
async def ext_create_instance(*, activation_code: str, vars: dict) -> str:
    payload = {"name": activation_code, "vars": vars or {}}
    async with _client(settings.EXTERNAL_API_BASE_URL, settings.EXTERNAL_API_TOKEN) as c:
        r = await c.post("/instances", json=payload)
        r.raise_for_status()
        return r.json()["id"]

async def ext_patch_instance(instance_id: str, *, vars: dict) -> None:
    payload = {"vars": vars or {}}
    async with _client(settings.EXTERNAL_API_BASE_URL, settings.EXTERNAL_API_TOKEN) as c:
        r = await c.patch(f"/instances/{instance_id}", json=payload)
        r.raise_for_status()

async def ext_delete_instance(instance_id: str) -> None:
    async with _client(settings.EXTERNAL_API_BASE_URL, settings.EXTERNAL_API_TOKEN) as c:
        r = await c.delete(f"/instances/{instance_id}")
        r.raise_for_status()

async def ext_activate_instance(instance_id: str) -> None:
    async with _client(settings.EXTERNAL_API_BASE_URL, settings.EXTERNAL_API_TOKEN) as c:
        r = await c.post(f"/instances/{instance_id}/activate")
        r.raise_for_status()

async def ext_deactivate_instance(instance_id: str) -> None:
    async with _client(settings.EXTERNAL_API_BASE_URL, settings.EXTERNAL_API_TOKEN) as c:
        r = await c.post(f"/instances/{instance_id}/deactivate")
        r.raise_for_status()

async def ext_health(instance_id: str) -> str:
    async with _client(settings.EXTERNAL_API_BASE_URL, settings.EXTERNAL_API_TOKEN) as c:
        r = await c.get(f"/instances/{instance_id}/health")
        r.raise_for_status()
        return r.json()["status"]  # provisioning/active/inactive/updating/deleting/error/unknown

# ---------- Knowledge API ----------
def _kb_base() -> str:
    return settings.KB_API_BASE_URL or settings.EXTERNAL_API_BASE_URL

async def kb_create_entry(*, instance_id: str, content: str) -> str:
    payload = {"instance_id": instance_id, "content": content}
    async with _client(_kb_base(), settings.KB_API_TOKEN or settings.EXTERNAL_API_TOKEN) as c:
        r = await c.post("/entry", json=payload)
        r.raise_for_status()
        return r.json()["entry_id"]

async def kb_delete_entry(*, instance_id: str, entry_id: str) -> None:
    payload = {"instance_id": instance_id, "entry_id": entry_id}
    async with _client(_kb_base(), settings.KB_API_TOKEN or settings.EXTERNAL_API_TOKEN) as c:
        r = await c.request("DELETE", "/entry", json=payload)
        r.raise_for_status()
