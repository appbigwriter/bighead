from __future__ import annotations

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
