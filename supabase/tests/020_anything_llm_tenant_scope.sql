begin;

select plan(16);

insert into auth.users (id, instance_id, aud, role, email, encrypted_password, created_at, updated_at)
values
  ('9a000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'rag-a@example.test', '', now(), now()),
  ('9b000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'rag-b@example.test', '', now(), now());
insert into public.profiles(id, display_name) values
  ('9a000000-0000-0000-0000-000000000001', 'RAG Owner A'),
  ('9b000000-0000-0000-0000-000000000001', 'RAG Owner B');
insert into public.organizations(id, name, slug, created_by) values
  ('9a100000-0000-0000-0000-000000000001', 'RAG Tenant A', 'rag-tenant-a', '9a000000-0000-0000-0000-000000000001'),
  ('9b100000-0000-0000-0000-000000000001', 'RAG Tenant B', 'rag-tenant-b', '9b000000-0000-0000-0000-000000000001');
insert into public.organization_members(organization_id, user_id, role, status) values
  ('9a100000-0000-0000-0000-000000000001', '9a000000-0000-0000-0000-000000000001', 'owner', 'active'),
  ('9b100000-0000-0000-0000-000000000001', '9a000000-0000-0000-0000-000000000001', 'admin', 'active'),
  ('9b100000-0000-0000-0000-000000000001', '9b000000-0000-0000-0000-000000000001', 'owner', 'active');
insert into public.artifacts(id, organization_id, name, kind, storage_bucket, storage_path) values
  ('9a200000-0000-0000-0000-000000000001', '9a100000-0000-0000-0000-000000000001', 'tenant-a.pdf', 'document', 'artifacts', '9a/tenant-a.pdf'),
  ('9b200000-0000-0000-0000-000000000001', '9b100000-0000-0000-0000-000000000001', 'tenant-b.pdf', 'document', 'artifacts', '9b/tenant-b.pdf');
insert into public.agents(id, organization_id, name, slug) values
  ('9a300000-0000-0000-0000-000000000001', '9a100000-0000-0000-0000-000000000001', 'Pinned agent', 'pinned-agent');
insert into public.agent_versions(id, organization_id, agent_id, version, system_prompt) values
  ('9a400000-0000-0000-0000-000000000001', '9a100000-0000-0000-0000-000000000001', '9a300000-0000-0000-0000-000000000001', 1, 'version one');
insert into public.skills(id, organization_id, name, slug, input_schema, output_schema) values
  ('9a410000-0000-0000-0000-000000000001', '9a100000-0000-0000-0000-000000000001', 'Query knowledge base', 'query_knowledge_base', '{}', '{"type":"object"}');
insert into public.agent_version_skills(organization_id, agent_version_id, skill_id) values
  ('9a100000-0000-0000-0000-000000000001', '9a400000-0000-0000-0000-000000000001', '9a410000-0000-0000-0000-000000000001');
update public.agent_versions
set published_at = now()
where id = '9a400000-0000-0000-0000-000000000001';
insert into public.tasks(id, organization_id, title, objective, requester_id, agent_id) values
  ('9a500000-0000-0000-0000-000000000001', '9a100000-0000-0000-0000-000000000001', 'Pinned run', 'Keep original version', '9a000000-0000-0000-0000-000000000001', '9a300000-0000-0000-0000-000000000001');
insert into public.runs(id, organization_id, task_id, idempotency_key) values
  ('9a600000-0000-0000-0000-000000000001', '9a100000-0000-0000-0000-000000000001', '9a500000-0000-0000-0000-000000000001', 'pin-version-test');
insert into public.agent_versions(id, organization_id, agent_id, version, system_prompt, published_at) values
  ('9a400000-0000-0000-0000-000000000002', '9a100000-0000-0000-0000-000000000001', '9a300000-0000-0000-0000-000000000001', 2, 'version two', now());
insert into public.agent_versions(id, organization_id, agent_id, version, system_prompt) values
  ('9a400000-0000-0000-0000-000000000003', '9a100000-0000-0000-0000-000000000001', '9a300000-0000-0000-0000-000000000001', 3, 'draft version');

select is(
  (select agent_id from public.runs where id = '9a600000-0000-0000-0000-000000000001'),
  '9a300000-0000-0000-0000-000000000001'::uuid,
  'run pins the task agent when enqueued'
);
select is(
  (select agent_version_id from public.runs where id = '9a600000-0000-0000-0000-000000000001'),
  '9a400000-0000-0000-0000-000000000001'::uuid,
  'run keeps the version published at enqueue time'
);
select throws_ok(
  $$ update public.runs set agent_version_id = '9a400000-0000-0000-0000-000000000002'
     where id = '9a600000-0000-0000-0000-000000000001' $$,
  '23514', 'run_agent_context_immutable',
  'pinned run version cannot be changed after enqueue'
);
select throws_ok(
  $$ delete from public.agent_version_skills
     where agent_version_id = '9a400000-0000-0000-0000-000000000001' $$,
  '23514', 'published_agent_version_skills_immutable',
  'published agent version skill bindings cannot change after enqueue'
);
select throws_ok(
  $$ update public.agent_version_skills
     set agent_version_id = '9a400000-0000-0000-0000-000000000003'
     where agent_version_id = '9a400000-0000-0000-0000-000000000001' $$,
  '23514', 'published_agent_version_skills_immutable',
  'published skill binding cannot be moved to a draft version'
);

set local role service_role;
select is(
  (select agent_version_id from private.snapshot_run_llm_context('9a600000-0000-0000-0000-000000000001')),
  '9a400000-0000-0000-0000-000000000001'::uuid,
  'worker snapshot uses the version pinned at enqueue instead of the latest publication'
);
select ok(
  (
    select policy_snapshot -> 'skills' @> '[{"slug":"query_knowledge_base"}]'::jsonb
    from public.claim_llm_runs('pgtap-worker', 20, 60)
    where id = '9a600000-0000-0000-0000-000000000001'
  ),
  'worker allowlist includes enabled skills bound directly to the pinned agent version'
);
reset role;

select ok(has_table_privilege('authenticated', 'public.anything_llm_ingestions', 'SELECT'), 'authenticated may read through RLS');
select ok(has_table_privilege('authenticated', 'public.anything_llm_ingestions', 'INSERT'), 'authenticated may insert through RLS');
select ok(has_table_privilege('authenticated', 'public.anything_llm_ingestions', 'UPDATE'), 'authenticated may update through RLS');
select ok(not has_table_privilege('authenticated', 'public.anything_llm_ingestions', 'DELETE'), 'authenticated cannot delete ingestion audit rows');

set local role authenticated;
set local request.jwt.claim.sub = '9a000000-0000-0000-0000-000000000001';
select lives_ok(
  $$ insert into public.anything_llm_ingestions(
       artifact_id, organization_id, workspace, status, checksum_sha256, mime_type, size_bytes
     ) values (
       '9a200000-0000-0000-0000-000000000001', '9a100000-0000-0000-0000-000000000001',
       'tenant-a', 'pending', repeat('a', 64), 'application/pdf', 10
     ) $$,
  'tenant admin can register its own artifact'
);
select is((select count(*) from public.anything_llm_ingestions), 1::bigint, 'tenant A sees its ingestion');
select throws_ok(
  $$ update public.anything_llm_ingestions
       set organization_id = '9b100000-0000-0000-0000-000000000001'
       where artifact_id = '9a200000-0000-0000-0000-000000000001' $$,
  '23514', 'tenant_scope_immutable',
  'member of both tenants cannot reparent an ingestion'
);

set local request.jwt.claim.sub = '9b000000-0000-0000-0000-000000000001';
select is((select count(*) from public.anything_llm_ingestions), 0::bigint, 'tenant B cannot read tenant A ingestion');
select throws_ok(
  $$ insert into public.anything_llm_ingestions(
       artifact_id, organization_id, workspace, status, checksum_sha256, mime_type, size_bytes
     ) values (
       '9a200000-0000-0000-0000-000000000001', '9a100000-0000-0000-0000-000000000001',
       'tenant-a', 'pending', repeat('b', 64), 'application/pdf', 10
     ) $$,
  '42501', null,
  'tenant B cannot register a tenant A artifact'
);

select * from finish();
rollback;
