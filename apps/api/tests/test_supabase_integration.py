# ruff: noqa: E501
import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from bighead_api.administration.models import PrivacyRequestCreateRequest
from bighead_api.administration.service import PostgresAdministrationRepository
from bighead_api.artifacts.models import (
    QuarantineStatus,
    UploadConfirmRequest,
    UploadInitiateRequest,
)
from bighead_api.artifacts.service import (
    ArtifactService,
    PostgresArtifactRepository,
    SupabaseStorageGateway,
)
from bighead_api.collaboration.models import (
    MessageCreateRequest,
    RoomCreateRequest,
    RoomPatchRequest,
    TaskCreateRequest,
    TaskStatus,
    TaskTransitionRequest,
)
from bighead_api.collaboration.service import PostgresCollaborationRepository
from bighead_api.commercial.models import (
    ContentAssetCreateRequest,
    CrmImportRequest,
    KnowledgeUploadRequest,
    OpportunityStageRequest,
    PublicationRetryRequest,
    SemanticSearchRequest,
)
from bighead_api.commercial.service import PostgresCommercialRepository, _fingerprint
from bighead_api.governance.models import (
    PlaybookInstantiateRequest,
    PortalDecisionRequest,
    WorkflowRollbackRequest,
)
from bighead_api.governance.service import PostgresGovernanceRepository
from bighead_api.identity.auth import SupabaseAuthProvider
from bighead_api.identity.models import MemberRole
from bighead_api.identity.repository import Database, PostgresIdentityRepository
from fastapi import HTTPException

pytestmark = pytest.mark.skipif(
    os.getenv("BIGHEAD_RUN_SUPABASE_INTEGRATION") != "1",
    reason="requires the local Supabase stack",
)

ATLAS_ORGANIZATION_ID = UUID("a7100000-0000-0000-0000-000000000001")
ATLAS_OWNER_ID = UUID("d1000000-0000-0000-0000-000000000001")
ATLAS_REVIEWER_ID = UUID("d1000000-0000-0000-0000-000000000005")
ATLAS_ANALYST_ID = UUID("d1000000-0000-0000-0000-000000000006")
ATLAS_MEMBER_ID = UUID("d1000000-0000-0000-0000-000000000004")
BEACON_OWNER_ID = UUID("d2000000-0000-0000-0000-000000000001")


class SignedPrivacyStorage:
    async def signed_upload(self, path: str) -> tuple[str, datetime]:
        return f"https://storage.example.test/upload/{path}", datetime.now(UTC)

    async def signed_download(self, path: str) -> tuple[str, datetime]:
        return f"https://storage.example.test/download/{path}", datetime.now(UTC)


@pytest.mark.asyncio
async def test_real_collaboration_replay_membership_retry_and_audit_guards() -> None:
    database = Database(os.environ["SUPABASE_INTEGRATION_DATABASE_URL"])
    repo = PostgresCollaborationRepository(database)
    room_id: UUID | None = None
    message_id: UUID | None = None
    task_id: UUID | None = None
    run_id: UUID | None = None
    message_payload = MessageCreateRequest(body="replay guard", client_id=f"guard-{uuid4()}")
    task_key = f"task-guard-{uuid4()}"
    task_payload: TaskCreateRequest | None = None
    try:
        room = await repo.create_room(
            ATLAS_ANALYST_ID,
            ATLAS_ORGANIZATION_ID,
            RoomCreateRequest(name=f"Replay guard {uuid4()}"),
        )
        room_id = room.id
        message = await repo.create_message(
            ATLAS_ANALYST_ID, ATLAS_ORGANIZATION_ID, room_id, message_payload
        )
        message_id = message.id
        task_payload = TaskCreateRequest(
            goal="Verify transaction replay security",
            room_id=room_id,
            source_message_id=message_id,
        )
        task, replayed = await repo.create_task(
            ATLAS_ANALYST_ID, ATLAS_ORGANIZATION_ID, task_payload, task_key
        )
        task_id = task.id
        assert replayed is False

        patched = await repo.patch_room(
            ATLAS_OWNER_ID,
            ATLAS_ORGANIZATION_ID,
            room_id,
            RoomPatchRequest(description="audited"),
        )
        assert patched.room.description == "audited"
        transitioned, _ = await repo.transition_task(
            ATLAS_ANALYST_ID,
            ATLAS_ORGANIZATION_ID,
            task_id,
            TaskTransitionRequest(
                target_state=TaskStatus.TRIAGED,
                reason="audit smoke",
                expected_version=1,
            ),
        )
        assert transitioned.status == TaskStatus.TRIAGED

        pool = await database.pool()
        run_id = uuid4()
        await pool.execute(
            """insert into public.runs(
                 id,organization_id,task_id,status,idempotency_key,attempt
               ) values($1,$2,$3,'failed',$4,1)""",
            run_id,
            ATLAS_ORGANIZATION_ID,
            task_id,
            f"original-{run_id}",
        )
        retries = await asyncio.gather(
            repo.retry_run(ATLAS_ANALYST_ID, ATLAS_ORGANIZATION_ID, run_id),
            repo.retry_run(ATLAS_ANALYST_ID, ATLAS_ORGANIZATION_ID, run_id),
        )
        assert retries[0].id == retries[1].id

        audit_actions = await pool.fetch(
            """select action from public.audit_log
                where organization_id=$1 and resource_id=any($2::text[])""",
            ATLAS_ORGANIZATION_ID,
            [str(room_id), str(task_id), str(retries[0].id)],
        )
        assert {row["action"] for row in audit_actions} >= {
            "room.updated",
            "task.created",
            "task.transitioned",
            "run.retry_requested",
        }

        await pool.execute(
            """update public.organization_members set status='suspended'
                where organization_id=$1 and user_id=$2""",
            ATLAS_ORGANIZATION_ID,
            ATLAS_ANALYST_ID,
        )
        with pytest.raises(HTTPException) as message_denied:
            await repo.create_message(
                ATLAS_ANALYST_ID, ATLAS_ORGANIZATION_ID, room_id, message_payload
            )
        assert message_denied.value.status_code == 403
        with pytest.raises(HTTPException) as task_denied:
            await repo.create_task(ATLAS_ANALYST_ID, ATLAS_ORGANIZATION_ID, task_payload, task_key)
        assert task_denied.value.status_code == 403
    finally:
        pool = await database.pool()
        await pool.execute(
            """update public.organization_members set status='active'
                where organization_id=$1 and user_id=$2""",
            ATLAS_ORGANIZATION_ID,
            ATLAS_ANALYST_ID,
        )
        resource_ids = [str(item) for item in (room_id, message_id, task_id, run_id) if item]
        if task_id:
            await pool.execute("delete from public.tasks where id=$1", task_id)
        if room_id:
            await pool.execute("delete from public.rooms where id=$1", room_id)
        if resource_ids:
            await pool.execute(
                "delete from public.event_outbox where aggregate_id::text=any($1::text[])",
                resource_ids,
            )
            await pool.execute(
                "delete from public.audit_log where resource_id=any($1::text[])", resource_ids
            )
        await database.close()


