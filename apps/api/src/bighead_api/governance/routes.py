from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request

from bighead_api.governance.models import (
    AgentPatchRequest,
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalPolicyPatchRequest,
    ApprovalPolicyResponse,
    Page,
    PlaybookInstantiateRequest,
    PlaybookInstantiateResponse,
    PortalDecisionRequest,
    SkillValidateRequest,
    SkillValidateResponse,
    WorkflowValidateRequest,
    WorkflowValidateResponse,
)
from bighead_api.governance.service import GovernanceRepository
from bighead_api.identity.dependencies import TenantContext, require_roles, tenant_context
from bighead_api.identity.models import MemberRole

router = APIRouter(prefix="/v1")
AdminContext = Annotated[TenantContext, require_roles(MemberRole.OWNER, MemberRole.ADMIN)]
ManagerContext = Annotated[
    TenantContext, require_roles(MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MANAGER)
]
ReviewerContext = Annotated[
    TenantContext, require_roles(MemberRole.OWNER, MemberRole.ADMIN, MemberRole.REVIEWER)
]


def repository(request: Request) -> GovernanceRepository:
    return cast(GovernanceRepository, request.app.state.governance_repository)


@router.get("/approvals", response_model=Page, tags=["approvals"])
async def approvals(
    context: ReviewerContext, repo: Annotated[GovernanceRepository, Depends(repository)]
) -> Page:
    return await repo.list_approvals(_user(context), context.organization_id)


@router.post(
    "/approvals/{approvalId}/decision",
    response_model=ApprovalDecisionResponse,
    tags=["approvals"],
)
async def decide(
    approval_id: Annotated[UUID, Path(alias="approvalId")],
    payload: ApprovalDecisionRequest,
    context: ReviewerContext,
    repo: Annotated[GovernanceRepository, Depends(repository)],
) -> ApprovalDecisionResponse:
    return await repo.decide(_user(context), context.organization_id, approval_id, payload)


@router.get("/approvals/{approvalId}/scorecard", tags=["approvals"])
async def scorecard(
    approval_id: Annotated[UUID, Path(alias="approvalId")],
    context: ReviewerContext,
    repo: Annotated[GovernanceRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.scorecard(_user(context), context.organization_id, approval_id)


@router.get("/policies/approvals", response_model=ApprovalPolicyResponse, tags=["approvals"])
async def get_policy(
    context: ManagerContext, repo: Annotated[GovernanceRepository, Depends(repository)]
) -> ApprovalPolicyResponse:
    return await repo.get_policy(_user(context), context.organization_id)


@router.patch("/policies/approvals", response_model=ApprovalPolicyResponse, tags=["approvals"])
async def patch_policy(
    payload: ApprovalPolicyPatchRequest,
    context: AdminContext,
    repo: Annotated[GovernanceRepository, Depends(repository)],
) -> ApprovalPolicyResponse:
    return await repo.patch_policy(_user(context), context.organization_id, payload)


@router.get("/portal/items/{token}", tags=["portal"])
async def portal_item(
    token: str, repo: Annotated[GovernanceRepository, Depends(repository)]
) -> dict[str, Any]:
    return await repo.portal_item(token)


@router.post(
    "/portal/items/{token}/decision",
    response_model=ApprovalDecisionResponse,
    tags=["portal"],
)
async def portal_decision(
    token: str,
    payload: PortalDecisionRequest,
    repo: Annotated[GovernanceRepository, Depends(repository)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ApprovalDecisionResponse:
    if not idempotency_key or len(idempotency_key) > 200:
        raise HTTPException(status_code=400, detail="Idempotency-Key header required")
    return await repo.portal_decide(token, idempotency_key, payload)


@router.get("/agents", response_model=Page, tags=["agents"])
async def agents(
    context: AdminContext, repo: Annotated[GovernanceRepository, Depends(repository)]
) -> Page:
    return await repo.list_agents(_user(context), context.organization_id)


@router.get("/agents/{agentId}", tags=["agents"])
async def agent_detail(
    agent_id: Annotated[UUID, Path(alias="agentId")],
    context: AdminContext,
    repo: Annotated[GovernanceRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.agent_detail(_user(context), context.organization_id, agent_id)


@router.patch("/agents/{agentId}", tags=["agents"])
async def patch_agent(
    agent_id: Annotated[UUID, Path(alias="agentId")],
    payload: AgentPatchRequest,
    context: AdminContext,
    repo: Annotated[GovernanceRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.patch_agent(_user(context), context.organization_id, agent_id, payload)


@router.get("/skills", response_model=Page, tags=["skills"])
async def skills(
    context: AdminContext, repo: Annotated[GovernanceRepository, Depends(repository)]
) -> Page:
    return await repo.list_skills(_user(context), context.organization_id)


@router.post("/skills/{skillId}/validate", response_model=SkillValidateResponse, tags=["skills"])
async def validate_skill(
    skill_id: Annotated[UUID, Path(alias="skillId")],
    payload: SkillValidateRequest,
    context: AdminContext,
    repo: Annotated[GovernanceRepository, Depends(repository)],
) -> SkillValidateResponse:
    return await repo.validate_skill(_user(context), context.organization_id, skill_id, payload)


@router.get("/models", tags=["models"])
async def models(
    context: AdminContext, repo: Annotated[GovernanceRepository, Depends(repository)]
) -> dict[str, Any]:
    return await repo.list_models(_user(context), context.organization_id)


@router.get("/prompts", response_model=Page, tags=["prompts"])
async def prompts(
    context: AdminContext, repo: Annotated[GovernanceRepository, Depends(repository)]
) -> Page:
    return await repo.list_prompts(_user(context), context.organization_id)


@router.get("/workflows", response_model=Page, tags=["workflows"])
async def workflows(
    context: ManagerContext, repo: Annotated[GovernanceRepository, Depends(repository)]
) -> Page:
    return await repo.list_workflows(_user(context), context.organization_id)


@router.post(
    "/workflows/{workflowId}/validate",
    response_model=WorkflowValidateResponse,
    tags=["workflows"],
)
async def validate_workflow_endpoint(
    workflow_id: Annotated[UUID, Path(alias="workflowId")],
    payload: WorkflowValidateRequest,
    context: AdminContext,
    repo: Annotated[GovernanceRepository, Depends(repository)],
) -> WorkflowValidateResponse:
    return await repo.validate_workflow(
        _user(context), context.organization_id, workflow_id, payload
    )


@router.get("/workflows/{workflowId}/versions", tags=["workflows"])
async def workflow_versions(
    workflow_id: Annotated[UUID, Path(alias="workflowId")],
    context: AdminContext,
    repo: Annotated[GovernanceRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.workflow_versions(_user(context), context.organization_id, workflow_id)


@router.post(
    "/playbooks/{playbookId}/instantiate",
    response_model=PlaybookInstantiateResponse,
    status_code=201,
    tags=["playbooks"],
)
async def instantiate(
    playbook_id: Annotated[UUID, Path(alias="playbookId")],
    payload: PlaybookInstantiateRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[GovernanceRepository, Depends(repository)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PlaybookInstantiateResponse:
    if not idempotency_key or len(idempotency_key) > 200:
        raise HTTPException(status_code=400, detail="Idempotency-Key header required")
    return await repo.instantiate(
        _user(context), context.organization_id, playbook_id, idempotency_key, payload
    )


def _user(context: TenantContext) -> UUID:
    if context.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    return context.user.id
