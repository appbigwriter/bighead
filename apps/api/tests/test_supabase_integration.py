# ruff: noqa: E501
import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
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
    MessagePatchRequest,
    RoomCreateRequest,
    RoomMemberDelta,
    RoomPatchRequest,
    TaskAssigneePatchRequest,
    TaskCreateRequest,
    TaskStatus,
    TaskTransitionRequest,
)
from bighead_api.collaboration.service import PostgresCollaborationRepository
from bighead_api.commercial.models import (
    ContentAssetCreateRequest,
    CrmImportRequest,
    CrmImportResumeRequest,
    CrmImportResumeRow,
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
ATLAS_EXPERIMENT_ID = UUID("e7100000-0000-0000-0000-000000000001")
BEACON_ADMIN_ID = UUID("d2000000-0000-0000-0000-000000000002")
BEACON_MEMBER_ID = UUID("d2000000-0000-0000-0000-000000000004")


class SignedPrivacyStorage:
    async def signed_upload(self, path: str) -> tuple[str, datetime]:
        return f"https://storage.example.test/upload/{path}", datetime.now(UTC)

    async def signed_download(self, path: str) -> tuple[str, datetime]:
        return f"https://storage.example.test/download/{path}", datetime.now(UTC)


@pytest.mark.asyncio
async def test_invite_lifecycle_is_atomic_for_used_expired_and_revoked_tokens() -> None:
    database = Database(os.environ["SUPABASE_INTEGRATION_DATABASE_URL"])
    repo = PostgresIdentityRepository(database)
    pool = await database.pool()
    used = await repo.create_invite(
        ATLAS_ORGANIZATION_ID,
        ATLAS_OWNER_ID,
        "owner@beacon.bighead.dev",
        MemberRole.MEMBER,
        24,
    )
    assert used.token is not None
    expired_token = f"expired-{uuid4()}"
    revoked_token = f"revoked-{uuid4()}"
    await pool.execute(
        """insert into public.organization_invites(
               organization_id,email,role,token_hash,invited_by,created_at,expires_at)
             values($1,'admin@beacon.bighead.dev','member',$2,$3,now()-interval '2 days',
                    now()-interval '1 day')""",
        ATLAS_ORGANIZATION_ID,
        hashlib.sha256(expired_token.encode()).hexdigest(),
        ATLAS_OWNER_ID,
    )
    await pool.execute(
        """insert into public.organization_invites(
               organization_id,email,role,token_hash,invited_by,expires_at,revoked_at)
             values($1,'member@beacon.bighead.dev','member',$2,$3,now()+interval '1 day',now())""",
        ATLAS_ORGANIZATION_ID,
        hashlib.sha256(revoked_token.encode()).hexdigest(),
        ATLAS_OWNER_ID,
    )
    try:
        outcomes = await asyncio.gather(
            repo.accept_invite(
                used.token,
                BEACON_OWNER_ID,
                "owner@beacon.bighead.dev",
                "Beacon Owner",
            ),
            repo.accept_invite(
                used.token,
                BEACON_OWNER_ID,
                "owner@beacon.bighead.dev",
                "Beacon Owner",
            ),
            return_exceptions=True,
        )
        assert sum(not isinstance(item, Exception) for item in outcomes) == 1
        conflicts = [item for item in outcomes if isinstance(item, HTTPException)]
        assert len(conflicts) == 1 and conflicts[0].status_code == 409

        for token, user_id, email in (
            (expired_token, BEACON_ADMIN_ID, "admin@beacon.bighead.dev"),
            (revoked_token, BEACON_MEMBER_ID, "member@beacon.bighead.dev"),
        ):
            with pytest.raises(HTTPException) as failure:
                await repo.accept_invite(token, user_id, email, "Must Not Change")
            assert failure.value.status_code == 410

        assert (
            await pool.fetchval(
                """select count(*) from public.organization_members
                 where organization_id=$1 and user_id=any($2::uuid[])""",
                ATLAS_ORGANIZATION_ID,
                [BEACON_OWNER_ID, BEACON_ADMIN_ID, BEACON_MEMBER_ID],
            )
            == 1
        )
        assert (
            await pool.fetchval(
                "select display_name from public.profiles where id=$1", BEACON_ADMIN_ID
            )
            == "Beacon Admin"
        )
        assert (
            await pool.fetchval(
                "select display_name from public.profiles where id=$1", BEACON_MEMBER_ID
            )
            == "Beacon Member"
        )
    finally:
        await pool.execute(
            """delete from public.organization_members
                 where organization_id=$1 and user_id=$2""",
            ATLAS_ORGANIZATION_ID,
            BEACON_OWNER_ID,
        )
        await pool.execute(
            """delete from public.organization_invites
                 where organization_id=$1
                   and email in ('owner@beacon.bighead.dev','admin@beacon.bighead.dev',
                                 'member@beacon.bighead.dev')""",
            ATLAS_ORGANIZATION_ID,
        )
        await database.close()


@pytest.mark.asyncio
async def test_analytics_component_records_are_tenant_scoped_and_cursor_paginated() -> None:
    database = Database(os.environ["SUPABASE_INTEGRATION_DATABASE_URL"])
    collaboration = PostgresCollaborationRepository(database)
    administration = PostgresAdministrationRepository(database, SignedPrivacyStorage())
    pool = await database.pool()
    task_ids: list[UUID] = []
    try:
        for index in range(3):
            task, _ = await collaboration.create_task(
                ATLAS_ANALYST_ID,
                ATLAS_ORGANIZATION_ID,
                TaskCreateRequest(goal=f"analytics pagination proof {index}"),
                f"analytics-record-{uuid4()}",
            )
            task_ids.append(task.id)

        start = datetime.now(UTC).replace(microsecond=0) - timedelta(days=1)
        end = datetime.now(UTC) + timedelta(days=1)
        first = await administration.analytics_summary_records(
            ATLAS_ANALYST_ID,
            ATLAS_ORGANIZATION_ID,
            "new",
            start,
            end,
            None,
            2,
        )
        assert first["total"] >= 3
        assert len(first["items"]) == 2
        assert first["nextCursor"] is not None
        second = await administration.analytics_summary_records(
            ATLAS_ANALYST_ID,
            ATLAS_ORGANIZATION_ID,
            "new",
            start,
            end,
            first["nextCursor"],
            100,
        )
        observed = {item["id"] for item in [*first["items"], *second["items"]]}
        assert set(task_ids).issubset(observed)

        beacon = await administration.analytics_summary_records(
            BEACON_OWNER_ID,
            UUID("b7200000-0000-0000-0000-000000000001"),
            "new",
            start,
            end,
            None,
            100,
        )
        assert set(task_ids).isdisjoint({item["id"] for item in beacon["items"]})
    finally:
        if task_ids:
            await pool.execute(
                "delete from public.event_outbox where aggregate_id=any($1::uuid[])", task_ids
            )
            await pool.execute("delete from public.tasks where id=any($1::uuid[])", task_ids)
        await database.close()


@pytest.mark.asyncio
async def test_experiment_start_is_concurrency_safe_and_idempotent() -> None:
    database = Database(os.environ["SUPABASE_INTEGRATION_DATABASE_URL"])
    repo = PostgresAdministrationRepository(database, SignedPrivacyStorage())
    pool = await database.pool()
    await pool.execute(
        "delete from public.event_outbox where aggregate_id=$1 and event_type='experiments.started'",
        ATLAS_EXPERIMENT_ID,
    )
    expected_updated_at = await pool.fetchval(
        "select updated_at from public.experiments where id=$1", ATLAS_EXPERIMENT_ID
    )
    try:
        results = await asyncio.gather(
            repo.start_experiment(
                ATLAS_ANALYST_ID,
                ATLAS_ORGANIZATION_ID,
                ATLAS_EXPERIMENT_ID,
                expected_updated_at,
            ),
            repo.start_experiment(
                ATLAS_ANALYST_ID,
                ATLAS_ORGANIZATION_ID,
                ATLAS_EXPERIMENT_ID,
                expected_updated_at,
            ),
        )
        assert sorted(result["replayed"] for result in results) == [False, True]
        assert all(result["experiment"]["status"] == "running" for result in results)
        assert (
            await pool.fetchval(
                """select count(*) from public.event_outbox
                    where aggregate_id=$1 and event_type='experiments.started'""",
                ATLAS_EXPERIMENT_ID,
            )
            == 1
        )
    finally:
        async with pool.acquire() as cleanup_conn:
            try:
                await cleanup_conn.execute("set session_replication_role = replica")
                await cleanup_conn.execute(
                    """update public.experiments set status='draft',starts_at=null,ends_at=null
                        where id=$1""",
                    ATLAS_EXPERIMENT_ID,
                )
            finally:
                await cleanup_conn.execute("set session_replication_role = origin")
        await pool.execute(
            "delete from public.event_outbox where aggregate_id=$1 and event_type='experiments.started'",
            ATLAS_EXPERIMENT_ID,
        )
        await database.close()


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
            RoomCreateRequest(name=f"Replay guard {uuid4()}", is_private=True),
        )
        room_id = room.id
        message = await repo.create_message(
            ATLAS_ANALYST_ID, ATLAS_ORGANIZATION_ID, room_id, message_payload
        )
        message_id = message.id
        replayed_message = await repo.create_message(
            ATLAS_ANALYST_ID, ATLAS_ORGANIZATION_ID, room_id, message_payload
        )
        assert replayed_message.id == message_id
        pool = await database.pool()
        assert (
            await pool.fetchval(
                """select count(*) from public.messages
                    where organization_id=$1 and room_id=$2 and author_user_id=$3
                      and metadata->>'client_id'=$4""",
                ATLAS_ORGANIZATION_ID,
                room_id,
                ATLAS_ANALYST_ID,
                message_payload.client_id,
            )
            == 1
        )
        with pytest.raises(HTTPException) as private_edit_denied:
            await repo.patch_message(
                ATLAS_OWNER_ID,
                ATLAS_ORGANIZATION_ID,
                room_id,
                message_id,
                MessagePatchRequest(body="tenant admin outside private room"),
            )
        assert private_edit_denied.value.status_code == 404
        with pytest.raises(HTTPException) as private_delete_denied:
            await repo.delete_message(ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, room_id, message_id)
        assert private_delete_denied.value.status_code == 404
        with pytest.raises(HTTPException) as foreign_member_denied:
            await repo.patch_room(
                ATLAS_OWNER_ID,
                ATLAS_ORGANIZATION_ID,
                room_id,
                RoomPatchRequest(
                    members_delta=[
                        RoomMemberDelta(user_id=uuid4(), action="add", is_moderator=False)
                    ]
                ),
            )
        assert foreign_member_denied.value.status_code == 422
        edited_message = await repo.patch_message(
            ATLAS_ANALYST_ID,
            ATLAS_ORGANIZATION_ID,
            room_id,
            message_id,
            MessagePatchRequest(body="replay guard edited"),
        )
        assert edited_message.edited_at is not None
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

        with pytest.raises(HTTPException) as reassignment_denied:
            await repo.reassign_task(
                ATLAS_MEMBER_ID,
                ATLAS_ORGANIZATION_ID,
                task_id,
                TaskAssigneePatchRequest(assignee_id=ATLAS_OWNER_ID, expected_version=1),
            )
        assert reassignment_denied.value.status_code == 403

        reassigned = await repo.reassign_task(
            ATLAS_ANALYST_ID,
            ATLAS_ORGANIZATION_ID,
            task_id,
            TaskAssigneePatchRequest(assignee_id=ATLAS_OWNER_ID, expected_version=1),
        )
        assert reassigned.assignee_id == ATLAS_OWNER_ID

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
                expected_version=2,
            ),
        )
        assert transitioned.status == TaskStatus.TRIAGED

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
        assert (
            await pool.fetchval(
                """select count(*) from public.event_outbox
                 where organization_id=$1 and aggregate_id=$2
                   and event_type='runs.retry.requested'""",
                ATLAS_ORGANIZATION_ID,
                retries[0].id,
            )
            == 1
        )
        assert (
            await pool.fetchval(
                """select count(*) from public.audit_log
                 where organization_id=$1 and resource_id=$2
                   and action='run.retry_requested'""",
                ATLAS_ORGANIZATION_ID,
                str(retries[0].id),
            )
            == 1
        )

        audit_actions = await pool.fetch(
            """select action from public.audit_log
                where organization_id=$1 and resource_id=any($2::text[])""",
            ATLAS_ORGANIZATION_ID,
            [str(room_id), str(message_id), str(task_id), str(retries[0].id)],
        )
        assert {row["action"] for row in audit_actions} >= {
            "room.updated",
            "message.edited",
            "task.created",
            "task.reassigned",
            "task.transitioned",
            "run.retry_requested",
        }

        deleted_message = await repo.delete_message(
            ATLAS_ANALYST_ID, ATLAS_ORGANIZATION_ID, room_id, message_id
        )
        assert deleted_message.deleted_at is not None
        assert await pool.fetchval(
            "select exists(select 1 from public.audit_log where organization_id=$1 and resource_id=$2 and action='message.deleted')",
            ATLAS_ORGANIZATION_ID,
            str(message_id),
        )

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
                    "scoreAlgorithmVersion": "icp-v2.1",
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
        partial_import = await repo.crm_import(
            ATLAS_ANALYST_ID,
            ATLAS_ORGANIZATION_ID,
            MemberRole.ANALYST,
            CrmImportRequest(
                source="integration-resume",
                rows=[
                    {
                        "accountName": "Resumable scored account",
                        "consentStatus": "granted",
                        "icpScore": 75,
                        "scoreFactors": {"fit": {"contribution": 75}},
                    }
                ],
                consent_basis="legitimate_interest",
            ),
            f"integration-resume-{memory_id}",
        )
        assert partial_import["status"] == "partial"
        resumed = await repo.resume_crm_import(
            ATLAS_ANALYST_ID,
            ATLAS_ORGANIZATION_ID,
            MemberRole.ANALYST,
            UUID(str(partial_import["importId"])),
            CrmImportResumeRequest(
                rows=[
                    CrmImportResumeRow(
                        row_number=0,
                        payload={
                            "accountName": "Resumable scored account",
                            "consentStatus": "granted",
                            "icpScore": 75,
                            "scoreFactors": {"fit": {"contribution": 75}},
                            "scoreAlgorithmVersion": "icp-v2.1",
                        },
                    )
                ]
            ),
        )
        assert resumed["status"] == "completed"
        merged = await repo.merge_crm_accounts(
            ATLAS_OWNER_ID,
            ATLAS_ORGANIZATION_ID,
            MemberRole.OWNER,
            null_domain_account_ids[0],
            null_domain_account_ids[1],
            "integration duplicate",
        )
        assert merged["targetId"] == str(null_domain_account_ids[1])
        assert await pool.fetchval(
            "select merged_into_id=$2 from public.crm_accounts where id=$1",
            null_domain_account_ids[0],
            null_domain_account_ids[1],
        )
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
        await pool.execute(
            "delete from public.crm_imports where source in ('integration','integration-null-domain','integration-resume')"
        )
        await pool.execute("delete from public.opportunities where id=$1", opportunity_id)
        if lead_id:
            await pool.execute("delete from public.leads where id=$1", lead_id)
        if contact_id:
            await pool.execute("delete from public.crm_contacts where id=$1", contact_id)
        if account_id:
            await pool.execute("delete from public.crm_accounts where id=$1", account_id)
        await pool.execute("delete from public.leads where source='integration-resume'")
        await pool.execute(
            "delete from public.crm_accounts where metadata->>'source'='integration-resume'"
        )
        if null_domain_account_ids:
            await pool.execute(
                "update public.crm_accounts set merged_into_id=null,merged_at=null where id=$1",
                null_domain_account_ids[0],
            )
            await pool.execute(
                "delete from public.crm_accounts where id=any($1::uuid[])",
                null_domain_account_ids,
            )
        if document_id:
            await pool.execute("delete from public.knowledge_documents where id=$1", document_id)
        await pool.execute("delete from public.artifacts where id=$1", artifact_id)
        await database.close()