@pytest.mark.asyncio
async def test_real_auth_database_and_storage_round_trip() -> None:
    base_url = os.environ["SUPABASE_INTEGRATION_URL"].rstrip("/")
    publishable_key = os.environ["SUPABASE_INTEGRATION_PUBLISHABLE_KEY"]
    secret_key = os.environ["SUPABASE_INTEGRATION_SECRET_KEY"]
    database = Database(os.environ["SUPABASE_INTEGRATION_DATABASE_URL"])
    auth = SupabaseAuthProvider(base_url, publishable_key, secret_key)
    storage = SupabaseStorageGateway(base_url, secret_key)
    artifacts = ArtifactService(PostgresArtifactRepository(database), storage)
    content = b"BigHead real Storage integration\n"
    checksum = hashlib.sha256(content).hexdigest()
    created = None

    try:
        user, session = await auth.login("owner@atlas.bighead.dev", "BigHeadLocalOnly!2026")
        assert user.id == ATLAS_OWNER_ID
        assert (await auth.verify(session.access_token)).id == ATLAS_OWNER_ID

        memberships = await PostgresIdentityRepository(database).memberships(ATLAS_OWNER_ID)
        membership_pairs = {(item.organization_id, item.role.value) for item in memberships}
        assert (ATLAS_ORGANIZATION_ID, "owner") in membership_pairs
        assert all(
            item.organization_id != UUID("b7200000-0000-0000-0000-000000000001")
            for item in memberships
        )

        created = await artifacts.initiate(
            ATLAS_ORGANIZATION_ID,
            ATLAS_OWNER_ID,
            UploadInitiateRequest(
                filename="integration.txt",
                mime_type="text/plain",
                size_bytes=len(content),
                checksum_sha256=checksum,
            ),
        )
        async with httpx.AsyncClient(timeout=10) as client:
            uploaded = await client.put(
                str(created.upload_url),
                content=content,
                headers=created.required_headers,
            )
        assert uploaded.status_code == 200

        confirmed = await artifacts.confirm(
            ATLAS_ORGANIZATION_ID,
            created.artifact_id,
            UploadConfirmRequest(checksum_sha256=checksum),
        )
        assert confirmed.quarantine_status == QuarantineStatus.PENDING

        pool = await database.pool()
        await pool.execute(
            "update public.artifacts set quarantine_status = 'clean' where id = $1",
            created.artifact_id,
        )
        downloadable = await artifacts.download(ATLAS_ORGANIZATION_ID, created.artifact_id)
        async with httpx.AsyncClient(timeout=10) as client:
            downloaded = await client.get(str(downloadable.download_url))
        assert downloaded.status_code == 200
        assert downloaded.content == content

        await auth.revoke(session.access_token, "local")
    finally:
        if created is not None:
            headers = {"apikey": secret_key, "Authorization": f"Bearer {secret_key}"}
            encoded_path = quote(created.path, safe="/")
            async with httpx.AsyncClient(timeout=10) as client:
                await client.delete(
                    f"{base_url}/storage/v1/object/artifacts/{encoded_path}", headers=headers
                )
            pool = await database.pool()
            await pool.execute("delete from public.artifacts where id = $1", created.artifact_id)
        await database.close()


