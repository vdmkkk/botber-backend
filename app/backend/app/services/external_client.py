import httpx
from typing import Any, Dict, Tuple
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
        print(r.json())
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
        print('polling health for instance', instance_id)
        r = await c.get(f"/instances/{instance_id}/health")
        print('health response', r.json())
        r.raise_for_status()
        return r.json()["status"]  # provisioning/active/inactive/updating/deleting/error/unknown

# ---------- Knowledge API ----------
async def kb_ingest(*, instance_id: str, url: str, data_type: str, lang_hint: str) -> str:
    """Return execution_id"""
    payload = {
        "instance_id": instance_id,
        "entity": [url],
        "data_type": data_type,
        "lang_hint": lang_hint,
    }
    async with _client(settings.KB_API_BASE_URL, settings.KB_API_TOKEN) as c:
        r = await c.post("/kb/ingest", json=payload)
        r.raise_for_status()
        data = r.json()
        # {"ok":true,"kb_name":"...","execution_id":"<uuid>"}
        return data["execution_id"]  # per KB API doc

async def kb_status(*, instance_id: str, execution_id: str) -> Tuple[str, list[str] | None]:
    """Return (status, entity_ids|None); status in {'in_progress','done'}"""
    async with _client(settings.KB_API_BASE_URL, settings.KB_API_TOKEN) as c:
        r = await c.get("/kb/status", params={"instance_id": instance_id, "execution_id": execution_id})
        if r.status_code == 404:
            # Unknown execution_id for instance — treat as failed
            return ("unknown", None)
        r.raise_for_status()
        data = r.json()
        return (data.get("status", "unknown"), data.get("entity_ids"))

async def kb_delete_by_ids(*, instance_id: str, entity_ids: list[str]) -> int:
    payload = {"instance_id": instance_id, "entity_ids": entity_ids}
    async with _client(settings.KB_API_BASE_URL, settings.KB_API_TOKEN) as c:
        r = await c.post("/kb/delete", json=payload)
        r.raise_for_status()
        return int(r.json().get("deleted_count", 0))