@pytest.mark.asyncio
async def test_real_crm_resume_is_atomic_and_concurrency_safe() -> None:
    database = Database(os.environ["SUPABASE_INTEGRATION_DATABASE_URL"])
    repo = PostgresCommercialRepository(database)
    suffix = uuid4()
    source = f"resume-concurrency-{suffix}"
    import_ids: list[UUID] = []
    reindex_run_id: UUID | None = None
    try:
        pool = await database.pool()

        async def start_reindex(model: str) -> UUID:
            async with pool.acquire() as connection, connection.transaction():
                return await connection.fetchval(
                    "select private.start_embedding_reindex('integration',$1,11,null)", model
                )

        starts = await asyncio.gather(
            start_reindex(f"concurrent-a-{suffix}"),
            start_reindex(f"concurrent-b-{suffix}"),
            return_exceptions=True,
        )
        successful_starts = [item for item in starts if isinstance(item, UUID)]
        failed_starts = [item for item in starts if isinstance(item, asyncpg.PostgresError)]
        assert len(successful_starts) == 1
        assert len(failed_starts) == 1 and failed_starts[0].sqlstate == "55000"
        reindex_run_id = successful_starts[0]
        assert (
            await pool.fetchval(
                "select count(*) from private.embedding_reindex_runs where status in ('running','ready')"
            )
            == 1
        )
        target_profile_id = await pool.fetchval(
            "delete from private.embedding_reindex_runs where id=$1 returning target_profile_id",
            reindex_run_id,
        )
        await pool.execute("delete from private.embedding_profiles where id=$1", target_profile_id)
        reindex_run_id = None

        initial = await repo.crm_import(
            ATLAS_ANALYST_ID,
            ATLAS_ORGANIZATION_ID,
            MemberRole.ANALYST,
            CrmImportRequest(
                source=source,
                rows=[
                    {
                        "accountName": "Atomic resume",
                        "consentStatus": "granted",
                        "icpScore": 81,
                        "scoreFactors": {"fit": {"contribution": 81}},
                    }
                ],
                consent_basis="legitimate_interest",
            ),
            f"atomic-resume-{suffix}",
        )
        import_id = UUID(str(initial["importId"]))
        import_ids.append(import_id)
        correction = CrmImportResumeRequest(
            rows=[
                CrmImportResumeRow(
                    row_number=0,
                    payload={
                        "accountName": "Atomic resume",
                        "domain": f"atomic-{suffix}.invalid",
                        "consentStatus": "granted",
                        "icpScore": 81,
                        "scoreFactors": {"fit": {"contribution": 81}},
                        "scoreAlgorithmVersion": "icp-v2.1",
                    },
                )
            ]
        )
        identical = await asyncio.gather(
            repo.resume_crm_import(
                ATLAS_ANALYST_ID,
                ATLAS_ORGANIZATION_ID,
                MemberRole.ANALYST,
                import_id,
                correction,
            ),
            repo.resume_crm_import(
                ATLAS_ANALYST_ID,
                ATLAS_ORGANIZATION_ID,
                MemberRole.ANALYST,
                import_id,
                correction,
            ),
        )
        assert sorted(item["replayed"] for item in identical) == [False, True]
        assert (
            await pool.fetchval(
                "select attempts from public.crm_import_rows where import_id=$1 and row_number=0",
                import_id,
            )
            == 2
        )
        assert await pool.fetchval("select count(*) from public.leads where source=$1", source) == 1

        divergent_source = f"{source}-divergent"
        divergent_initial = await repo.crm_import(
            ATLAS_ANALYST_ID,
            ATLAS_ORGANIZATION_ID,
            MemberRole.ANALYST,
            CrmImportRequest(
                source=divergent_source,
                rows=[{"accountName": "Divergent", "consentStatus": "invalid"}],
                consent_basis="legitimate_interest",
            ),
            f"divergent-resume-{suffix}",
        )
        divergent_id = UUID(str(divergent_initial["importId"]))
        import_ids.append(divergent_id)

        def divergent_payload(name: str) -> CrmImportResumeRequest:
            return CrmImportResumeRequest(
                rows=[
                    CrmImportResumeRow(
                        row_number=0,
                        payload={"accountName": name, "consentStatus": "denied"},
                    )
                ]
            )

        divergent = await asyncio.gather(
            repo.resume_crm_import(
                ATLAS_ANALYST_ID,
                ATLAS_ORGANIZATION_ID,
                MemberRole.ANALYST,
                divergent_id,
                divergent_payload("Winner A"),
            ),
            repo.resume_crm_import(
                ATLAS_ANALYST_ID,
                ATLAS_ORGANIZATION_ID,
                MemberRole.ANALYST,
                divergent_id,
                divergent_payload("Winner B"),
            ),
            return_exceptions=True,
        )
        assert (
            sum(isinstance(item, HTTPException) and item.status_code == 409 for item in divergent)
            == 1
        )
        assert sum(isinstance(item, dict) and item["replayed"] is False for item in divergent) == 1
        assert (
            await pool.fetchval(
                "select attempts from public.crm_import_rows where import_id=$1 and row_number=0",
                divergent_id,
            )
            == 2
        )
    finally:
        pool = await database.pool()
        if reindex_run_id:
            target_profile_id = await pool.fetchval(
                "delete from private.embedding_reindex_runs where id=$1 returning target_profile_id",
                reindex_run_id,
            )
            if target_profile_id:
                await pool.execute(
                    "delete from private.embedding_profiles where id=$1", target_profile_id
                )
        if import_ids:
            await pool.execute(
                "delete from public.event_outbox where aggregate_id=any($1::uuid[])", import_ids
            )
            await pool.execute(
                "delete from public.crm_imports where id=any($1::uuid[])", import_ids
            )
        await pool.execute("delete from public.leads where source like $1", f"{source}%")
        await pool.execute(
            "delete from public.crm_accounts where metadata->>'source' like $1", f"{source}%"
        )
        await database.close()