@pytest.mark.asyncio
async def test_real_t35_t45_postgres_tenant_and_outbox_round_trip() -> None:
    database = Database(os.environ["SUPABASE_INTEGRATION_DATABASE_URL"])
    repo = PostgresCommercialRepository(database)
    artifact_id = uuid4()
    document_id: UUID | None = None
    memory_id = uuid4()
    lead_id: UUID | None = None
    contact_id: UUID | None = None
    opportunity_id = uuid4()
    campaign_id = uuid4()
    task_id = uuid4()
    approval_id = uuid4()
    publication_task_id = uuid4()
    publication_approval_id = uuid4()
    failed_publication_id = uuid4()
    unapproved_publication_id = uuid4()
    created_asset_id: UUID | None = None
    account_id: UUID | None = None
    import_id: UUID | None = None
    null_domain_account_ids: list[UUID] = []
    null_domain_import_id: UUID | None = None
    try:
        pool = await database.pool()
        await pool.execute(
            """insert into public.artifacts(
                 id,organization_id,name,kind,storage_bucket,storage_path,mime_type,size_bytes,
                 checksum_sha256,created_by,quarantine_status
               ) values($1,$2,'integration-policy.txt','upload','artifacts',$3,'text/plain',42,$4,$5,'clean')""",
            artifact_id,
            ATLAS_ORGANIZATION_ID,
            f"{ATLAS_ORGANIZATION_ID}/{ATLAS_OWNER_ID}/{artifact_id}/integration-policy.txt",
            "a" * 64,
            ATLAS_OWNER_ID,
        )
        upload_payload = KnowledgeUploadRequest(
            file_ref=str(artifact_id),
            classification="medium",
            visibility="tenant",
            title="Integration policy",
        )
        upload_key = f"integration-knowledge-{memory_id}"
        uploads = await asyncio.gather(
            repo.upload_document(ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, upload_payload, upload_key),
            repo.upload_document(ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, upload_payload, upload_key),
        )
        assert sorted(item["replayed"] for item in uploads) == [False, True]
        assert len({item["documentId"] for item in uploads}) == 1
        upload = uploads[0]
        document_id = UUID(str(upload["documentId"]))
        await pool.execute(
            "update public.knowledge_documents set review_status='approved' where id=$1",
            document_id,
        )
        embedding = [1.0, *([0.0] * 1535)]
        vector = "[" + ",".join(str(item) for item in embedding) + "]"
        await pool.execute(
            """insert into public.knowledge_chunks(
                 organization_id,document_id,ordinal,content,embedding,metadata
               ) values($1,$2,0,'renewal policy integration evidence',$3::extensions.vector,'{}')
               on conflict(document_id,ordinal) do update
                 set content=excluded.content,embedding=excluded.embedding""",
            ATLAS_ORGANIZATION_ID,
            document_id,
            vector,
        )
        documents = await repo.documents(
            ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, "approved", None, 10
        )
        assert any(item.id == document_id for item in documents["documents"])
        search = await repo.semantic_search(
            ATLAS_OWNER_ID,
            ATLAS_ORGANIZATION_ID,
            MemberRole.OWNER,
            SemanticSearchRequest(
                query="renewal policy",
                top_k=5,
                debug=True,
                filters={"classification": "medium", "embedding": embedding, "threshold": 0.9},
            ),
        )
        assert search["results"][0]["source"]["documentId"] == document_id

        await pool.execute(
            """insert into public.memory_items(id,organization_id,kind,content,source_reference,
                 confidence,review_status,created_by) values($1,$2,'fact','renew annually',$3::jsonb,
                 95,'approved',$4)""",
            memory_id,
            ATLAS_ORGANIZATION_ID,
            json.dumps({"documentId": str(document_id)}),
            ATLAS_OWNER_ID,
        )
        memories = await repo.memory_items(
            ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, "fact", "approved", 10
        )
        assert any(item.id == memory_id for item in memories["items"])

        crm_payload = CrmImportRequest(
            source="integration",
            rows=[
                {
                    "accountName": "Integration Account",
                    "domain": f"integration-{memory_id}.bighead.dev",
                    "contactName": "Integration Contact",
                    "email": f"integration-{memory_id}@example.com",
                    "consentStatus": "granted",
                    "legalBasis": "legitimate_interest",
                    "createLead": True,
                    "icpScore": 88,
                    "scoreFactors": {"fit": "high"},
                    "nextAction": "send proposal",
                }
            ],
            consent_basis="legitimate_interest",
        )
        crm_key = f"integration-crm-{memory_id}"
        imports = await asyncio.gather(
            repo.crm_import(
                ATLAS_ANALYST_ID,
                ATLAS_ORGANIZATION_ID,
                MemberRole.ANALYST,
                crm_payload,
                crm_key,
            ),
            repo.crm_import(
                ATLAS_ANALYST_ID,
                ATLAS_ORGANIZATION_ID,
                MemberRole.ANALYST,
                crm_payload,
                crm_key,
            ),
        )
        assert sorted(item["replayed"] for item in imports) == [False, True]
        imported = imports[0]
        import_id = UUID(str(imported["importId"]))
        account_id = UUID(imported["dedupePreview"][0]["accountId"])
        contact_id = UUID(imported["dedupePreview"][0]["contactId"])
        lead_id = UUID(imported["dedupePreview"][0]["leadId"])
        null_domain_import = await repo.crm_import(
            ATLAS_ANALYST_ID,
            ATLAS_ORGANIZATION_ID,
            MemberRole.ANALYST,
            CrmImportRequest(
                source="integration-null-domain",
                rows=[
                    {"accountName": "No domain A", "consentStatus": "denied"},
                    {"accountName": "No domain B", "consentStatus": "denied"},
                ],
                consent_basis="legitimate_interest",
            ),
            f"integration-null-domain-{memory_id}",
        )
        null_domain_import_id = UUID(str(null_domain_import["importId"]))
        null_domain_account_ids = [
            UUID(item["accountId"]) for item in null_domain_import["dedupePreview"]
        ]
        assert len(set(null_domain_account_ids)) == 2
        await pool.execute(
            "update public.organization_members set status='suspended' where organization_id=$1 and user_id=$2",
            ATLAS_ORGANIZATION_ID,
            ATLAS_ANALYST_ID,
        )
        with pytest.raises(HTTPException) as replay_error:
            await repo.crm_import(
                ATLAS_ANALYST_ID,
                ATLAS_ORGANIZATION_ID,
                MemberRole.ANALYST,
                crm_payload,
                crm_key,
            )
        assert replay_error.value.status_code == 403
        await pool.execute(
            "update public.organization_members set status='active' where organization_id=$1 and user_id=$2",
            ATLAS_ORGANIZATION_ID,
            ATLAS_ANALYST_ID,
        )
        await pool.execute(
            """insert into public.lead_signals(organization_id,lead_id,signal_type,strength,
                 source,occurred_at) values($1,$2,'intent',90,'integration',now())""",
            ATLAS_ORGANIZATION_ID,
            lead_id,
        )
        assert (await repo.leads(ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, "new", None, 10))["items"][
            0
        ].id == lead_id
        assert (await repo.lead(ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, lead_id))["signals"]

        await pool.execute(
            """insert into public.opportunities(id,organization_id,lead_id,account_id,name,stage,
                 amount,probability) values($1,$2,$3,$4,'Integration renewal','qualification',null,30)""",
            opportunity_id,
            ATLAS_ORGANIZATION_ID,
            lead_id,
            account_id,
        )
        with pytest.raises(HTTPException) as missing_stage_fields:
            await repo.opportunity_stage(
                ATLAS_OWNER_ID,
                ATLAS_ORGANIZATION_ID,
                MemberRole.OWNER,
                opportunity_id,
                OpportunityStageRequest(target_stage="proposal"),
            )
        assert missing_stage_fields.value.status_code == 422
        assert (
            await pool.fetchval(
                "select stage from public.opportunities where id=$1", opportunity_id
            )
            == "qualification"
        )
        with pytest.raises(HTTPException) as untrusted_required_fields:
            await repo.opportunity_stage(
                ATLAS_OWNER_ID,
                ATLAS_ORGANIZATION_ID,
                MemberRole.OWNER,
                opportunity_id,
                OpportunityStageRequest(
                    target_stage="proposal",
                    required_fields={"amount": 1000},
                ),
            )
        assert untrusted_required_fields.value.status_code == 422
        moved = await repo.opportunity_stage(
            ATLAS_OWNER_ID,
            ATLAS_ORGANIZATION_ID,
            MemberRole.OWNER,
            opportunity_id,
            OpportunityStageRequest(target_stage="proposal", amount=1000, probability=60),
        )
        assert moved["opportunity"].stage == "proposal"
        with pytest.raises(HTTPException) as missing_loss_reason:
            await repo.opportunity_stage(
                ATLAS_OWNER_ID,
                ATLAS_ORGANIZATION_ID,
                MemberRole.OWNER,
                opportunity_id,
                OpportunityStageRequest(target_stage="lost"),
            )
        assert missing_loss_reason.value.status_code == 422
        lost = await repo.opportunity_stage(
            ATLAS_OWNER_ID,
            ATLAS_ORGANIZATION_ID,
            MemberRole.OWNER,
            opportunity_id,
            OpportunityStageRequest(target_stage="lost", loss_reason="budget frozen"),
        )
        assert lost["opportunity"].stage == "lost"
        authoritative = await pool.fetchrow(
            "select amount,loss_reason,closed_at from public.opportunities where id=$1",
            opportunity_id,
        )
        assert authoritative["amount"] == 1000
        assert authoritative["loss_reason"] == "budget frozen"
        assert authoritative["closed_at"] is not None

        await pool.execute(
            "insert into public.campaigns(id,organization_id,name,status) values($1,$2,'Integration campaign','active')",
            campaign_id,
            ATLAS_ORGANIZATION_ID,
        )
        await pool.execute(
            """insert into public.tasks(id,organization_id,title,objective,status,requester_id)
               values($1,$2,'Approve integration content','Verify publication policy','ready_for_review',$3)""",
            task_id,
            ATLAS_ORGANIZATION_ID,
            ATLAS_OWNER_ID,
        )
        await pool.execute(
            """insert into public.approval_requests(
                 id,organization_id,task_id,artifact_id,requested_by,assigned_to,status,risk_level
               ) values($1,$2,$3,$4,$5,$6,'pending','medium')""",
            approval_id,
            ATLAS_ORGANIZATION_ID,
            task_id,
            artifact_id,
            ATLAS_OWNER_ID,
            ATLAS_REVIEWER_ID,
        )
        await pool.execute(
            """insert into public.tasks(id,organization_id,title,objective,status,requester_id)
               values($1,$2,'Approve integration publication','Verify exact publication','ready_for_review',$3)""",
            publication_task_id,
            ATLAS_ORGANIZATION_ID,
            ATLAS_OWNER_ID,
        )
        await pool.execute(
            """insert into public.approval_requests(
                 id,organization_id,task_id,artifact_id,requested_by,assigned_to,status,risk_level
               ) values($1,$2,$3,$4,$5,$6,'pending','medium')""",
            publication_approval_id,
            ATLAS_ORGANIZATION_ID,
            publication_task_id,
            artifact_id,
            ATLAS_OWNER_ID,
            ATLAS_REVIEWER_ID,
        )
        assert (await repo.campaigns(ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, "active", None, 10))[
            "campaigns"
        ]
        asset_payload = ContentAssetCreateRequest(
            brief="Integration launch",
            channels=["linkedin"],
            campaign_id=campaign_id,
            task_id=task_id,
            approval_request_id=approval_id,
        )
        asset_key = f"integration-asset-{campaign_id}"
        assets = await asyncio.gather(
            repo.create_content_asset(
                ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, asset_payload, asset_key
            ),
            repo.create_content_asset(
                ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, asset_payload, asset_key
            ),
        )
        assert sorted(item["replayed"] for item in assets) == [False, True]
        created = assets[0]
        created_asset_id = created["asset"].id
        assert (
            await pool.fetchval(
                "select approval_request_id from public.content_assets where id=$1",
                created_asset_id,
            )
            == approval_id
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await pool.execute(
                """insert into public.content_assets(
                     organization_id,task_id,title,content_type,status,body,approval_request_id,
                     approval_payload_hash)
                   values($1,$2,'Wrong approval subject','publication','draft',$3::jsonb,$4,$5)""",
                ATLAS_ORGANIZATION_ID,
                publication_task_id,
                json.dumps({"brief": "not the approved task"}),
                approval_id,
                _fingerprint({"brief": "not the approved task"}),
            )
        assert (await repo.content_assets(ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, 20))["assets"]

        await pool.execute(
            """insert into public.approval_decisions(
                 organization_id,approval_request_id,decision,decided_by,comment
               ) values($1,$2,'approved',$3,'Integration approval')""",
            ATLAS_ORGANIZATION_ID,
            approval_id,
            ATLAS_REVIEWER_ID,
        )
        await pool.execute(
            "update public.approval_requests set status='approved',decided_at=now() where id=$1",
            approval_id,
        )

        publication_body = {"publication_payload": {"body": "preserved"}}
        await pool.execute(
            """insert into public.content_assets(id,organization_id,campaign_id,task_id,title,
                 content_type,status,body,channel,approval_request_id,approval_payload_hash)
               values($1,$2,$3,$4,'Failed integration publication','publication',
                 'failed',$5::jsonb,'linkedin',$6,$7)""",
            failed_publication_id,
            ATLAS_ORGANIZATION_ID,
            campaign_id,
            publication_task_id,
            json.dumps(publication_body),
            publication_approval_id,
            _fingerprint(publication_body),
        )
        await pool.execute(
            """insert into public.approval_decisions(
                 organization_id,approval_request_id,decision,decided_by,comment
               ) values($1,$2,'approved',$3,'Exact publication approval')""",
            ATLAS_ORGANIZATION_ID,
            publication_approval_id,
            ATLAS_REVIEWER_ID,
        )
        await pool.execute(
            "update public.approval_requests set status='approved',decided_at=now() where id=$1",
            publication_approval_id,
        )
        retried = await repo.retry_publication(
            ATLAS_OWNER_ID,
            ATLAS_ORGANIZATION_ID,
            failed_publication_id,
            PublicationRetryRequest(channel="linkedin", reason="provider recovered"),
            f"integration-retry-{failed_publication_id}",
        )
        assert retried["preservedPayload"] == {"body": "preserved"}
        assert retried["providerAttempt"]["status"] == "queued"
        replayed_retry = await repo.retry_publication(
            ATLAS_OWNER_ID,
            ATLAS_ORGANIZATION_ID,
            failed_publication_id,
            PublicationRetryRequest(channel="linkedin", reason="provider recovered"),
            f"integration-retry-{failed_publication_id}",
        )
        assert replayed_retry["replayed"] is True
        assert replayed_retry["publication"]["channel"] == "linkedin"
        with pytest.raises(HTTPException) as retry_conflict:
            await repo.retry_publication(
                ATLAS_OWNER_ID,
                ATLAS_ORGANIZATION_ID,
                failed_publication_id,
                PublicationRetryRequest(channel="email", reason="different payload"),
                f"integration-retry-{failed_publication_id}",
            )
        assert retry_conflict.value.status_code == 409
        assert (
            await pool.fetchval(
                "select count(*) from private.publication_attempts where content_asset_id=$1",
                failed_publication_id,
            )
            == 1
        )
        assert "publication_attempts" not in (
            await pool.fetchval(
                "select body from public.content_assets where id=$1", failed_publication_id
            )
        )
        async with database.authenticated(ATLAS_MEMBER_ID, ATLAS_ORGANIZATION_ID) as member_conn:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await member_conn.execute(
                    "update public.content_assets set status='published',body='{}' where id=$1",
                    failed_publication_id,
                )
        async with database.authenticated(ATLAS_MEMBER_ID, ATLAS_ORGANIZATION_ID) as member_conn:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await member_conn.fetch(
                    "select * from private.publication_attempts where content_asset_id=$1",
                    failed_publication_id,
                )
        await pool.execute(
            """insert into public.content_assets(id,organization_id,campaign_id,title,content_type,
                 status,body,channel) values($1,$2,$3,'Unapproved publication','publication',
                 'failed',$4::jsonb,'linkedin')""",
            unapproved_publication_id,
            ATLAS_ORGANIZATION_ID,
            campaign_id,
            json.dumps({"approval_request_id": str(approval_id)}),
        )
        # approval_id is approved but belongs to created_asset_id; forged JSON cannot rebind it.
        with pytest.raises(HTTPException) as approval_error:
            await repo.retry_publication(
                ATLAS_OWNER_ID,
                ATLAS_ORGANIZATION_ID,
                unapproved_publication_id,
                PublicationRetryRequest(channel="linkedin", reason="must not bypass approval"),
                f"integration-unapproved-{unapproved_publication_id}",
            )
        assert approval_error.value.status_code == 409
    finally:
        pool = await database.pool()
        await pool.execute(
            "update public.organization_members set status='active' where organization_id=$1 and user_id=$2",
            ATLAS_ORGANIZATION_ID,
            ATLAS_ANALYST_ID,
        )
        aggregate_ids = [
            item
            for item in (
                document_id,
                account_id,
                import_id,
                null_domain_import_id,
                opportunity_id,
                campaign_id,
                failed_publication_id,
                unapproved_publication_id,
                created_asset_id,
            )
            if item is not None
        ]
        if aggregate_ids:
            await pool.execute(
                "delete from public.event_outbox where organization_id=$1 and aggregate_id=any($2::uuid[])",
                ATLAS_ORGANIZATION_ID,
                aggregate_ids,
            )
        await pool.execute("delete from public.memory_items where id=$1", memory_id)
        async with pool.acquire() as cleanup_conn:
            try:
                await cleanup_conn.execute("set session_replication_role = replica")
                await cleanup_conn.execute(
                    "delete from public.approval_decisions where approval_request_id=any($1::uuid[])",
                    [approval_id, publication_approval_id],
                )
            finally:
                await cleanup_conn.execute("set session_replication_role = origin")
        await pool.execute(
            "delete from public.content_assets where id=any($1::uuid[])",
            [
                failed_publication_id,
                unapproved_publication_id,
                *([created_asset_id] if created_asset_id else []),
            ],
        )
        await pool.execute("delete from public.campaigns where id=$1", campaign_id)
        await pool.execute("delete from public.approval_requests where id=$1", approval_id)
        await pool.execute(
            "delete from public.approval_requests where id=$1", publication_approval_id
        )
        await pool.execute("delete from public.tasks where id=$1", task_id)
        await pool.execute("delete from public.tasks where id=$1", publication_task_id)
        await pool.execute("delete from public.opportunities where id=$1", opportunity_id)
        if lead_id:
            await pool.execute("delete from public.leads where id=$1", lead_id)
        if contact_id:
            await pool.execute("delete from public.crm_contacts where id=$1", contact_id)
        if account_id:
            await pool.execute("delete from public.crm_accounts where id=$1", account_id)
        if null_domain_account_ids:
            await pool.execute(
                "delete from public.crm_accounts where id=any($1::uuid[])",
                null_domain_account_ids,
            )
        if document_id:
            await pool.execute("delete from public.knowledge_documents where id=$1", document_id)
        await pool.execute("delete from public.artifacts where id=$1", artifact_id)
        await database.close()


@pytest.mark.asyncio
async def test_real_privacy_request_replay_and_authorized_export() -> None:
    database = Database(os.environ["SUPABASE_INTEGRATION_DATABASE_URL"])
    repo = PostgresAdministrationRepository(database, SignedPrivacyStorage())
    key = f"privacy-integration-{uuid4()}"
    request_id: UUID | None = None
    try:
        payload = PrivacyRequestCreateRequest(
            subject_user_id=ATLAS_MEMBER_ID, request_type="export"
        )
        created = await repo.create_privacy_request(
            ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, key, payload
        )
        replay = await repo.create_privacy_request(
            ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, key, payload
        )
        request_id = created["request"]["id"]
        assert replay["replayed"] is True and replay["request"]["id"] == request_id
        listed = await repo.privacy_requests(ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID)
        assert any(item["id"] == request_id for item in listed["items"])
        pool = await database.pool()
        path = f"{ATLAS_ORGANIZATION_ID}/privacy-exports/{request_id}.json"
        await pool.execute(
            """update private.privacy_requests set status='completed',completed_at=now(),
                      evidence=jsonb_build_object('exportPath',$2::text) where id=$1""",
            request_id,
            path,
        )
        exported = await repo.privacy_export(ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, request_id)
        assert exported["downloadUrl"].endswith(path)
        with pytest.raises(HTTPException) as unauthorized:
            await repo.privacy_export(ATLAS_MEMBER_ID, ATLAS_ORGANIZATION_ID, request_id)
        assert unauthorized.value.status_code == 403
    finally:
        pool = await database.pool()
        if request_id:
            await pool.execute("delete from public.event_outbox where aggregate_id=$1", request_id)
            await pool.execute("delete from private.privacy_requests where id=$1", request_id)
        await database.close()


@pytest.mark.asyncio
async def test_real_governance_replay_portal_and_last_owner_concurrency() -> None:
    database = Database(os.environ["SUPABASE_INTEGRATION_DATABASE_URL"])
    repo = PostgresGovernanceRepository(database, "integration-portal-pepper")
    workflow_id, version_id, playbook_id = uuid4(), uuid4(), uuid4()
    approval_task_id, approval_id, link_id = uuid4(), uuid4(), uuid4()
    temporary_org_id = uuid4()
    token = f"portal-{uuid4()}"
    token_hash = hashlib.sha256(f"integration-portal-pepper:{token}".encode()).hexdigest()
    try:
        pool = await database.pool()
        await pool.execute(
            "insert into public.workflows(id,organization_id,name,slug,owner_user_id) values($1,$2,'Integration workflow',$3,$4)",
            workflow_id,
            ATLAS_ORGANIZATION_ID,
            f"integration-{workflow_id}",
            ATLAS_OWNER_ID,
        )
        await pool.execute(
            "insert into public.workflow_versions(id,organization_id,workflow_id,version,definition,created_by) values($1,$2,$3,1,'{}',$4)",
            version_id,
            ATLAS_ORGANIZATION_ID,
            workflow_id,
            ATLAS_OWNER_ID,
        )
        await pool.execute(
            "insert into public.playbooks(id,organization_id,workflow_version_id,name,default_inputs) values($1,$2,$3,'Integration playbook','{\"required\":[\"goal\"]}')",
            playbook_id,
            ATLAS_ORGANIZATION_ID,
            version_id,
        )
        key = f"playbook-integration-{playbook_id}"
        payload = PlaybookInstantiateRequest(
            context={"source": "integration"}, owner_id=ATLAS_OWNER_ID, parameters={"goal": "test"}
        )
        with pytest.raises(HTTPException) as cross_tenant_owner:
            await repo.instantiate(
                ATLAS_MEMBER_ID,
                ATLAS_ORGANIZATION_ID,
                playbook_id,
                f"cross-tenant-owner-{playbook_id}",
                payload.model_copy(update={"owner_id": BEACON_OWNER_ID}),
            )
        assert cross_tenant_owner.value.status_code == 422
        instantiated = await asyncio.gather(
            repo.instantiate(ATLAS_MEMBER_ID, ATLAS_ORGANIZATION_ID, playbook_id, key, payload),
            repo.instantiate(ATLAS_MEMBER_ID, ATLAS_ORGANIZATION_ID, playbook_id, key, payload),
        )
        assert instantiated[0].task_id == instantiated[1].task_id
        versions = await repo.workflow_versions(
            ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, workflow_id, None, True
        )
        assert versions["versions"][0]["rollback_safe"] is False
        rolled_back = await repo.rollback_workflow(
            ATLAS_OWNER_ID,
            ATLAS_ORGANIZATION_ID,
            workflow_id,
            WorkflowRollbackRequest(target_version=1, expected_latest_version=1),
        )
        assert rolled_back["version"]["version"] == 2
        assert (
            await pool.fetchval(
                "select workflow_version_id=$2 from public.runs where id=$1",
                instantiated[0].workflow_instance_id,
                version_id,
            )
            is True
        )
        await pool.execute(
            "update public.organization_members set status='suspended' where organization_id=$1 and user_id=$2",
            ATLAS_ORGANIZATION_ID,
            ATLAS_MEMBER_ID,
        )
        with pytest.raises(HTTPException) as replay_denied:
            await repo.instantiate(
                ATLAS_MEMBER_ID, ATLAS_ORGANIZATION_ID, playbook_id, key, payload
            )
        assert replay_denied.value.status_code == 403
        await pool.execute(
            "update public.organization_members set status='active' where organization_id=$1 and user_id=$2",
            ATLAS_ORGANIZATION_ID,
            ATLAS_MEMBER_ID,
        )

        await pool.execute(
            "insert into public.tasks(id,organization_id,title,objective,status,requester_id) values($1,$2,'Portal approval','External decision','waiting_human',$3)",
            approval_task_id,
            ATLAS_ORGANIZATION_ID,
            ATLAS_OWNER_ID,
        )
        await pool.execute(
            "insert into public.runs(organization_id,task_id,status,idempotency_key) values($1,$2,'waiting',$3)",
            ATLAS_ORGANIZATION_ID,
            approval_task_id,
            f"waiting-{approval_task_id}",
        )
        await pool.execute(
            "insert into public.approval_requests(id,organization_id,task_id,requested_by,status,risk_level) values($1,$2,$3,$4,'pending','high')",
            approval_id,
            ATLAS_ORGANIZATION_ID,
            approval_task_id,
            ATLAS_OWNER_ID,
        )
        await pool.execute(
            "insert into public.external_approval_links(id,organization_id,approval_request_id,token_hash,expires_at,created_by) values($1,$2,$3,$4,now()+interval '1 hour',$5)",
            link_id,
            ATLAS_ORGANIZATION_ID,
            approval_id,
            token_hash,
            ATLAS_OWNER_ID,
        )
        await repo.portal_item(token)
        await repo.portal_item(token)
        assert (
            await pool.fetchval(
                "select use_count from public.external_approval_links where id=$1", link_id
            )
            == 0
        )
        await pool.execute("update public.tasks set status='triaged' where id=$1", approval_task_id)
        with pytest.raises(HTTPException) as not_waiting:
            await repo.portal_decide(
                token,
                f"not-waiting-{approval_id}",
                PortalDecisionRequest(decision="approved", expected_round=1),
            )
        assert not_waiting.value.status_code == 409
        assert (
            await pool.fetchval(
                "select status::text from public.approval_requests where id=$1", approval_id
            )
            == "pending"
        )
        await pool.execute(
            "update public.tasks set status='waiting_human' where id=$1", approval_task_id
        )
        decision_key = f"portal-decision-{approval_id}"
        decision_payload = PortalDecisionRequest(decision="approved", expected_round=1)
        decision = await repo.portal_decide(
            token,
            decision_key,
            decision_payload,
        )
        assert decision.round_result == "approved"
        replayed_decision = await repo.portal_decide(token, decision_key, decision_payload)
        assert replayed_decision.approval["id"] == approval_id
        with pytest.raises(HTTPException) as replay_conflict:
            await repo.portal_decide(
                token,
                decision_key,
                decision_payload.model_copy(update={"comment": "changed replay payload"}),
            )
        assert replay_conflict.value.status_code == 409
        assert (
            await pool.fetchval(
                "select use_count from public.external_approval_links where id=$1", link_id
            )
            == 1
        )
        assert (
            await pool.fetchval(
                "select status::text from public.tasks where id=$1", approval_task_id
            )
            == "approved"
        )
        assert (
            await pool.fetchval(
                "select status::text from public.runs where task_id=$1", approval_task_id
            )
            == "queued"
        )
        for attempt in range(6):
            with pytest.raises(HTTPException) as invalid_attempt:
                await repo.portal_decide(
                    token,
                    f"invalid-{attempt}-{approval_id}",
                    PortalDecisionRequest(decision="changes_requested", expected_round=1),
                )
            assert invalid_attempt.value.status_code == 410
        with pytest.raises(HTTPException) as rate_limited:
            await repo.portal_decide(
                token,
                f"rate-limited-{approval_id}",
                PortalDecisionRequest(decision="changes_requested", expected_round=1),
            )
        assert rate_limited.value.status_code == 429

        await pool.execute(
            "insert into public.organizations(id,name,slug,created_by) values($1,'Owner race',$2,$3)",
            temporary_org_id,
            f"owner-race-{temporary_org_id}",
            ATLAS_OWNER_ID,
        )
        await pool.executemany(
            "insert into public.organization_members(organization_id,user_id,role,status) values($1,$2,'owner','active')",
            [(temporary_org_id, ATLAS_OWNER_ID), (temporary_org_id, ATLAS_REVIEWER_ID)],
        )
        results = await asyncio.gather(
            pool.execute(
                "update public.organization_members set role='admin' where organization_id=$1 and user_id=$2",
                temporary_org_id,
                ATLAS_OWNER_ID,
            ),
            pool.execute(
                "update public.organization_members set role='admin' where organization_id=$1 and user_id=$2",
                temporary_org_id,
                ATLAS_REVIEWER_ID,
            ),
            return_exceptions=True,
        )
        assert sum(isinstance(item, Exception) for item in results) == 1
        assert (
            await pool.fetchval(
                "select count(*) from public.organization_members where organization_id=$1 and role='owner' and status='active'",
                temporary_org_id,
            )
            == 1
        )
    finally:
        pool = await database.pool()
        await pool.execute(
            "update public.organization_members set status='active' where organization_id=$1 and user_id=$2",
            ATLAS_ORGANIZATION_ID,
            ATLAS_MEMBER_ID,
        )
        async with pool.acquire() as cleanup_conn:
            try:
                await cleanup_conn.execute("set session_replication_role = replica")
                await cleanup_conn.execute(
                    "delete from public.organization_members where organization_id=$1",
                    temporary_org_id,
                )
                await cleanup_conn.execute(
                    "delete from public.organizations where id=$1", temporary_org_id
                )
                await cleanup_conn.execute(
                    "delete from public.approval_decisions where approval_request_id=$1",
                    approval_id,
                )
            finally:
                await cleanup_conn.execute("set session_replication_role = origin")
        await pool.execute(
            "delete from private.portal_access_events where token_hash=$1", token_hash
        )
        await pool.execute("delete from public.approval_requests where id=$1", approval_id)
        await pool.execute("delete from public.tasks where id=$1", approval_task_id)
        await pool.execute(
            "delete from public.tasks where metadata->>'playbook_id'=$1", str(playbook_id)
        )
        await pool.execute("delete from public.playbooks where id=$1", playbook_id)
        async with pool.acquire() as cleanup_conn:
            try:
                await cleanup_conn.execute("set session_replication_role = replica")
                await cleanup_conn.execute(
                    "delete from public.workflow_versions where workflow_id=$1", workflow_id
                )
                await cleanup_conn.execute(
                    "delete from public.workflows where id=$1", workflow_id
                )
            finally:
                await cleanup_conn.execute("set session_replication_role = origin")
        await database.close()
