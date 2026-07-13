from bighead_api.governance.models import WorkflowValidateRequest
from bighead_api.governance.service import (
    _sensitive_paths,
    _validate_payload,
    validate_workflow,
)


def test_workflow_validation_accepts_dag_and_rejects_cycles_and_dangling_edges() -> None:
    dag = validate_workflow(
        WorkflowValidateRequest(
            version=1,
            nodes=[{"id": "start"}, {"id": "end"}],
            edges=[{"source": "start", "target": "end"}],
        )
    )
    cycle = validate_workflow(
        WorkflowValidateRequest(
            version=1,
            nodes=[{"id": "a"}, {"id": "b"}],
            edges=[{"source": "a", "target": "b"}, {"source": "b", "target": "a"}],
        )
    )
    dangling = validate_workflow(
        WorkflowValidateRequest(
            version=1,
            nodes=[{"id": "start"}],
            edges=[{"source": "start", "target": "missing"}],
        )
    )

    assert dag.valid is True
    assert cycle.valid is False and cycle.cycles
    assert dangling.valid is False and dangling.schema_errors


def test_skill_payload_validation_checks_required_types_and_nested_redactions() -> None:
    schema = {
        "required": ["query", "limit"],
        "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
    }
    findings = _validate_payload({"query": 42, "limit": True}, schema)

    assert findings == ["Invalid type for field: query", "Invalid type for field: limit"]
    assert _sensitive_paths({"auth": {"accessToken": "unsafe"}, "password": "unsafe"}) == [
        "auth.accessToken",
        "password",
    ]
