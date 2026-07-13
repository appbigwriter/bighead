begin;
create extension if not exists pgtap with schema extensions;
select plan(21);

select has_index(
  'public',
  'knowledge_documents',
  'knowledge_documents_idempotency_key_idx',
  'knowledge ingestion has a database idempotency boundary'
);
select has_index(
  'public',
  'crm_accounts',
  'crm_accounts_org_domain_unique_idx',
  'CRM account domains are unique only when present'
);
select lives_ok(
  $$insert into public.crm_accounts(organization_id, name, domain)
    values
      ('a7100000-0000-0000-0000-000000000001', 'pgTAP no domain A', null),
      ('a7100000-0000-0000-0000-000000000001', 'pgTAP no domain B', null)$$,
  'multiple CRM accounts without domains remain distinct'
);
insert into public.crm_accounts(organization_id, name, domain)
values (
  'a7100000-0000-0000-0000-000000000001',
  'pgTAP domain owner',
  'pgtap-domain-unique.invalid'
);
select throws_ok(
  $$insert into public.crm_accounts(organization_id, name, domain)
    values (
      'a7100000-0000-0000-0000-000000000001',
      'pgTAP duplicate domain',
      'pgtap-domain-unique.invalid'
    )$$,
  '23505',
  null,
  'a present CRM domain remains unique inside the tenant'
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
select has_column(
  'public','content_assets','approval_payload_hash',
  'approved content seals the exact payload hash'
);
select has_trigger(
  'public','content_assets','content_assets_validate_approval_subject',
  'content approval subject is checked by the database'
);
select has_table(
  'private','publication_attempts',
  'publication idempotency and attempts use a private ledger'
);
select ok(
  not has_column_privilege('authenticated','public.content_assets','body','UPDATE'),
  'Data API cannot rewrite approved content bodies'
);
select ok(
  not has_column_privilege('authenticated','public.content_assets','status','UPDATE'),
  'Data API cannot force publication lifecycle states'
);
select ok(
  not has_table_privilege('authenticated','private.publication_attempts','SELECT'),
  'application users cannot read or forge publication attempts'
);

select * from finish();
rollback;
