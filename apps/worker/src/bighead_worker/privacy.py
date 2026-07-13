import json
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import httpx


@dataclass(frozen=True)
class PrivacyRequest:
    id: UUID
    organization_id: UUID
    subject_user_id: UUID | None
    request_type: str
    attempts: int


class PrivacyStore(Protocol):
    async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[PrivacyRequest]: ...
    async def process(self, request: PrivacyRequest, worker: str) -> dict[str, Any]: ...
    async def complete(self, request_id: UUID, worker: str, evidence: dict[str, Any]) -> bool: ...
    async def fail(self, request_id: UUID, worker: str, error: str, max_attempts: int) -> bool: ...


@dataclass
class SupabasePrivacyStore:
    base_url: str
    secret_key: str
    export_bucket: str = "artifacts"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "apikey": self.secret_key,
            "Content-Type": "application/json",
        }

    async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[PrivacyRequest]:
        rows = await self._rpc(
            "claim_privacy_requests",
            {"p_worker": worker, "p_limit": limit, "p_lease_seconds": lease_seconds},
        )
        return [
            PrivacyRequest(
                id=UUID(row["id"]),
                organization_id=UUID(row["organization_id"]),
                subject_user_id=(UUID(row["subject_user_id"]) if row["subject_user_id"] else None),
                request_type=row["request_type"],
                attempts=int(row["attempts"]),
            )
            for row in rows
        ]

    async def process(self, request: PrivacyRequest, worker: str) -> dict[str, Any]:
        if request.request_type == "export":
            payload = await self._rpc(
                "build_privacy_export", {"p_id": str(request.id), "p_worker": worker}
            )
            path = f"{request.organization_id}/privacy-exports/{request.id}.json"
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/storage/v1/object/{self.export_bucket}/{path}",
                    headers={**self._headers(), "x-upsert": "true"},
                    content=json.dumps(payload, sort_keys=True, default=str).encode(),
                )
            response.raise_for_status()
            return {"exportPath": path, "recordCountEvidence": True}
        return dict(
            await self._rpc(
                "execute_privacy_mutation",
                {"p_id": str(request.id), "p_worker": worker},
            )
        )

    async def complete(self, request_id: UUID, worker: str, evidence: dict[str, Any]) -> bool:
        return bool(
            await self._rpc(
                "complete_privacy_request",
                {"p_id": str(request_id), "p_worker": worker, "p_evidence": evidence},
            )
        )

    async def fail(self, request_id: UUID, worker: str, error: str, max_attempts: int) -> bool:
        return bool(
            await self._rpc(
                "fail_privacy_request",
                {
                    "p_id": str(request_id),
                    "p_worker": worker,
                    "p_error": error,
                    "p_max_attempts": max_attempts,
                },
            )
        )

    async def _rpc(self, function: str, payload: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/rest/v1/rpc/{function}",
                headers=self._headers(),
                json=payload,
            )
        response.raise_for_status()
        return response.json()


async def process_privacy_requests(
    store: PrivacyStore,
    *,
    worker: str,
    limit: int = 10,
    lease_seconds: int = 60,
    max_attempts: int = 5,
) -> tuple[int, int]:
    completed = failed = 0
    for request in await store.claim(worker, limit, lease_seconds):
        try:
            evidence = await store.process(request, worker)
            if not await store.complete(request.id, worker, evidence):
                raise RuntimeError("privacy request lease was lost before completion")
            completed += 1
        except Exception as exc:
            await store.fail(request.id, worker, f"{type(exc).__name__}: {exc}", max_attempts)
            failed += 1
    return completed, failed
