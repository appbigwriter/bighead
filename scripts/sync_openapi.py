"""Build the canonical OpenAPI document from the handoff matrix and FastAPI.

The endpoint matrix is the product contract for T01-T56.  FastAPI is used as
the authoritative schema source for endpoints that already have an
implementation; matrix-only endpoints remain explicit, typed placeholders
until their router lands.  Running this script updates both published copies.
"""

from __future__ import annotations

import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "frontend-backend" / "ENDPOINT-MATRIX.md"
CANONICAL = ROOT / "packages" / "contracts" / "openapi" / "openapi.yaml"
SNAPSHOT = ROOT / "docs" / "frontend-backend" / "openapi-snapshot.yaml"

_ROW = re.compile(
    r"^\| (T\d{2}) \|.*?\| `([^`]+)` \| `([^`]+)` \| (.*?) \| (.*?) \| "
    r"`([^`]+)` \| (.*?) \| (.*?) \| (.*?) \|$"
)
_SCHEMA = re.compile(r"`?([A-Z][A-Za-z0-9]+(?:Request|Response))\b")
_PATH_PARAMETER = re.compile(r"\{([^}]+)\}")


def _configure_test_environment() -> None:
    defaults = {
        "APP_ENV": "contract",
        "APP_URL": "http://localhost:3000",
        "API_URL": "http://localhost:8000",
        "CORS_ORIGINS": "http://localhost:3000",
        "DATABASE_URL": "postgresql://postgres:postgres@localhost:55322/postgres",
        "DIRECT_DATABASE_URL": "postgresql://postgres:postgres@localhost:55322/postgres",
        "SUPABASE_URL": "http://localhost:55321",
        "SUPABASE_PUBLISHABLE_KEY": "contract-publishable-key",
        "SUPABASE_SECRET_KEY": "contract-secret-key",
        "STORAGE_BUCKET": "artifacts",
        "REDIS_URL": "redis://localhost:6379/0",
        "QUEUE_NAME": "bighead:jobs",
        "JOB_LEASE_SECONDS": "300",
        "OTEL_SERVICE_NAME": "bighead-api-contract",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
        "ENCRYPTION_KEY": "12345678901234567890123456789012",
        "WEBHOOK_SIGNING_SECRET": "contract-webhook-secret",
        "PORTAL_TOKEN_PEPPER": "contract-portal-pepper",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


def _matrix_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        match = _ROW.match(line)
        if not match:
            continue
        screen, path, methods, request, response, statuses, role, event, error = match.groups()
        rows.append(
            {
                "screen": screen,
                "path": path,
                "methods": methods,
                "request": request,
                "response": response,
                "statuses": statuses,
                "role": role,
                "event": event,
                "error": error,
            }
        )
    if {row["screen"] for row in rows} != {f"T{index:02d}" for index in range(1, 57)}:
        raise RuntimeError("Endpoint matrix must contain exactly T01-T56")
    return rows


def _schema_name(text: str, fallback: str) -> str:
    match = _SCHEMA.search(text)
    return match.group(1) if match else fallback


def _success_status(method: str, statuses: list[str]) -> str:
    successes = [status for status in statuses if status.startswith("2")]
    preferred = {"post": ["201", "202", "200"], "patch": ["200", "202"]}.get(method, ["200", "206"])
    return next((status for status in preferred if status in successes), successes[0])


def _tag(path: str) -> str:
    segment = path.removeprefix("/v1/").split("/", 1)[0]
    return {
        "auth": "access",
        "onboarding": "access",
        "preferences": "access",
        "memberships": "administration",
        "audit": "administration",
    }.get(segment, segment)


def _matrix_operation(row: dict[str, str], method: str, schemas: dict[str, Any]) -> dict[str, Any]:
    statuses = [item.strip() for item in row["statuses"].split(",")]
    response_schema = _schema_name(row["response"], f"{row['screen']}Response")
    schemas.setdefault(
        response_schema,
        {"type": "object", "additionalProperties": True, "title": response_schema},
    )
    operation: dict[str, Any] = {
        "tags": [_tag(row["path"])],
        "operationId": f"{row['screen'].lower()}{method.title()}",
        "summary": f"{row['screen']} - {row['path']}",
        "x-bighead-screen": row["screen"],
        "x-bighead-role": row["role"],
        "x-bighead-cache-event": row["event"],
        "x-bighead-critical-error": row["error"],
        "responses": {},
    }
    for parameter in _PATH_PARAMETER.findall(row["path"]):
        operation.setdefault("parameters", []).append(
            {
                "name": parameter,
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            }
        )
    if method in {"post", "patch", "put"}:
        request_schema = _schema_name(row["request"], f"{row['screen']}Request")
        schemas.setdefault(
            request_schema,
            {"type": "object", "additionalProperties": True, "title": request_schema},
        )
        operation["requestBody"] = {
            "required": True,
            "content": {
                "application/json": {"schema": {"$ref": f"#/components/schemas/{request_schema}"}}
            },
        }
    success = _success_status(method, statuses)
    for status in statuses:
        if status == success:
            operation["responses"][status] = {
                "description": f"{row['screen']} successful response",
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{response_schema}"}
                    }
                },
            }
        else:
            operation["responses"][status] = {"$ref": "#/components/responses/Problem"}
    if row["role"] not in {"publico", "autenticado sem membership", "guest"}:
        operation["security"] = [{"HTTPBearer": []}]
    return operation


