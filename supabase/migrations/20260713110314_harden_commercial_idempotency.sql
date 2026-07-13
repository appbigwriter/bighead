begin;

create unique index knowledge_documents_idempotency_key_idx
on public.knowledge_documents (organization_id, (metadata ->> 'idempotency_key'))
where nullif(metadata ->> 'idempotency_key', '') is not null;

create unique index content_assets_idempotency_key_idx
on public.content_assets (organization_id, (body ->> 'idempotency_key'))
where nullif(body ->> 'idempotency_key', '') is not null;

create unique index event_outbox_crm_import_idempotency_key_idx
on public.event_outbox (organization_id, (payload ->> 'idempotencyKey'))
where event_type = 'crm.import.requested'
  and nullif(payload ->> 'idempotencyKey', '') is not null;

create index approval_requests_approved_artifact_idx
on public.approval_requests (organization_id, artifact_id, decided_at desc)
where status = 'approved';

commit;
