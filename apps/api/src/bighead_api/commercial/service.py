# ruff: noqa: E501
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter, ValidationError

from bighead_api.commercial.models import (
    Campaign,
    ContentAsset,
    ContentAssetCreateRequest,
    CrmImportRequest,
    CrmImportResumeRequest,
    KnowledgeDocument,
    KnowledgeUploadRequest,
    Lead,
    MemoryItem,
    Opportunity,
    OpportunityStageRequest,
    PublicationRetryRequest,
    SemanticSearchRequest,
)
from bighead_api.identity.models import MemberRole
from bighead_api.identity.repository import Database


class CommercialRepository(Protocol):
    async def documents(
        self,
        user_id: UUID,
        organization_id: UUID,
        status: str | None,
        classification: str | None,
        limit: int,
    ) -> dict[str, Any]: ...
    async def upload_document(
        self,
        user_id: UUID,
        organization_id: UUID,
        payload: KnowledgeUploadRequest,
        idempotency_key: str,
    ) -> dict[str, Any]: ...
    async def memory_items(
        self, user_id: UUID, organization_id: UUID, kind: str | None, status: str | None, limit: int
    ) -> dict[str, Any]: ...
    async def semantic_search(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        payload: SemanticSearchRequest,
    ) -> dict[str, Any]: ...
    async def crm_import(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        payload: CrmImportRequest,
        idempotency_key: str,
    ) -> dict[str, Any]: ...
    async def _process_crm_resume_row(
        self,
        conn: Any,
        user_id: UUID,
        organization_id: UUID,
        source: str,
        consent_basis: str,
        row_number: int,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        name = str(item.get("accountName") or item.get("name") or "").strip()
        if not name:
            return {"row": row_number, "action": "rejected", "reason": "accountName required"}
        consent_status = str(item.get("consentStatus") or "").lower()
        if consent_status not in {"unknown", "granted", "denied", "revoked"}:
            return {
                "row": row_number,
                "action": "rejected",
                "reason": "valid consentStatus required",
            }
        if item.get("icpScore") is not None:
            score_factors = item.get("scoreFactors")
            score_version = str(item.get("scoreAlgorithmVersion") or "").strip()
            if not isinstance(score_factors, dict) or not score_factors or not score_version:
                return {
                    "row": row_number,
                    "action": "rejected",
                    "reason": "scored lead requires scoreFactors and scoreAlgorithmVersion",
                }
        raw_email = str(item.get("email") or "").strip().lower()
        email: str | None = None
        contact_name: str | None = None
        if raw_email:
            try:
                email = str(TypeAdapter(EmailStr).validate_python(raw_email))
            except ValidationError:
                return {"row": row_number, "action": "rejected", "reason": "invalid email"}
            contact_name = str(item.get("contactName") or item.get("name") or "").strip()
            if not contact_name:
                return {
                    "row": row_number,
                    "action": "rejected",
                    "reason": "contactName required",
                }
        owner_id = user_id
        if item.get("ownerId"):
            try:
                requested_owner = UUID(str(item["ownerId"]))
            except ValueError:
                return {"row": row_number, "action": "rejected", "reason": "invalid ownerId"}
            valid_owner = await conn.fetchval(
                """select exists(select 1 from public.organization_members
                    where organization_id=$1 and user_id=$2 and status='active')""",
                organization_id,
                requested_owner,
            )
            if not valid_owner:
                return {"row": row_number, "action": "rejected", "reason": "owner not active"}
            owner_id = requested_owner
        domain = str(item.get("domain") or "").lower() or None
        account = None
        if domain is not None:
            account = await conn.fetchrow(
                "select id from public.crm_accounts where organization_id=$1 and domain=$2",
                organization_id,
                domain,
            )
        if account:
            account_id = account["id"]
            report: dict[str, Any] = {
                "row": row_number,
                "action": "merge_preview",
                "accountId": str(account_id),
            }
        else:
            account_id = await conn.fetchval(
                """insert into public.crm_accounts(
                    organization_id,name,domain,owner_user_id,metadata
                ) values($1,$2,$3,$4,$5::jsonb) returning id""",
                organization_id,
                name,
                domain,
                user_id,
                json.dumps({"source": source}),
            )
            report = {"row": row_number, "action": "create", "accountId": str(account_id)}
        contact_id: UUID | None = None
        if email and contact_name:
            contact_id = await conn.fetchval(
                """insert into public.crm_contacts(
                    organization_id,account_id,name,email,phone,consent_status,legal_basis,metadata
                ) values($1,$2,$3,$4,$5,$6,$7,$8::jsonb)
                on conflict (organization_id,email) do update set
                  account_id=excluded.account_id,name=excluded.name,phone=excluded.phone,
                  consent_status=excluded.consent_status,legal_basis=excluded.legal_basis,
                  metadata=excluded.metadata returning id""",
                organization_id,
                account_id,
                contact_name,
                email,
                item.get("phone"),
                consent_status,
                str(item.get("legalBasis") or consent_basis),
                json.dumps({"source": source}),
            )
            report["contactId"] = str(contact_id)
        if bool(item.get("createLead", True)) and consent_status == "granted":
            lead_id = await conn.fetchval(
                """insert into public.leads(
                    organization_id,account_id,contact_id,owner_user_id,status,source,
                    icp_score,score_factors,score_algorithm_version,next_action
                ) values($1,$2,$3,$4,'new',$5,$6,$7::jsonb,$8,$9) returning id""",
                organization_id,
                account_id,
                contact_id,
                owner_id,
                source,
                item.get("icpScore"),
                json.dumps(item.get("scoreFactors") or {}),
                item.get("scoreAlgorithmVersion"),
                item.get("nextAction"),
            )
            report["leadId"] = str(lead_id)
        return report

    async def resume_crm_import(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        import_id: UUID,
        payload: CrmImportResumeRequest,
    ) -> dict[str, Any]: ...
    async def merge_crm_accounts(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        source_id: UUID,
        target_id: UUID,
        reason: str,
    ) -> dict[str, Any]: ...
    async def leads(
        self,
        user_id: UUID,
        organization_id: UUID,
        status: str | None,
        owner_id: UUID | None,
        limit: int,
    ) -> dict[str, Any]: ...
    async def lead(self, user_id: UUID, organization_id: UUID, lead_id: UUID) -> dict[str, Any]: ...
    async def opportunity_stage(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        opportunity_id: UUID,
        payload: OpportunityStageRequest,
    ) -> dict[str, Any]: ...
    async def campaigns(
        self,
        user_id: UUID,
        organization_id: UUID,
        status: str | None,
        channel: str | None,
        limit: int,
    ) -> dict[str, Any]: ...
    async def content_assets(
        self, user_id: UUID, organization_id: UUID, limit: int
    ) -> dict[str, Any]: ...
    async def create_content_asset(
        self,
        user_id: UUID,
        organization_id: UUID,
        payload: ContentAssetCreateRequest,
        idempotency_key: str,
    ) -> dict[str, Any]: ...
    async def retry_publication(
        self,
        user_id: UUID,
        organization_id: UUID,
        asset_id: UUID,
        payload: PublicationRetryRequest,
        idempotency_key: str,
    ) -> dict[str, Any]: ...


def _model[ModelT](model: type[ModelT], row: Mapping[str, Any]) -> ModelT:
    data = dict(row)
    for key in ("metadata", "score_factors", "body"):
        if key in data:
            data[key] = _json_value(data[key])
    return cast(ModelT, model.model_validate(data))  # type: ignore[attr-defined]


def _json_value(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


@dataclass
class PostgresCommercialRepository:
    database: Database

    async def documents(
        self,
        user_id: UUID,
        organization_id: UUID,
        status: str | None,
        classification: str | None,
        limit: int,
    ) -> dict[str, Any]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select id,title,source_type,source_uri,confidentiality::text classification,
              review_status::text status,metadata,created_at from public.knowledge_documents
              where organization_id=$1 and ($2::text is null or review_status::text=$2)
                and ($3::text is null or confidentiality::text=$3)
              order by created_at desc,id desc limit $4""",
                organization_id,
                status,
                classification,
                limit,
            )
            counts = await conn.fetchrow(
                """select count(*)::int total,
              count(*) filter(where review_status='approved')::int approved,
              count(*) filter(where review_status in ('draft','pending'))::int processing
              from public.knowledge_documents where organization_id=$1""",
                organization_id,
            )
        return {
            "documents": [_model(KnowledgeDocument, row) for row in rows],
            "counters": dict(counts or {}),
            "nextCursor": None,
        }

    async def upload_document(
        self,
        user_id: UUID,
        organization_id: UUID,
        payload: KnowledgeUploadRequest,
        idempotency_key: str,
    ) -> dict[str, Any]:
        fingerprint = _fingerprint(payload.model_dump(mode="json"))
        artifact_id = UUID(payload.file_ref)
        async with self.database.privileged() as conn:
            await self._authorize_and_lock(
                conn, organization_id, user_id, idempotency_key, "t36", None
            )
            artifact = await conn.fetchrow(
                """select id,name,storage_bucket,storage_path,checksum_sha256,mime_type,size_bytes
                     from public.artifacts
                    where id=$1 and organization_id=$2 and created_by=$3
                      and storage_bucket='artifacts' and quarantine_status='clean'
                      and checksum_sha256 ~ '^[0-9a-f]{64}$'
                      and storage_path is not null
                      and private.artifact_storage_path_is_valid(storage_path)
                      and (storage.foldername(storage_path))[1]=$2::text
                      and (storage.foldername(storage_path))[2]=$3::text
                      and private.try_uuid((storage.foldername(storage_path))[3])=$1""",
                artifact_id,
                organization_id,
                user_id,
            )
            if not artifact:
                raise HTTPException(
                    status_code=422,
                    detail="Artifact must be clean, tenant-scoped and owned by the requester",
                )
            existing = await conn.fetchrow(
                """select id,metadata from public.knowledge_documents where organization_id=$1
                  and metadata->>'idempotency_key'=$2 order by created_at desc limit 1""",
                organization_id,
                idempotency_key,
            )
            if existing:
                existing_metadata = _json_value(existing["metadata"])
                if existing_metadata.get("fingerprint") != fingerprint:
                    raise HTTPException(status_code=409, detail="Idempotency key payload conflict")
                return self._upload_response(existing["id"], existing_metadata, True)
            document_id, job_id = uuid4(), uuid4()
            metadata = {
                "visibility": payload.visibility,
                "job_id": str(job_id),
                "idempotency_key": idempotency_key,
                "fingerprint": fingerprint,
                "ingestion_status": "queued",
                "artifact_id": str(artifact_id),
                "checksum_sha256": artifact["checksum_sha256"],
                "expected_mime_type": artifact["mime_type"],
                "expected_size_bytes": artifact["size_bytes"],
            }
            row = await conn.fetchrow(
                """insert into public.knowledge_documents
              (id,organization_id,title,source_type,source_uri,storage_path,confidentiality,review_status,metadata,created_by)
              values($1,$2,$3,'upload',$4,$5,$6,'pending',$7::jsonb,$8) returning id""",
                document_id,
                organization_id,
                payload.title or artifact["name"],
                str(artifact_id),
                artifact["storage_path"],
                payload.classification,
                json.dumps(metadata),
                user_id,
            )
            if not row:
                raise HTTPException(status_code=403, detail="Active tenant membership required")
            await self._emit(
                conn,
                organization_id,
                "knowledge.ingestion.requested",
                "knowledge_document",
                document_id,
                {"jobId": str(job_id), "documentId": str(document_id)},
            )
        return self._upload_response(document_id, metadata, False)

    @staticmethod
    def _upload_response(
        document_id: UUID, metadata: Mapping[str, Any], replayed: bool
    ) -> dict[str, Any]:
        return {
            "documentId": document_id,
            "jobId": metadata["job_id"],
            "chunkPlan": {
                "status": metadata.get("ingestion_status", "queued"),
                "strategy": "semantic-1200",
            },
            "replayed": replayed,
        }

    async def memory_items(
        self, user_id: UUID, organization_id: UUID, kind: str | None, status: str | None, limit: int
    ) -> dict[str, Any]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select id,kind::text,content,source_reference source,confidence::float8,
              review_status::text status,valid_until,created_at from public.memory_items
              where organization_id=$1 and ($2::text is null or kind::text=$2)
                and ($3::text is null or review_status::text=$3)
                and review_status not in ('contested','expired','archived') and (valid_until is null or valid_until>now())
              order by created_at desc,id desc limit $4""",
                organization_id,
                kind,
                status,
                limit,
            )
        items = [
            MemoryItem.model_validate({**dict(row), "source": _json_value(row["source"])})
            for row in rows
        ]
        return {"items": items, "sources": [item.source for item in items], "nextCursor": None}

    async def semantic_search(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        payload: SemanticSearchRequest,
    ) -> dict[str, Any]:
        requested_classification = str(payload.filters["classification"])
        rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        maximum_by_role = {
            MemberRole.MEMBER: "medium",
            MemberRole.REVIEWER: "medium",
            MemberRole.ANALYST: "medium",
            MemberRole.MANAGER: "high",
            MemberRole.ADMIN: "critical",
            MemberRole.OWNER: "critical",
        }
        if rank[requested_classification] > rank[maximum_by_role[role]]:
            raise HTTPException(status_code=403, detail="Classification exceeds role clearance")
        embedding = "[" + ",".join(str(float(item)) for item in payload.filters["embedding"]) + "]"
        threshold = payload.filters.get("threshold", 0.75)
        if not isinstance(threshold, int | float) or isinstance(threshold, bool):
            raise HTTPException(status_code=422, detail="Invalid similarity threshold")
        threshold = float(threshold)
        if threshold < -1 or threshold > 1:
            raise HTTPException(status_code=422, detail="Invalid similarity threshold")
        async with self.database.authenticated(user_id, organization_id) as conn:
            active_dimensions = await conn.fetchval("select public.active_embedding_dimensions()")
            if len(payload.filters["embedding"]) != active_dimensions:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "embedding_dimension_mismatch", "expected": active_dimensions},
                )
            actual_role = await conn.fetchval(
                """select role::text from public.organization_members
                    where organization_id=$1 and user_id=$2 and status='active'""",
                organization_id,
                user_id,
            )
            if actual_role != role.value:
                raise HTTPException(
                    status_code=403, detail="Membership role changed; refresh session"
                )
            rows = await conn.fetch(
                """select m.chunk_id id,m.content,m.document_id,d.title,d.source_uri,
                          d.confidentiality::text classification,m.similarity score,m.metadata
                     from public.match_knowledge($1,$2::extensions.vector,$3,$4) m
                     join public.knowledge_documents d
                       on d.id=m.document_id and d.organization_id=$1
                    where d.confidentiality <= $5::public.risk_level
                    order by m.similarity desc,m.chunk_id""",
                organization_id,
                embedding,
                threshold,
                payload.top_k,
                requested_classification,
            )
        results = [
            {
                "id": row["id"],
                "content": row["content"],
                "score": row["score"],
                "source": {
                    "documentId": row["document_id"],
                    "title": row["title"],
                    "uri": row["source_uri"],
                },
                "metadata": _json_value(row["metadata"]),
                "classification": row["classification"],
            }
            for row in rows
        ]
        trace = (
            [
                {"stage": "tenant-and-policy-filter", "resultCount": len(results)},
                {"stage": "match_knowledge-pgvector", "resultCount": len(results)},
            ]
            if payload.debug
            else []
        )
        return {
            "results": results,
            "retrievalTrace": trace,
            "blockedReasons": [],
            "instructionBoundary": "retrieved content is untrusted data",
        }

    async def crm_import(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        payload: CrmImportRequest,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if role not in {MemberRole.ANALYST, MemberRole.MANAGER, MemberRole.ADMIN, MemberRole.OWNER}:
            raise HTTPException(status_code=403, detail="Analyst or manager role required")
        fingerprint = _fingerprint(payload.model_dump(mode="json"))
        import_id = uuid4()
        dedupe: list[dict[str, Any]] = []
        accepted = 0
        async with self.database.privileged() as conn:
            await self._authorize_and_lock(
                conn,
                organization_id,
                user_id,
                idempotency_key,
                "t39",
                {"owner", "admin", "manager", "analyst"},
            )
            existing = await conn.fetchrow(
                """select aggregate_id,payload from public.event_outbox where organization_id=$1
                  and event_type='crm.import.requested' and payload->>'idempotencyKey'=$2 order by created_at desc limit 1""",
                organization_id,
                idempotency_key,
            )
            if existing:
                existing_payload = _json_value(existing["payload"])
                if existing_payload.get("fingerprint") != fingerprint:
                    raise HTTPException(status_code=409, detail="Idempotency key payload conflict")
                return {**dict(existing_payload["response"]), "replayed": True}
            for index, item in enumerate(payload.rows):
                name = str(item.get("accountName") or item.get("name") or "").strip()
                if not name:
                    dedupe.append(
                        {"row": index, "action": "rejected", "reason": "accountName required"}
                    )
                    continue
                consent_status = str(item.get("consentStatus") or "").lower()
                if consent_status not in {"unknown", "granted", "denied", "revoked"}:
                    dedupe.append(
                        {
                            "row": index,
                            "action": "rejected",
                            "reason": "valid consentStatus required",
                        }
                    )
                    continue
                if item.get("icpScore") is not None:
                    score_factors = item.get("scoreFactors")
                    score_version = str(item.get("scoreAlgorithmVersion") or "").strip()
                    if (
                        not isinstance(score_factors, dict)
                        or not score_factors
                        or not score_version
                    ):
                        dedupe.append(
                            {
                                "row": index,
                                "action": "rejected",
                                "reason": "scored lead requires scoreFactors and scoreAlgorithmVersion",
                            }
                        )
                        continue
                raw_email = str(item.get("email") or "").strip().lower()
                email: str | None = None
                contact_name: str | None = None
                if raw_email:
                    try:
                        email = str(TypeAdapter(EmailStr).validate_python(raw_email))
                    except ValidationError:
                        dedupe.append(
                            {"row": index, "action": "rejected", "reason": "invalid email"}
                        )
                        continue
                    contact_name = str(item.get("contactName") or item.get("name") or "").strip()
                    if not contact_name:
                        dedupe.append(
                            {"row": index, "action": "rejected", "reason": "contactName required"}
                        )
                        continue
                owner_id = user_id
                if item.get("ownerId"):
                    try:
                        requested_owner = UUID(str(item["ownerId"]))
                    except ValueError:
                        dedupe.append(
                            {"row": index, "action": "rejected", "reason": "invalid ownerId"}
                        )
                        continue
                    valid_owner = await conn.fetchval(
                        """select exists(select 1 from public.organization_members
                             where organization_id=$1 and user_id=$2 and status='active')""",
                        organization_id,
                        requested_owner,
                    )
                    if not valid_owner:
                        dedupe.append(
                            {"row": index, "action": "rejected", "reason": "owner not active"}
                        )
                        continue
                    owner_id = requested_owner
                domain = str(item.get("domain") or "").lower() or None
                existing = None
                if domain is not None:
                    existing = await conn.fetchrow(
                        "select id,name from public.crm_accounts where organization_id=$1 and domain=$2",
                        organization_id,
                        domain,
                    )
                if existing:
                    account_id = existing["id"]
                    dedupe.append(
                        {"row": index, "action": "merge_preview", "accountId": str(account_id)}
                    )
                else:
                    account_id = await conn.fetchval(
                        "insert into public.crm_accounts(organization_id,name,domain,owner_user_id,metadata) values($1,$2,$3,$4,$5::jsonb) returning id",
                        organization_id,
                        name,
                        domain,
                        user_id,
                        json.dumps({"source": payload.source}),
                    )
                    dedupe.append({"row": index, "action": "create", "accountId": str(account_id)})
                contact_id: UUID | None = None
                if email and contact_name:
                    contact_id = await conn.fetchval(
                        """insert into public.crm_contacts(
                             organization_id,account_id,name,email,phone,consent_status,legal_basis,metadata
                           ) values($1,$2,$3,$4,$5,$6,$7,$8::jsonb)
                           on conflict (organization_id,email) do update set
                             account_id=excluded.account_id,name=excluded.name,phone=excluded.phone,
                             consent_status=excluded.consent_status,legal_basis=excluded.legal_basis,
                             metadata=excluded.metadata
                           returning id""",
                        organization_id,
                        account_id,
                        contact_name,
                        email,
                        item.get("phone"),
                        consent_status,
                        str(item.get("legalBasis") or payload.consent_basis),
                        json.dumps({"source": payload.source}),
                    )
                    dedupe[-1]["contactId"] = str(contact_id)
                if bool(item.get("createLead", True)) and consent_status == "granted":
                    lead_id = await conn.fetchval(
                        """insert into public.leads(
                             organization_id,account_id,contact_id,owner_user_id,status,source,
                             icp_score,score_factors,score_algorithm_version,next_action
                           ) values($1,$2,$3,$4,'new',$5,$6,$7::jsonb,$8,$9) returning id""",
                        organization_id,
                        account_id,
                        contact_id,
                        owner_id,
                        payload.source,
                        item.get("icpScore"),
                        json.dumps(item.get("scoreFactors") or {}),
                        item.get("scoreAlgorithmVersion"),
                        item.get("nextAction"),
                    )
                    dedupe[-1]["leadId"] = str(lead_id)
                accepted += 1
            response = {
                "importId": import_id,
                "dedupePreview": dedupe,
                "rowReports": dedupe,
                "validationSummary": {
                    "total": len(payload.rows),
                    "accepted": accepted,
                    "rejected": len(payload.rows) - accepted,
                },
                "status": "completed" if accepted == len(payload.rows) else "partial",
            }
            await conn.execute(
                """insert into public.crm_imports(
                     id,organization_id,source,consent_basis,idempotency_key,fingerprint,status,
                     total_rows,accepted_rows,failed_rows,created_by
                   ) values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
                import_id,
                organization_id,
                payload.source,
                payload.consent_basis,
                idempotency_key,
                fingerprint,
                response["status"],
                len(payload.rows),
                accepted,
                len(payload.rows) - accepted,
                user_id,
            )
            for index, item in enumerate(payload.rows):
                report = dedupe[index]
                row_status = "failed" if report["action"] == "rejected" else "accepted"
                await conn.execute(
                    """insert into public.crm_import_rows(
                         import_id,organization_id,row_number,payload,status,action,account_id,
                         contact_id,lead_id,attempts,error_code,error_detail
                       ) values($1,$2,$3,$4::jsonb,$5,$6,$7,$8,$9,1,$10,$11)""",
                    import_id,
                    organization_id,
                    index,
                    json.dumps(item),
                    row_status,
                    report["action"],
                    report.get("accountId"),
                    report.get("contactId"),
                    report.get("leadId"),
                    "validation_error" if row_status == "failed" else None,
                    report.get("reason"),
                )
            await self._emit(
                conn,
                organization_id,
                "crm.import.requested",
                "crm_import",
                import_id,
                {
                    "idempotencyKey": idempotency_key,
                    "fingerprint": fingerprint,
                    "response": response,
                    "consentBasis": payload.consent_basis,
                },
            )
        return {**response, "replayed": False}

    async def _process_crm_resume_row(
        self,
        conn: Any,
        user_id: UUID,
        organization_id: UUID,
        source: str,
        consent_basis: str,
        row_number: int,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        return await CommercialRepository._process_crm_resume_row(
            self, conn, user_id, organization_id, source, consent_basis, row_number, item
        )

    async def resume_crm_import(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        import_id: UUID,
        payload: CrmImportResumeRequest,
    ) -> dict[str, Any]:
        if role not in {MemberRole.ANALYST, MemberRole.MANAGER, MemberRole.ADMIN, MemberRole.OWNER}:
            raise HTTPException(status_code=403, detail="Analyst or manager role required")
        requested = {item.row_number: item.payload for item in payload.rows}
        if len(requested) != len(payload.rows):
            raise HTTPException(status_code=422, detail="Duplicate CRM import row number")
        ordered = sorted(requested)
        resume_fingerprint = _fingerprint(
            {
                "importId": import_id,
                "rows": [{"rowNumber": index, "payload": requested[index]} for index in ordered],
            }
        )
        async with self.database.privileged() as conn:
            await conn.execute(
                "select pg_advisory_xact_lock(hashtextextended($1,0))",
                f"crm.resume:{organization_id}:{import_id}",
            )
            allowed = await conn.fetchrow(
                """select i.source,i.consent_basis
                     from public.crm_imports i join public.organization_members m
                       on m.organization_id=i.organization_id and m.user_id=$3 and m.status='active'
                    where i.id=$1 and i.organization_id=$2 for update of i""",
                import_id,
                organization_id,
                user_id,
            )
            if not allowed:
                raise HTTPException(status_code=404, detail="CRM import not found")
            rows = await conn.fetch(
                """select row_number,status,action,account_id,contact_id,lead_id,error_detail,
                          last_resume_fingerprint
                     from public.crm_import_rows
                    where import_id=$1 and organization_id=$2
                      and row_number=any($3::integer[]) order by row_number for update""",
                import_id,
                organization_id,
                ordered,
            )
            if {row["row_number"] for row in rows} != set(requested):
                raise HTTPException(status_code=409, detail="CRM import rows not found")

            if all(row["last_resume_fingerprint"] == resume_fingerprint for row in rows):
                summary = await self._crm_import_summary(conn, import_id, organization_id)
                replay_reports = [self._crm_row_report(row) for row in rows]
                return self._crm_resume_response(import_id, replay_reports, summary, replayed=True)
            if any(row["status"] != "failed" for row in rows):
                raise HTTPException(status_code=409, detail="Only failed rows can be resumed")
            reports: list[dict[str, Any]] = []
            for original_row in ordered:
                report = await self._process_crm_resume_row(
                    conn,
                    user_id,
                    organization_id,
                    allowed["source"],
                    allowed["consent_basis"],
                    original_row,
                    requested[original_row],
                )
                reports.append(report)
                row_status = "failed" if report["action"] == "rejected" else "accepted"
                await conn.execute(
                    """update public.crm_import_rows set payload=$4::jsonb,status=$5,action=$6,
                         account_id=$7,contact_id=$8,lead_id=$9,attempts=attempts+1,
                         error_code=$10,error_detail=$11,last_resume_fingerprint=$12,
                         last_resume_at=now(),updated_at=now()
                       where import_id=$1 and organization_id=$2 and row_number=$3""",
                    import_id,
                    organization_id,
                    original_row,
                    json.dumps(requested[original_row]),
                    row_status,
                    report["action"],
                    report.get("accountId"),
                    report.get("contactId"),
                    report.get("leadId"),
                    "validation_error" if row_status == "failed" else None,
                    report.get("reason"),
                    resume_fingerprint,
                )
            summary = await self._crm_import_summary(conn, import_id, organization_id)
            final_status = "completed" if summary["rejected"] == 0 else "partial"
            await conn.execute(
                """update public.crm_imports set status=$3,accepted_rows=$4,failed_rows=$5,updated_at=now()
                    where id=$1 and organization_id=$2""",
                import_id,
                organization_id,
                final_status,
                summary["accepted"],
                summary["rejected"],
            )
            response = self._crm_resume_response(import_id, reports, summary, replayed=False)
            await self._emit(
                conn,
                organization_id,
                "crm.import.resumed",
                "crm_import",
                import_id,
                {"fingerprint": resume_fingerprint, "response": response},
            )
            return response

    async def _crm_import_summary(self, conn: Any, import_id: UUID, organization_id: UUID) -> Any:
        return await conn.fetchrow(
            """select count(*)::int total,
                count(*) filter(where status='accepted')::int accepted,
                count(*) filter(where status='failed')::int rejected
               from public.crm_import_rows where import_id=$1 and organization_id=$2""",
            import_id,
            organization_id,
        )

    @staticmethod
    def _crm_row_report(row: Any) -> dict[str, Any]:
        return {
            "row": row["row_number"],
            "action": row["action"],
            **({"accountId": str(row["account_id"])} if row["account_id"] else {}),
            **({"contactId": str(row["contact_id"])} if row["contact_id"] else {}),
            **({"leadId": str(row["lead_id"])} if row["lead_id"] else {}),
            **({"reason": row["error_detail"]} if row["error_detail"] else {}),
        }

    @staticmethod
    def _crm_resume_response(
        import_id: UUID, reports: list[dict[str, Any]], summary: Any, replayed: bool
    ) -> dict[str, Any]:
        return {
            "importId": import_id,
            "dedupePreview": reports,
            "rowReports": reports,
            "validationSummary": dict(summary),
            "status": "completed" if summary["rejected"] == 0 else "partial",
            "replayed": replayed,
        }

    async def merge_crm_accounts(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        source_id: UUID,
        target_id: UUID,
        reason: str,
    ) -> dict[str, Any]:
        if role not in {MemberRole.MANAGER, MemberRole.ADMIN, MemberRole.OWNER}:
            raise HTTPException(status_code=403, detail="Manager role required")
        async with self.database.privileged() as conn:
            allowed = await conn.fetchval(
                """select exists(select 1 from public.organization_members
                    where organization_id=$1 and user_id=$2 and status='active'
                      and role in ('owner','admin','manager'))""",
                organization_id,
                user_id,
            )
            if not allowed:
                raise HTTPException(status_code=403, detail="Active manager membership required")
            try:
                result = await conn.fetchval(
                    "select private.merge_crm_accounts($1,$2,$3,$4,$5)",
                    organization_id,
                    source_id,
                    target_id,
                    user_id,
                    reason,
                )
            except Exception as exc:
                if getattr(exc, "sqlstate", None) == "P0002":
                    raise HTTPException(
                        status_code=404, detail="Active CRM accounts not found"
                    ) from exc
                raise
        return cast(dict[str, Any], _json_value(result))

    async def leads(
        self,
        user_id: UUID,
        organization_id: UUID,
        status: str | None,
        owner_id: UUID | None,
        limit: int,
    ) -> dict[str, Any]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select id,account_id,contact_id,owner_user_id,status::text,source,icp_score::float8,
              score_factors,score_algorithm_version,next_action,next_action_at,created_at from public.leads where organization_id=$1
              and ($2::text is null or status::text=$2) and ($3::uuid is null or owner_user_id=$3)
              order by icp_score desc nulls last,created_at desc limit $4""",
                organization_id,
                status,
                owner_id,
                limit,
            )
            counts = await conn.fetchrow(
                "select count(*)::int total,count(*) filter(where status='qualified')::int qualified from public.leads where organization_id=$1",
                organization_id,
            )
        return {
            "items": [_model(Lead, row) for row in rows],
            "counters": dict(counts or {}),
            "nextCursor": None,
        }

    async def lead(self, user_id: UUID, organization_id: UUID, lead_id: UUID) -> dict[str, Any]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            row = await conn.fetchrow(
                """select id,account_id,contact_id,owner_user_id,status::text,source,icp_score::float8,
              score_factors,score_algorithm_version,next_action,next_action_at,created_at from public.leads where id=$1 and organization_id=$2""",
                lead_id,
                organization_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Lead not found")
            signals = await conn.fetch(
                "select signal_type,strength::float8,source,payload,occurred_at from public.lead_signals where lead_id=$1 and organization_id=$2 order by occurred_at desc",
                lead_id,
                organization_id,
            )
        lead = _model(Lead, row)
        return {
            "lead": lead,
            "timeline": [
                {"type": "created", "at": lead.created_at},
                *[dict(item) for item in signals],
            ],
            "signals": [dict(item) for item in signals],
            "suggestions": [{"action": lead.next_action, "reason": lead.score_factors}]
            if lead.next_action
            else [],
        }

    async def opportunity_stage(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        opportunity_id: UUID,
        payload: OpportunityStageRequest,
    ) -> dict[str, Any]:
        if role not in {MemberRole.MANAGER, MemberRole.ADMIN, MemberRole.OWNER}:
            raise HTTPException(status_code=403, detail="Manager role required")
        allowed = {"discovery", "qualification", "proposal", "negotiation", "won", "lost"}
        if payload.target_stage not in allowed:
            raise HTTPException(status_code=422, detail="Invalid opportunity stage")
        async with self.database.privileged() as conn:
            member = await conn.fetchval(
                "select exists(select 1 from public.organization_members where organization_id=$1 and user_id=$2 and status='active' and role in ('owner','admin','manager'))",
                organization_id,
                user_id,
            )
            if not member:
                raise HTTPException(status_code=403, detail="Active manager membership required")
            current = await conn.fetchrow(
                """select stage,amount,probability,expected_close_date,loss_reason,closed_at
                     from public.opportunities where id=$1 and organization_id=$2 for update""",
                opportunity_id,
                organization_id,
            )
            if not current:
                raise HTTPException(status_code=404, detail="Opportunity not found")
            if current["stage"] in {"won", "lost"} and current["stage"] != payload.target_stage:
                raise HTTPException(
                    status_code=409, detail="Closed opportunity cannot change stage"
                )
            amount = payload.amount if payload.amount is not None else current["amount"]
            probability = (
                payload.probability if payload.probability is not None else current["probability"]
            )
            if payload.target_stage == "won":
                probability = 100
            elif payload.target_stage == "lost":
                probability = 0
            expected_close_date = (
                payload.expected_close_date
                if payload.expected_close_date is not None
                else current["expected_close_date"]
            )
            loss_reason = payload.loss_reason or current["loss_reason"]
            missing: list[str] = []
            if payload.target_stage in {"proposal", "negotiation", "won"} and amount is None:
                missing.append("amount")
            if payload.target_stage == "negotiation" and probability is None:
                missing.append("probability")
            if payload.target_stage == "lost" and not loss_reason:
                missing.append("lossReason")
            if missing:
                raise HTTPException(status_code=422, detail={"missingFields": missing})
            row = await conn.fetchrow(
                """update public.opportunities set stage=$3,amount=$4,probability=$5,
              expected_close_date=$6,loss_reason=case when $3='lost' then $7 else null end,
              closed_at=case when $3 in ('won','lost') then coalesce(closed_at,now()) else null end
              where id=$1 and organization_id=$2 returning id,name,stage,amount::float8,currency,probability::float8,expected_close_date""",
                opportunity_id,
                organization_id,
                payload.target_stage,
                amount,
                probability,
                expected_close_date,
                loss_reason,
            )
            event_id = await self._emit(
                conn,
                organization_id,
                "opportunities.updated",
                "opportunity",
                opportunity_id,
                {
                    "from": current["stage"],
                    "to": payload.target_stage,
                    "forecast": {
                        "amount": amount,
                        "probability": probability,
                        "expectedCloseDate": expected_close_date,
                        "lossReason": loss_reason if payload.target_stage == "lost" else None,
                    },
                },
            )
        return {
            "opportunity": _model(Opportunity, cast(Mapping[str, Any], row)),
            "boardSummary": {"movedFrom": current["stage"], "movedTo": payload.target_stage},
            "auditEntry": {"eventId": event_id, "actorUserId": user_id},
        }

    async def campaigns(
        self,
        user_id: UUID,
        organization_id: UUID,
        status: str | None,
        channel: str | None,
        limit: int,
    ) -> dict[str, Any]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select distinct c.id,c.name,c.objective,c.status,c.budget::float8,c.starts_at,c.ends_at,c.created_at
              from public.campaigns c left join public.content_assets a on a.campaign_id=c.id and a.organization_id=c.organization_id
              where c.organization_id=$1 and ($2::text is null or c.status=$2) and ($3::text is null or a.channel=$3)
              order by c.created_at desc limit $4""",
                organization_id,
                status,
                channel,
                limit,
            )
        campaigns = [_model(Campaign, row) for row in rows]
        return {"campaigns": campaigns, "counters": {"total": len(campaigns)}, "nextCursor": None}

    async def content_assets(
        self, user_id: UUID, organization_id: UUID, limit: int
    ) -> dict[str, Any]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select id,campaign_id,title,content_type,status::text,body,channel,scheduled_at,published_at,external_id,created_at,updated_at
              from public.content_assets where organization_id=$1 order by updated_at desc,id desc limit $2""",
                organization_id,
                limit,
            )
        assets = [_model(ContentAsset, row) for row in rows]
        return {
            "assets": assets,
            "approvals": [],
            "versionHistory": [
                {
                    "assetId": item.id,
                    "version": len(item.body.get("versions", [])) or 1,
                    "updatedAt": item.updated_at,
                }
                for item in assets
            ],
        }

    async def create_content_asset(
        self,
        user_id: UUID,
        organization_id: UUID,
        payload: ContentAssetCreateRequest,
        idempotency_key: str,
    ) -> dict[str, Any]:
        fingerprint = _fingerprint(payload.model_dump(mode="json"))
        body = {
            "brief": payload.brief,
            "channels": payload.channels,
            "variants": payload.variants,
            "versions": [{"version": 1, "brief": payload.brief}],
            "idempotency_key": idempotency_key,
            "fingerprint": fingerprint,
        }
        approval_payload_hash = _fingerprint(body) if payload.approval_request_id else None
        async with self.database.privileged() as conn:
            await self._authorize_and_lock(
                conn, organization_id, user_id, idempotency_key, "t44", None
            )
            existing = await conn.fetchrow(
                """select id,campaign_id,title,content_type,status::text,body,channel,scheduled_at,published_at,external_id,created_at,updated_at
                  from public.content_assets where organization_id=$1 and body->>'idempotency_key'=$2 order by created_at desc limit 1""",
                organization_id,
                idempotency_key,
            )
            if existing:
                existing_body = _json_value(existing["body"])
                if existing_body.get("fingerprint") != fingerprint:
                    raise HTTPException(status_code=409, detail="Idempotency key payload conflict")
                return self._asset_response(_model(ContentAsset, existing), True)
            if payload.approval_request_id:
                if payload.task_id is None:
                    raise HTTPException(
                        status_code=422,
                        detail="Approved content must identify its approval task",
                    )
                approval_exists = await conn.fetchval(
                    """select exists(select 1 from public.approval_requests
                         where organization_id=$1 and id=$2 and status='pending'
                           and decided_at is null and task_id=$3)""",
                    organization_id,
                    payload.approval_request_id,
                    payload.task_id,
                )
                if not approval_exists:
                    raise HTTPException(
                        status_code=422,
                        detail="Approval request must be pending in the content tenant",
                    )
            row = await conn.fetchrow(
                """insert into public.content_assets(
                     organization_id,campaign_id,task_id,title,content_type,status,body,channel,
                     approval_request_id,approval_payload_hash
                   )
              select $1,$2,$9,$3,'multichannel','draft',$4::jsonb,$5,$7,$8 where exists(select 1 from public.organization_members
                where organization_id=$1 and user_id=$6 and status='active') and ($2::uuid is null or exists(
                select 1 from public.campaigns where id=$2 and organization_id=$1))
              returning id,campaign_id,title,content_type,status::text,body,channel,scheduled_at,published_at,external_id,created_at,updated_at""",
                organization_id,
                payload.campaign_id,
                payload.title or payload.brief[:120],
                json.dumps(body),
                payload.channels[0],
                user_id,
                payload.approval_request_id,
                approval_payload_hash,
                payload.task_id,
            )
            if not row:
                raise HTTPException(
                    status_code=403, detail="Active tenant membership and valid campaign required"
                )
            await self._emit(
                conn,
                organization_id,
                "content.updated",
                "content_asset",
                row["id"],
                {"status": "draft"},
            )
        return self._asset_response(_model(ContentAsset, cast(Mapping[str, Any], row)), False)

    @staticmethod
    def _asset_response(asset: ContentAsset, replayed: bool) -> dict[str, Any]:
        return {
            "asset": asset,
            "approvals": [],
            "versionHistory": asset.body.get("versions", []),
            "replayed": replayed,
        }

    async def retry_publication(
        self,
        user_id: UUID,
        organization_id: UUID,
        asset_id: UUID,
        payload: PublicationRetryRequest,
        idempotency_key: str,
    ) -> dict[str, Any]:
        key = idempotency_key
        fingerprint = _fingerprint(payload.model_dump(mode="json"))
        async with self.database.privileged() as conn:
            await self._authorize_and_lock(conn, organization_id, user_id, key, "t45", None)
            row = await conn.fetchrow(
                """select id,status::text,body,channel,approval_request_id,approval_payload_hash
                     from public.content_assets
                    where id=$1 and organization_id=$2 for update""",
                asset_id,
                organization_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Publication not found")
            body = _json_value(row["body"])
            payload_hash = _fingerprint(body)
            approved = await conn.fetchval(
                """select exists(
                     select 1 from public.content_assets ca
                     join public.approval_requests ar
                       on ar.organization_id=ca.organization_id
                       and ar.id=ca.approval_request_id and ar.task_id=ca.task_id
                     join public.approval_decisions ad
                       on ad.organization_id=ar.organization_id
                      and ad.approval_request_id=ar.id
                    where ca.organization_id=$2 and ca.id=$1 and ca.task_id is not null
                      and ar.status='approved' and ar.decided_at is not null
                      and ad.decision='approved' and ca.approval_payload_hash=$3
                   )""",
                asset_id,
                organization_id,
                payload_hash,
            )
            if not approved:
                raise HTTPException(
                    status_code=409, detail="A valid approval is required before publication retry"
                )
            previous = await conn.fetchrow(
                """select content_asset_id,request_fingerprint,channel,reason,status,
                          preserved_payload
                     from private.publication_attempts
                    where organization_id=$1 and idempotency_key=$2""",
                organization_id,
                key,
            )
            if previous:
                if (
                    previous["content_asset_id"] != asset_id
                    or previous["request_fingerprint"] != fingerprint
                ):
                    raise HTTPException(status_code=409, detail="Idempotency key payload conflict")
                attempt = {
                    "idempotencyKey": key,
                    "fingerprint": previous["request_fingerprint"],
                    "channel": previous["channel"],
                    "reason": previous["reason"],
                    "status": previous["status"],
                }
                return {
                    "publication": {
                        "id": asset_id,
                        "status": "scheduled",
                        "channel": previous["channel"],
                    },
                    "providerAttempt": attempt,
                    "preservedPayload": _json_value(previous["preserved_payload"]),
                    "replayed": True,
                }
            if row["status"] != "failed":
                raise HTTPException(
                    status_code=409, detail="Only failed publications can be retried"
                )
            attempt = {
                "idempotencyKey": key,
                "fingerprint": fingerprint,
                "channel": payload.channel,
                "reason": payload.reason,
                "status": "queued",
            }
            preserved = body.get("publication_payload", body)
            await conn.execute(
                """insert into private.publication_attempts(
                       organization_id,content_asset_id,idempotency_key,request_fingerprint,
                       channel,reason,status,preserved_payload)
                     values($1,$2,$3,$4,$5,$6,'queued',$7::jsonb)""",
                organization_id,
                asset_id,
                key,
                fingerprint,
                payload.channel,
                payload.reason,
                json.dumps(preserved),
            )
            await conn.execute(
                "update public.content_assets set status='scheduled',channel=$3 where id=$1 and organization_id=$2",
                asset_id,
                organization_id,
                payload.channel,
            )
            await self._emit(
                conn,
                organization_id,
                "publications.retry.requested",
                "content_asset",
                asset_id,
                {"attempt": attempt, "preservedPayload": preserved},
            )
        return {
            "publication": {"id": asset_id, "status": "scheduled", "channel": payload.channel},
            "providerAttempt": attempt,
            "preservedPayload": preserved,
            "replayed": False,
        }

    @staticmethod
    async def _authorize_and_lock(
        conn: Any,
        organization_id: UUID,
        user_id: UUID,
        idempotency_key: str,
        operation: str,
        allowed_roles: set[str] | None,
    ) -> str:
        role = await conn.fetchval(
            """select role::text from public.organization_members
                where organization_id=$1 and user_id=$2 and status='active'
                for key share""",
            organization_id,
            user_id,
        )
        if not role or (allowed_roles is not None and role not in allowed_roles):
            raise HTTPException(status_code=403, detail="Active authorized membership required")
        await conn.execute(
            "select pg_advisory_xact_lock(hashtextextended($1, 0))",
            f"{organization_id}:{operation}:{idempotency_key}",
        )
        return cast(str, role)

    @staticmethod
    async def _emit(
        conn: Any,
        organization_id: UUID,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: Mapping[str, Any],
    ) -> UUID:
        event_id = uuid4()
        await conn.execute(
            """insert into public.event_outbox(id,organization_id,event_type,aggregate_type,aggregate_id,payload)
          values($1,$2,$3,$4,$5,$6::jsonb)""",
            event_id,
            organization_id,
            event_type,
            aggregate_type,
            aggregate_id,
            json.dumps(payload, default=str),
        )
        return event_id