def build_document() -> dict[str, Any]:
    _configure_test_environment()
    api_src = str(ROOT / "apps" / "api" / "src")
    if api_src not in sys.path:
        sys.path.insert(0, api_src)
    from bighead_api.main import create_app

    runtime = create_app().openapi()
    schemas: dict[str, Any] = deepcopy(runtime.get("components", {}).get("schemas", {}))
    schemas.setdefault(
        "ProblemDetails",
        {
            "type": "object",
            "required": ["type", "title", "status"],
            "properties": {
                "type": {"type": "string", "format": "uri-reference"},
                "title": {"type": "string"},
                "status": {"type": "integer"},
                "detail": {"type": "string"},
                "traceId": {"type": "string"},
            },
        },
    )
    paths: dict[str, Any] = {}
    for row in _matrix_rows():
        path_item = paths.setdefault(row["path"], {})
        for method in row["methods"].lower().split("/"):
            operation = _matrix_operation(row, method, schemas)
            previous = path_item.get(method)
            if previous is not None:
                screens = list(previous.get("x-bighead-screens", [previous["x-bighead-screen"]]))
                screens.append(row["screen"])
                operation["x-bighead-screens"] = screens
                operation["x-bighead-screen"] = screens[0]
                for status, response in previous["responses"].items():
                    operation["responses"].setdefault(status, response)
            path_item[method] = operation

    # Runtime models are more precise than matrix placeholders.  Preserve the
    # matrix evidence extensions and its documented error statuses.
    for path, runtime_item in runtime.get("paths", {}).items():
        canonical_item = paths.setdefault(path, {})
        for method, runtime_operation in runtime_item.items():
            if method.startswith("x-") or not isinstance(runtime_operation, dict):
                canonical_item[method] = deepcopy(runtime_operation)
                continue
            matrix_operation = canonical_item.get(method, {})
            merged = deepcopy(runtime_operation)
            for key, value in matrix_operation.items():
                if key.startswith("x-bighead-"):
                    merged[key] = value
            for status, response in matrix_operation.get("responses", {}).items():
                merged.setdefault("responses", {}).setdefault(status, response)
            canonical_item[method] = merged

    security_schemes = deepcopy(runtime.get("components", {}).get("securitySchemes", {}))
    security_schemes.setdefault(
        "HTTPBearer", {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    )
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "BigHead API",
            "version": "0.3.0",
            "description": "Contrato canônico Sprint 3: matriz T01-T56 e implementação FastAPI.",
        },
        "servers": [{"url": "http://localhost:8000", "description": "Local"}],
        "paths": paths,
        "components": {
            "securitySchemes": security_schemes,
            "responses": {
                "Problem": {
                    "description": "Erro no formato RFC 9457",
                    "content": {
                        "application/problem+json": {
                            "schema": {"$ref": "#/components/schemas/ProblemDetails"}
                        }
                    },
                }
            },
            "schemas": schemas,
        },
    }


def render_document(document: dict[str, Any]) -> str:
    return yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=100)


def main() -> None:
    document = build_document()
    rendered = render_document(document)
    if "--check" in sys.argv:
        stale = [
            str(path.relative_to(ROOT))
            for path in (CANONICAL, SNAPSHOT)
            if not path.exists() or path.read_text(encoding="utf-8") != rendered
        ]
        if stale:
            raise SystemExit(
                "OpenAPI drift in "
                + ", ".join(stale)
                + "; run `uv run --project apps/api python scripts/sync_openapi.py`"
            )
        print(f"OpenAPI is current: {len(document['paths'])} paths")
        return
    CANONICAL.write_text(rendered, encoding="utf-8", newline="\n")
    SNAPSHOT.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"OpenAPI synchronized: {len(document['paths'])} paths")


if __name__ == "__main__":
    main()
