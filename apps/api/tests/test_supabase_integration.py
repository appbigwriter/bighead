# ruff: noqa: E501
import asyncio
import hashlib
import json
import os
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
import pytest
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
from bighead_api.commercial.service import PostgresCommercialRepository
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
        assert [(item.organization_id, item.role.value) for item in memberships] == [
            (ATLAS_ORGANIZATION_ID, "owner")
        ]

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
                 amount,probability) values($1,$2,$3,$4,'Integration renewal','qualification',1000,30)""",
            opportunity_id,
            ATLAS_ORGANIZATION_ID,
            lead_id,
            account_id,
        )
        moved = await repo.opportunity_stage(
            ATLAS_OWNER_ID,
            ATLAS_ORGANIZATION_ID,
            MemberRole.OWNER,
            opportunity_id,
            OpportunityStageRequest(
                target_stage="proposal",
                required_fields={"amount": 1000},
                forecast={"probability": 60},
            ),
        )
        assert moved["opportunity"].stage == "proposal"

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
                 id,organization_id,task_id,artifact_id,requested_by,assigned_to,status,risk_level,decided_at
               ) values($1,$2,$3,$4,$5,$6,'approved','medium',now())""",
            approval_id,
            ATLAS_ORGANIZATION_ID,
            task_id,
            artifact_id,
            ATLAS_OWNER_ID,
            ATLAS_REVIEWER_ID,
        )
        await pool.execute(
            """insert into public.approval_decisions(
                 organization_id,approval_request_id,decision,decided_by,comment
               ) values($1,$2,'approved',$3,'Integration approval')""",
            ATLAS_ORGANIZATION_ID,
            approval_id,
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
                 id,organization_id,task_id,artifact_id,requested_by,assigned_to,status,risk_level,decided_at
               ) values($1,$2,$3,$4,$5,$6,'approved','medium',now())""",
            publication_approval_id,
            ATLAS_ORGANIZATION_ID,
            publication_task_id,
            artifact_id,
            ATLAS_OWNER_ID,
            ATLAS_REVIEWER_ID,
        )
        await pool.execute(
            """insert into public.approval_decisions(
                 organization_id,approval_request_id,decision,decided_by,comment
               ) values($1,$2,'approved',$3,'Exact publication approval')""",
            ATLAS_ORGANIZATION_ID,
            publication_approval_id,
            ATLAS_REVIEWER_ID,
        )
        assert (await repo.campaigns(ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, "active", None, 10))[
            "campaigns"
        ]
        asset_payload = ContentAssetCreateRequest(
            brief="Integration launch",
            channels=["linkedin"],
            campaign_id=campaign_id,
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
        assert (await repo.content_assets(ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, 20))["assets"]

        await pool.execute(
            """insert into public.content_assets(id,organization_id,campaign_id,title,content_type,
                 status,body,channel,approval_request_id)
               values($1,$2,$3,'Failed integration publication','publication',
                 'failed',$4::jsonb,'linkedin',$5)""",
            failed_publication_id,
            ATLAS_ORGANIZATION_ID,
            campaign_id,
            json.dumps(
                {
                    "publication_payload": {"body": "preserved"},
                }
            ),
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
        await pool.execute(
            """insert into public.content_assets(id,organization_id,campaign_id,title,content_type,
                 status,body,channel) values($1,$2,$3,'Unapproved publication','publication',
                 'failed',$4::jsonb,'linkedin')""",
            unapproved_publication_id,
            ATLAS_ORGANIZATION_ID,
            campaign_id,
            json.dumps({"approval_request_id": str(approval_id)}),
        )
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
        if document_id:
            await pool.execute("delete from public.knowledge_documents where id=$1", document_id)
        await pool.execute("delete from public.artifacts where id=$1", artifact_id)
        await database.close()