@pytest.mark.asyncio
async def test_real_embedding_activation_serializes_chunk_and_memory_writes() -> None:
    database = Database(os.environ["SUPABASE_INTEGRATION_DATABASE_URL"])
    document_id = uuid4()
    inverse_chunk_id, inverse_memory_id = uuid4(), uuid4()
    run_id: UUID | None = None
    restore_run_id: UUID | None = None
    target_profile_id: UUID | None = None
    old_profile: asyncpg.Record | None = None
    original_embeddings: list[asyncpg.Record] = []
    activation_connection: asyncpg.Connection[asyncpg.Record] | None = None
    inverse_connection: asyncpg.Connection[asyncpg.Record] | None = None
    chunk_connection: asyncpg.Connection[asyncpg.Record] | None = None
    memory_connection: asyncpg.Connection[asyncpg.Record] | None = None
    activation_transaction: asyncpg.Transaction | None = None
    inverse_transaction: asyncpg.Transaction | None = None
    activation_open = False
    inverse_open = False
    writer_tasks: list[asyncio.Task[None]] = []
    try:
        pool = await database.pool()
        old_profile = await pool.fetchrow(
            """select id,provider,model_name,dimensions
                 from private.embedding_profiles where status='active'"""
        )
        assert old_profile is not None
        original_embeddings = await pool.fetch(
            """select 'knowledge_chunk'::text entity_type,id entity_id,embedding::text embedding
                 from public.knowledge_chunks
               union all
               select 'memory_item'::text entity_type,id entity_id,embedding::text embedding
                 from public.memory_items"""
        )
        await pool.execute(
            """insert into public.knowledge_documents(
                 id,organization_id,title,source_type,review_status
               ) values($1,$2,'Concurrent activation barrier','text','approved')""",
            document_id,
            ATLAS_ORGANIZATION_ID,
        )
        await pool.execute(
            """insert into public.memory_items(
                 id,organization_id,kind,content,review_status
               ) values($1,$2,'fact','existing inverse-order memory','approved')""",
            inverse_memory_id,
            ATLAS_ORGANIZATION_ID,
        )
        await pool.execute(
            """insert into public.knowledge_chunks(
                 id,organization_id,document_id,ordinal,content
               ) values($1,$2,$3,0,'existing inverse-order chunk')""",
            inverse_chunk_id,
            ATLAS_ORGANIZATION_ID,
            document_id,
        )
        run_id = await pool.fetchval(
            "select private.start_embedding_reindex('integration',$1,17,null)",
            f"activation-barrier-{uuid4()}",
        )
        target_profile_id = await pool.fetchval(
            "select target_profile_id from private.embedding_reindex_runs where id=$1", run_id
        )
        target_vector = "[1," + ",".join(["0"] * 16) + "]"
        items = await pool.fetch(
            "select entity_type,entity_id from private.embedding_reindex_items where run_id=$1",
            run_id,
        )
        for item in items:
            await pool.execute(
                "select private.complete_embedding_reindex_item($1,$2,$3,$4::extensions.vector)",
                run_id,
                item["entity_type"],
                item["entity_id"],
                target_vector,
            )
        assert (
            await pool.fetchval(
                "select status from private.embedding_reindex_runs where id=$1", run_id
            )
            == "ready"
        )
        index_commands = await pool.fetch(
            "select ddl from private.embedding_reindex_index_commands($1)", run_id
        )
        assert len(index_commands) == 2
        for command in index_commands:
            await pool.execute(command["ddl"])

        activation_connection = await pool.acquire()
        inverse_connection = await pool.acquire()
        chunk_connection = await pool.acquire()
        memory_connection = await pool.acquire()

        # These are UPDATEs of rows that activation will update itself. The
        # statement trigger must acquire the advisory lock before either tuple
        # is locked, including the inverse memory-then-chunk order.
        inverse_transaction = inverse_connection.transaction()
        await inverse_transaction.start()
        inverse_open = True
        await inverse_connection.execute(
            "update public.memory_items set content='updated before activation' where id=$1",
            inverse_memory_id,
        )
        activation_pid = await activation_connection.fetchval("select pg_backend_pid()")
        blocked_activation = asyncio.create_task(
            activation_connection.execute("select private.activate_embedding_reindex($1)", run_id)
        )
        advisory_waiting = False
        for _ in range(100):
            advisory_waiting = await pool.fetchval(
                """select exists(select 1 from pg_locks
                     where pid=$1 and locktype='advisory' and not granted)""",
                activation_pid,
            )
            if advisory_waiting:
                break
            await asyncio.sleep(0.02)
        assert advisory_waiting
        await inverse_connection.execute(
            "update public.knowledge_chunks set content='updated before activation' where id=$1",
            inverse_chunk_id,
        )
        await inverse_transaction.commit()
        inverse_open = False
        with pytest.raises(asyncpg.PostgresError) as blocked_result:
            await asyncio.wait_for(blocked_activation, timeout=5)
        assert blocked_result.value.sqlstate == "55000"
        assert (
            await pool.fetchval(
                """select count(*)::int from private.embedding_reindex_items
                     where run_id=$1 and status='pending'
                       and (entity_type,entity_id) in (
                         ('knowledge_chunk',$2::uuid),('memory_item',$3::uuid)
                       )""",
                run_id,
                inverse_chunk_id,
                inverse_memory_id,
            )
            == 2
        )
        for entity_type, entity_id in (
            ("knowledge_chunk", inverse_chunk_id),
            ("memory_item", inverse_memory_id),
        ):
            await pool.execute(
                "select private.complete_embedding_reindex_item($1,$2,$3,$4::extensions.vector)",
                run_id,
                entity_type,
                entity_id,
                target_vector,
            )
        assert (
            await pool.fetchval(
                "select status from private.embedding_reindex_runs where id=$1", run_id
            )
            == "ready"
        )

        activation_transaction = activation_connection.transaction()
        await activation_transaction.start()
        activation_open = True
        await activation_connection.execute("select private.activate_embedding_reindex($1)", run_id)

        chunk_pid = await chunk_connection.fetchval("select pg_backend_pid()")
        memory_pid = await memory_connection.fetchval("select pg_backend_pid()")

        async def update_chunk() -> None:
            assert chunk_connection is not None
            async with chunk_connection.transaction():
                await chunk_connection.execute(
                    """update public.knowledge_chunks
                          set content='chunk update committed after activation'
                        where id=$1""",
                    inverse_chunk_id,
                )

        async def update_memory() -> None:
            assert memory_connection is not None
            async with memory_connection.transaction():
                await memory_connection.execute(
                    """update public.memory_items
                          set content='memory update committed after activation'
                        where id=$1""",
                    inverse_memory_id,
                )

        writer_tasks = [asyncio.create_task(update_chunk()), asyncio.create_task(update_memory())]
        blocked_writers = 0
        for _ in range(100):
            blocked_writers = await pool.fetchval(
                """select count(distinct pid)::int from pg_locks
                     where pid=any($1::integer[]) and locktype='advisory' and not granted""",
                [chunk_pid, memory_pid],
            )
            if blocked_writers == 2:
                break
            await asyncio.sleep(0.02)
        assert blocked_writers == 2
        assert not any(task.done() for task in writer_tasks)

        await activation_transaction.commit()
        activation_open = False
        await asyncio.gather(*writer_tasks)
        writer_tasks = []

        assert (
            await pool.fetchval(
                "select status from private.embedding_reindex_runs where id=$1", run_id
            )
            == "activated"
        )
        assert (
            await pool.fetchval(
                """select count(*)::int from (
                     select embedding_profile_id from public.knowledge_chunks
                       where id=any($1::uuid[])
                     union all
                     select embedding_profile_id from public.memory_items
                       where id=any($2::uuid[])
                   ) written where embedding_profile_id=$3""",
                [inverse_chunk_id],
                [inverse_memory_id],
                target_profile_id,
            )
            == 2
        )
        assert (
            await pool.fetchval(
                "select content from public.knowledge_chunks where id=$1", inverse_chunk_id
            )
            == "chunk update committed after activation"
        )
        assert (
            await pool.fetchval(
                "select content from public.memory_items where id=$1", inverse_memory_id
            )
            == "memory update committed after activation"
        )

        # Restore the global embedding profile so this integration remains
        # hermetic for tests that follow it.
        await pool.execute(
            "delete from public.memory_items where id=any($1::uuid[])",
            [inverse_memory_id],
        )
        await pool.execute("delete from public.knowledge_documents where id=$1", document_id)
        restore_run_id = await pool.fetchval(
            "select private.start_embedding_reindex($1,$2,$3,null)",
            old_profile["provider"],
            old_profile["model_name"],
            old_profile["dimensions"],
        )
        for item in original_embeddings:
            await pool.execute(
                "select private.complete_embedding_reindex_item($1,$2,$3,$4::extensions.vector)",
                restore_run_id,
                item["entity_type"],
                item["entity_id"],
                item["embedding"],
            )
        restore_index_commands = await pool.fetch(
            "select ddl from private.embedding_reindex_index_commands($1)", restore_run_id
        )
        assert len(restore_index_commands) == 2
        for command in restore_index_commands:
            await pool.execute(command["ddl"])
        await pool.execute("select private.activate_embedding_reindex($1)", restore_run_id)
        assert (
            await pool.fetchval("select id from private.embedding_profiles where status='active'")
            == old_profile["id"]
        )
        await pool.execute("delete from private.embedding_reindex_runs where id=$1", restore_run_id)
        restore_run_id = None
        await pool.execute("delete from private.embedding_reindex_runs where id=$1", run_id)
        run_id = None
        old_suffix = str(old_profile["id"]).replace("-", "")[:8]
        await pool.execute(
            f'drop index if exists public."knowledge_chunks_embedding_{old_suffix}_hnsw_idx"'
        )
        await pool.execute(
            f'drop index if exists public."memory_items_embedding_{old_suffix}_hnsw_idx"'
        )
        suffix = str(target_profile_id).replace("-", "")[:8]
        await pool.execute(
            f'drop index if exists public."knowledge_chunks_embedding_{suffix}_hnsw_idx"'
        )
        await pool.execute(
            f'drop index if exists public."memory_items_embedding_{suffix}_hnsw_idx"'
        )
        await pool.execute("delete from private.embedding_profiles where id=$1", target_profile_id)
        target_profile_id = None
    finally:
        if activation_open and activation_transaction is not None:
            await activation_transaction.rollback()
        if inverse_open and inverse_transaction is not None:
            await inverse_transaction.rollback()
        for task in writer_tasks:
            task.cancel()
        if writer_tasks:
            await asyncio.gather(*writer_tasks, return_exceptions=True)
        pool = await database.pool()
        await pool.execute(
            "delete from public.memory_items where id=any($1::uuid[])",
            [inverse_memory_id],
        )
        await pool.execute("delete from public.knowledge_documents where id=$1", document_id)
        if restore_run_id:
            await pool.execute(
                "delete from private.embedding_reindex_runs where id=$1", restore_run_id
            )
        if run_id:
            await pool.execute("delete from private.embedding_reindex_runs where id=$1", run_id)
        if target_profile_id:
            await pool.execute(
                "delete from private.embedding_profiles where id=$1", target_profile_id
            )
        if activation_connection is not None:
            await pool.release(activation_connection)
        if inverse_connection is not None:
            await pool.release(inverse_connection)
        if chunk_connection is not None:
            await pool.release(chunk_connection)
        if memory_connection is not None:
            await pool.release(memory_connection)
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
async def test_real_agent_cost_analytics_uses_event_model_not_latest_agent_version() -> None:
    database = Database(os.environ["SUPABASE_INTEGRATION_DATABASE_URL"])
    repo = PostgresAdministrationRepository(database)
    provider_event, provider_latest = uuid4(), uuid4()
    model_event, model_latest, agent_id, task_id = uuid4(), uuid4(), uuid4(), uuid4()
    event_key = f"historical-{uuid4()}"
    try:
        pool = await database.pool()
        await pool.execute(
            """insert into public.model_providers(id,organization_id,name,provider_key)
               values($1,$3,'Historical provider',$4),($2,$3,'Latest provider',$5)""",
            provider_event,
            provider_latest,
            ATLAS_ORGANIZATION_ID,
            f"historical-{provider_event}",
            f"latest-{provider_latest}",
        )
        await pool.execute(
            """insert into public.models(id,organization_id,provider_id,model_key)
               values($1,$3,$4,$6),($2,$3,$5,$7)""",
            model_event,
            model_latest,
            ATLAS_ORGANIZATION_ID,
            provider_event,
            provider_latest,
            f"historical-model-{model_event}",
            f"latest-model-{model_latest}",
        )
        await pool.execute(
            """insert into public.agents(id,organization_id,name,slug,owner_user_id)
               values($1,$2,'Historical cost agent',$3,$4)""",
            agent_id,
            ATLAS_ORGANIZATION_ID,
            f"historical-agent-{agent_id}",
            ATLAS_OWNER_ID,
        )
        await pool.execute(
            """insert into public.agent_versions(
                 organization_id,agent_id,version,model_id,system_prompt,created_by
               ) values($1,$2,1,$3,'old',$5),($1,$2,2,$4,'latest',$5)""",
            ATLAS_ORGANIZATION_ID,
            agent_id,
            model_event,
            model_latest,
            ATLAS_OWNER_ID,
        )
        await pool.execute(
            """insert into public.tasks(id,organization_id,title,objective,requester_id,agent_id)
               values($1,$2,'Historical cost task','analytics',$3,$4)""",
            task_id,
            ATLAS_ORGANIZATION_ID,
            ATLAS_OWNER_ID,
            agent_id,
        )
        await pool.execute(
            """insert into public.cost_events(
                 organization_id,task_id,model_id,provider_event_id,amount,currency
               ) values($1,$2,$3,$4,3.25,'USD')""",
            ATLAS_ORGANIZATION_ID,
            task_id,
            model_event,
            event_key,
        )
        now = datetime.now(UTC)
        result = await repo.analytics(
            ATLAS_OWNER_ID,
            ATLAS_ORGANIZATION_ID,
            "agents",
            now - timedelta(minutes=5),
            now + timedelta(minutes=5),
            "UTC",
            {"provider": f"historical-{provider_event}", "model_id": model_event},
        )
        metric = next(row for row in result["metrics"] if row["id"] == agent_id)
        assert metric["model_id"] == model_event
        assert metric["provider"] == f"historical-{provider_event}"
        assert metric["cost"] == Decimal("3.25")
        assert "skillMetrics" in result
        assert "agent_versions" not in result["source"]
        assert "cost_events.model_id" in result["source"]
    finally:
        pool = await database.pool()
        await pool.execute(
            "delete from public.cost_events where organization_id=$1 and provider_event_id=$2",
            ATLAS_ORGANIZATION_ID,
            event_key,
        )
        await pool.execute("delete from public.tasks where id=$1", task_id)
        await pool.execute("delete from public.agents where id=$1", agent_id)
        await pool.execute(
            "delete from public.model_providers where id=any($1::uuid[])",
            [provider_event, provider_latest],
        )
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
                await cleanup_conn.execute("delete from public.workflows where id=$1", workflow_id)
            finally:
                await cleanup_conn.execute("set session_replication_role = origin")
        await database.close()
