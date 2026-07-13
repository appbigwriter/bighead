from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.sync_openapi import (  # noqa: E402
    CANONICAL,
    SNAPSHOT,
    _matrix_rows,
    build_document,
)


def _load(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _operations(document: dict[str, Any]) -> list[dict[str, Any]]:
    methods = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
    return [
        operation
        for path_item in document["paths"].values()
        for method, operation in path_item.items()
        if method in methods
    ]


def test_canonical_document_and_handoff_snapshot_are_in_sync() -> None:
    canonical = _load(CANONICAL)

    assert canonical == _load(SNAPSHOT)
    assert canonical == build_document(), (
        "OpenAPI drift detected; run `uv run --project apps/api python scripts/sync_openapi.py`"
    )


def test_canonical_document_covers_every_matrix_operation_and_screen() -> None:
    document = _load(CANONICAL)
    covered_screens: set[str] = set()

    for row in _matrix_rows():
        path_item = document["paths"][row["path"]]
        for method in row["methods"].lower().split("/"):
            assert method in path_item, f"Missing {method.upper()} {row['path']} ({row['screen']})"
            operation = path_item[method]
            covered_screens.update(
                operation.get("x-bighead-screens", [operation["x-bighead-screen"]])
            )

    assert covered_screens == {f"T{index:02d}" for index in range(1, 57)}


def test_operation_ids_are_unique_and_all_local_references_resolve() -> None:
    document = _load(CANONICAL)
    operation_ids = [operation["operationId"] for operation in _operations(document)]
    assert len(operation_ids) == len(set(operation_ids))

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str) and reference.startswith("#/"):
                target: Any = document
                for segment in reference.removeprefix("#/").split("/"):
                    target = target[segment.replace("~1", "/").replace("~0", "~")]
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(document)


def test_every_fastapi_operation_is_published_with_its_precise_schema() -> None:
    # build_document overlays FastAPI's request/response models onto matrix
    # placeholders.  Rebuilding in the first test makes any router drift fail;
    # here we make the implementation-boundary guarantee explicit.
    document = _load(CANONICAL)
    expected = build_document()

    for path, path_item in expected["paths"].items():
        for method, operation in path_item.items():
            if not isinstance(operation, dict) or "operationId" not in operation:
                continue
            published = document["paths"][path][method]
            assert published.get("requestBody") == operation.get("requestBody")
            for status, response in operation["responses"].items():
                if status.startswith("2"):
                    assert published["responses"][status] == response


def test_implemented_path_parameter_names_match_the_handoff_contract() -> None:
    from bighead_api.main import create_app

    matrix_paths = {row["path"] for row in _matrix_rows()}
    matrix_by_shape = {re.sub(r"\{[^}]+\}", "{}", path): path for path in matrix_paths}
    for runtime_path in create_app().openapi()["paths"]:
        shape = re.sub(r"\{[^}]+\}", "{}", runtime_path)
        expected = matrix_by_shape.get(shape)
        if expected is not None:
            assert runtime_path == expected, (
                f"FastAPI publishes {runtime_path}, but the handoff contract requires {expected}"
            )


def test_security_boundary_headers_are_required_in_the_published_contract() -> None:
    document = _load(CANONICAL)
    boundary_headers = {"x-organization-id", "Idempotency-Key"}
    observed: set[str] = set()

    for operation in _operations(document):
        for parameter in operation.get("parameters", []):
            name = parameter.get("name")
            if parameter.get("in") == "header" and name in boundary_headers:
                observed.add(name)
                assert parameter.get("required") is True, (
                    f"{name} must be required for {operation['operationId']}"
                )

    assert observed == boundary_headers


def test_every_matrix_operation_exists_in_fastapi_runtime() -> None:
    from bighead_api.main import create_app

    runtime_paths = create_app().openapi()["paths"]
    for row in _matrix_rows():
        for method in row["methods"].lower().split("/"):
            assert method in runtime_paths.get(row["path"], {}), (
                f"Matrix operation missing from FastAPI: {method.upper()} {row['path']}"
            )


def test_every_tenant_scoped_operation_declares_bearer_security() -> None:
    document = _load(CANONICAL)
    tenant_operations = 0
    for operation in _operations(document):
        parameters = operation.get("parameters", [])
        if any(
            parameter.get("in") == "header" and parameter.get("name") == "x-organization-id"
            for parameter in parameters
        ):
            tenant_operations += 1
            assert {"HTTPBearer": []} in operation.get("security", []), operation["operationId"]
    assert tenant_operations >= 56
