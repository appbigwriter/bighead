import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

import httpx
from fastapi import HTTPException, Request, status

from bighead_api.config import Settings
from bighead_api.identity.models import AuthUser, Session


class AuthProvider(Protocol):
    async def verify(self, token: str) -> AuthUser: ...

    async def login(self, email: str, password: str) -> tuple[AuthUser, Session]: ...

    async def send_magic_link(self, email: str) -> AuthUser: ...

    async def request_recovery(self, email: str) -> None: ...

    async def create_invited_user(self, email: str, password: str) -> AuthUser: ...

    async def revoke(self, token: str, scope: str) -> None: ...

    async def signup(self, email: str, password: str) -> tuple[AuthUser, Session | None]: ...

    async def exchange_code(self, code: str, verifier: str) -> tuple[AuthUser, Session]: ...

    async def update_password(self, token: str, new_password: str) -> None: ...


@dataclass(frozen=True)
class SupabaseAuthProvider:
    base_url: str
    publishable_key: str
    secret_key: str

    @classmethod
    def from_settings(cls, settings: Settings) -> SupabaseAuthProvider:
        return cls(
            base_url=str(settings.supabase_url).rstrip("/"),
            publishable_key=settings.supabase_publishable_key.get_secret_value(),
            secret_key=settings.supabase_secret_key.get_secret_value(),
        )

    async def verify(self, token: str) -> AuthUser:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{self.base_url}/auth/v1/user",
                headers={"apikey": self.publishable_key, "Authorization": f"Bearer {token}"},
            )
        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        payload = response.json()
        claims = _verified_claims(token)
        return AuthUser(
            id=UUID(payload["id"]),
            email=payload["email"],
            session_id=_optional_uuid(claims.get("session_id")),
            expires_at=_expiry(claims.get("exp")),
        )

    async def login(self, email: str, password: str) -> tuple[AuthUser, Session]:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{self.base_url}/auth/v1/token",
                params={"grant_type": "password"},
                headers={"apikey": self.publishable_key},
                json={"email": email, "password": password},
            )
        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return await self._verified_session(response.json())

    async def signup(self, email: str, password: str) -> tuple[AuthUser, Session | None]:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{self.base_url}/auth/v1/signup",
                headers={"apikey": self.publishable_key},
                json={"email": email, "password": password},
            )
        if response.status_code not in {200, 201}:
            raise HTTPException(status_code=409, detail="Unable to create account")
        payload = response.json()
        if payload.get("access_token"):
            return await self._verified_session(payload)
        user_payload = payload.get("user") or payload
        return AuthUser(id=UUID(user_payload["id"]), email=user_payload["email"]), None

    async def exchange_code(self, code: str, verifier: str) -> tuple[AuthUser, Session]:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{self.base_url}/auth/v1/token",
                params={"grant_type": "pkce"},
                headers={"apikey": self.publishable_key},
                json={"auth_code": code, "code_verifier": verifier},
            )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid or expired auth callback")
        return await self._verified_session(response.json())

    async def update_password(self, token: str, new_password: str) -> None:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.put(
                f"{self.base_url}/auth/v1/user",
                headers={"apikey": self.publishable_key, "Authorization": f"Bearer {token}"},
                json={"password": new_password},
            )
        if response.status_code != 200:
            raise HTTPException(status_code=409, detail="Password could not be updated")

    async def _verified_session(self, payload: dict[str, Any]) -> tuple[AuthUser, Session]:
        token = str(payload["access_token"])
        user = await self.verify(token)
        return user, Session(
            id=str(user.session_id or "current"),
            access_token=token,
            refresh_token=payload.get("refresh_token"),
            expires_at=user.expires_at,
        )

    async def send_magic_link(self, email: str) -> AuthUser:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{self.base_url}/auth/v1/otp",
                headers={"apikey": self.publishable_key},
                json={"email": email, "create_user": False},
            )
        if response.status_code >= 400 and response.status_code != 429:
            # Keep the public response non-enumerating.
            return AuthUser(id=UUID(int=0), email=email)
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Try again later")
        return AuthUser(id=UUID(int=0), email=email)

    async def request_recovery(self, email: str) -> None:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{self.base_url}/auth/v1/recover",
                headers={"apikey": self.publishable_key},
                json={"email": email},
            )
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Try again later")

    async def create_invited_user(self, email: str, password: str) -> AuthUser:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{self.base_url}/auth/v1/admin/users",
                headers={
                    "apikey": self.secret_key,
                    "Authorization": f"Bearer {self.secret_key}",
                },
                json={"email": email, "password": password, "email_confirm": True},
            )
        if response.status_code not in {200, 201}:
            raise HTTPException(status_code=409, detail="Unable to provision invited user")
        payload = response.json()
        return AuthUser(id=UUID(payload["id"]), email=payload["email"])

    async def revoke(self, token: str, scope: str) -> None:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{self.base_url}/auth/v1/logout",
                params={"scope": scope},
                headers={"apikey": self.publishable_key, "Authorization": f"Bearer {token}"},
            )
        if response.status_code not in {200, 204}:
            raise HTTPException(status_code=409, detail="Session could not be revoked")


def bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Bearer token required")
    return token


def optional_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    return token if scheme.lower() == "bearer" and token else None


def _verified_claims(token: str) -> dict[str, Any]:
    # The token has already been verified by /auth/v1/user. Decoding only extracts
    # its trusted session and expiry claims; no authorization uses metadata claims.
    try:
        segment = token.split(".")[1]
        raw = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except IndexError, ValueError, json.JSONDecodeError:
        return {}


def _optional_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


def _expiry(value: object) -> datetime | None:
    return datetime.fromtimestamp(value, tz=UTC) if isinstance(value, int | float) else None
