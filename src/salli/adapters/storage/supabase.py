"""
SupabaseStorageAdapter — production storage via Supabase Storage buckets.

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in settings.
Uses the `statements` bucket (create it in Supabase dashboard with private access).

Bucket path convention: {user_id}/{key}
"""

from __future__ import annotations

import httpx

from salli.application.ports import StoragePort

_BUCKET = "statements"


class SupabaseStorageAdapter(StoragePort):
    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        self._base = supabase_url.rstrip("/") + f"/storage/v1/object/{_BUCKET}"
        self._headers = {
            "Authorization": f"Bearer {service_role_key}",
            "apikey": service_role_key,
        }

    async def upload(self, user_id: str, key: str, data: bytes) -> str:
        path = f"{user_id}/{key}"
        url = f"{self._base}/{path}"
        async with httpx.AsyncClient() as client:
            r = await client.post(
                url,
                content=data,
                headers={**self._headers, "Content-Type": "application/octet-stream"},
            )
            r.raise_for_status()
        return path

    async def download(self, key: str) -> bytes:
        url = f"{self._base}/{key}"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=self._headers)
            r.raise_for_status()
            return r.content
