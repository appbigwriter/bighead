begin;
create extension if not exists pgtap with schema extensions;
select plan(12);

select has_index(
  'public',
  'knowledge_documents',
  'knowledge_documents_idempotency_key_idx',
  'knowledge ingestion has a database idempotency boundary'
);
select has_index(
  'public',
  'content_assets',
  'content_assets_idempotency_key_idx',
  'content generation has a database idempotency boundary'
);
select has_index(
  'public',
  'event_outbox',
  'event_outbox_crm_import_idempotency_key_idx',
  'CRM import outbox has a database idempotency boundary'
);
select has_index(
  'public',
  'approval_requests',
  'approval_requests_approved_artifact_idx',
  'approved artifacts are indexed for publication authorization'
);

select ok(
  (select indisunique from pg_catalog.pg_index
    where indexrelid='public.knowledge_documents_idempotency_key_idx'::regclass),
  'knowledge idempotency boundary is unique'
);
select ok(
  (select indisunique from pg_catalog.pg_index
    where indexrelid='public.content_assets_idempotency_key_idx'::regclass),
  'content idempotency boundary is unique'
);
select ok(
  (select indisunique from pg_catalog.pg_index
    where indexrelid='public.event_outbox_crm_import_idempotency_key_idx'::regclass),
  'CRM import idempotency boundary is unique'
);

select has_column(
  'public',
  'content_assets',
  'approval_request_id',
  'content approvals have a relational binding column'
);
select has_trigger(
  'public',
  'content_assets',
  'content_assets_approval_binding_immutable',
  'content approval bindings are immutable'
);
select ok(
  not has_column_privilege(
    'authenticated', 'public.content_assets', 'approval_request_id', 'INSERT'
  ),
  'authenticated members cannot insert forged content approval bindings'
);
select ok(
  not has_column_privilege(
    'authenticated', 'public.content_assets', 'approval_request_id', 'UPDATE'
  ),
  'authenticated members cannot update content approval bindings'
);
select has_index(
  'public',
  'content_assets',
  'content_assets_approval_request_unique',
  'an approval request cannot be rebound to another content asset'
);

select * from finish();
rollback;
