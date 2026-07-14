begin;
create extension if not exists pgtap with schema extensions;
select plan(23);

insert into auth.users (id, instance_id, aud, role, email, encrypted_password, created_at, updated_at)
values
  ('41000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'security-owner@example.test', '', now(), now()),
  ('41000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'security-member@example.test', '', now(), now()),
  ('41000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'security-reviewer@example.test', '', now(), now()),
  ('42000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'security-other@example.test', '', now(), now());
insert into public.profiles(id, display_name) values
  ('41000000-0000-0000-0000-000000000001', 'Security Owner'),
  ('41000000-0000-0000-0000-000000000002', 'Security Member'),
  ('41000000-0000-0000-0000-000000000003', 'Security Reviewer'),
  ('42000000-0000-0000-0000-000000000001', 'Security Other');
insert into public.organizations(id, name, slug, created_by) values
  ('aa100000-0000-0000-0000-000000000001', 'Security Tenant A', 'security-tenant-a', '41000000-0000-0000-0000-000000000001'),
  ('bb100000-0000-0000-0000-000000000001', 'Security Tenant B', 'security-tenant-b', '42000000-0000-0000-0000-000000000001');
insert into public.organization_members(organization_id, user_id, role, status) values
  ('aa100000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000001', 'owner', 'active'),
  ('aa100000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000002', 'member', 'active'),
  ('aa100000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000003', 'reviewer', 'active'),
  ('bb100000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000002', 'member', 'active'),
  ('bb100000-0000-0000-0000-000000000001', '42000000-0000-0000-0000-000000000001', 'owner', 'active');
insert into public.rooms(id, organization_id, name, created_by) values
  ('aa200000-0000-0000-0000-000000000001', 'aa100000-0000-0000-0000-000000000001', 'Security Room A', '41000000-0000-0000-0000-000000000001'),
  ('aa200000-0000-0000-0000-000000000002', 'aa100000-0000-0000-0000-000000000001', 'Security Room A2', '41000000-0000-0000-0000-000000000001'),
  ('bb200000-0000-0000-0000-000000000001', 'bb100000-0000-0000-0000-000000000001', 'Security Room B', '42000000-0000-0000-0000-000000000001');
insert into public.messages(id, organization_id, room_id, author_user_id, body) values
  ('aa300000-0000-0000-0000-000000000001', 'aa100000-0000-0000-0000-000000000001', 'aa200000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000002', 'Protected message');
insert into public.tasks(id, organization_id, room_id, title, objective, requester_id) values
  ('aa400000-0000-0000-0000-000000000001', 'aa100000-0000-0000-0000-000000000001', 'aa200000-0000-0000-0000-000000000001', 'Protected task', 'Security boundary', '41000000-0000-0000-0000-000000000002');
insert into public.approval_requests(id, organization_id, task_id, requested_by, assigned_to, risk_level, status) values
  ('aa500000-0000-0000-0000-000000000001', 'aa100000-0000-0000-0000-000000000001', 'aa400000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000002', '41000000-0000-0000-0000-000000000001', 'high', 'pending'),
  ('aa500000-0000-0000-0000-000000000002', 'aa100000-0000-0000-0000-000000000001', 'aa400000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000002', '41000000-0000-0000-0000-000000000003', 'high', 'approved');
insert into public.notifications(id, organization_id, user_id, kind, title) values
  ('aa600000-0000-0000-0000-000000000001', 'aa100000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000001', 'approval', 'Owner notice'),
  ('aa600000-0000-0000-0000-000000000002', 'aa100000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000002', 'task', 'Member notice');
insert into public.audit_log(id, organization_id, actor_type, action, resource_type)
overriding system value values (91001, 'aa100000-0000-0000-0000-000000000001', 'system', 'created', 'test');
insert into public.knowledge_documents(id, organization_id, title, source_type)
values (
  'aa700000-0000-0000-0000-000000000001',
  'aa100000-0000-0000-0000-000000000001',
  'Tenant-bound document',
  'upload'
);

set local role authenticated;
set local request.jwt.claim.sub = '41000000-0000-0000-0000-000000000002';
select is((select auth.uid()), '41000000-0000-0000-0000-000000000002'::uuid,
  'adversarial session is the ordinary member');
select throws_ok(
  $$ insert into public.approval_decisions(organization_id, approval_request_id, decision, decided_by)
     values ('aa100000-0000-0000-0000-000000000001', 'aa500000-0000-0000-0000-000000000001', 'approved', '41000000-0000-0000-0000-000000000002') $$,
  '42501', null, 'ordinary member cannot decide an approval'
);
select throws_ok(
  $$ update public.approval_requests set status = 'approved'
     where id = 'aa500000-0000-0000-0000-000000000001' $$,
  '42501', null,
  'ordinary member cannot update approval request state'
);
select throws_ok(
  $$ update public.tasks set status = 'done', version = 99
     where id = 'aa400000-0000-0000-0000-000000000001' $$,
  '42501', null, 'task state fields cannot be changed directly'
);
select lives_ok(
  $$ update public.tasks set title = 'Safe task edit'
     where id = 'aa400000-0000-0000-0000-000000000001' $$,
  'safe task fields remain editable'
);
select throws_ok(
  $$ update public.knowledge_documents
     set organization_id = 'bb100000-0000-0000-0000-000000000001'
     where id = 'aa700000-0000-0000-0000-000000000001' $$,
  '23514', 'tenant_scope_immutable',
  'member of both tenants cannot reparent a tenant-owned row'
);
select results_eq(
  $$ select title from public.notifications order by title $$,
  $$ values ('Member notice'::text) $$,
  'ordinary member reads only own notifications'
);
select throws_ok(
  $$ update public.messages
     set organization_id = 'bb100000-0000-0000-0000-000000000001',
         room_id = 'bb200000-0000-0000-0000-000000000001'
     where id = 'aa300000-0000-0000-0000-000000000001' $$,
  '23514', 'message_retarget_forbidden', 'message cannot be moved to an unauthorized room or tenant'
);
select throws_ok(
  $$ update public.messages set room_id = 'aa200000-0000-0000-0000-000000000002'
     where id = 'aa300000-0000-0000-0000-000000000001' $$,
  '23514', 'message_retarget_forbidden', 'message cannot be retargeted inside the same tenant'
);

set local request.jwt.claim.sub = '41000000-0000-0000-0000-000000000003';
select throws_ok(
  $$ insert into public.approval_decisions(organization_id, approval_request_id, decision, decided_by)
     values ('aa100000-0000-0000-0000-000000000001', 'aa500000-0000-0000-0000-000000000001', 'approved', '41000000-0000-0000-0000-000000000003') $$,
  '42501', null, 'reviewer cannot decide a request assigned to someone else'
);
select throws_ok(
  $$ insert into public.approval_decisions(organization_id, approval_request_id, decision, decided_by)
     values ('aa100000-0000-0000-0000-000000000001', 'aa500000-0000-0000-0000-000000000002', 'approved', '41000000-0000-0000-0000-000000000003') $$,
  '42501', null, 'reviewer cannot decide a request that is no longer pending'
);

set local request.jwt.claim.sub = '41000000-0000-0000-0000-000000000001';
select throws_ok(
  $$ insert into public.approval_decisions(organization_id, approval_request_id, decision, decided_by)
     values ('aa100000-0000-0000-0000-000000000001', 'aa500000-0000-0000-0000-000000000001', 'approved', '41000000-0000-0000-0000-000000000002') $$,
  '42501', null, 'elevated reviewer cannot forge decided_by'
);
select throws_ok(
  $$ update public.approval_requests set status = 'approved'
     where id = 'aa500000-0000-0000-0000-000000000001' $$,
  '42501', null, 'owner cannot bypass approval state workflow with direct update'
);
select lives_ok(
  $$ insert into public.approval_decisions(organization_id, approval_request_id, decision, decided_by)
     values ('aa100000-0000-0000-0000-000000000001', 'aa500000-0000-0000-0000-000000000001', 'approved', '41000000-0000-0000-0000-000000000001') $$,
  'owner override is explicit and preserves actor identity'
);
select is((select count(*) from public.notifications), 2::bigint,
  'owner may read tenant notifications for governance');
select is(
  (select (public.transition_task('aa400000-0000-0000-0000-000000000001', 'triaged', 'reviewed', 1)).status),
  'triaged'::public.task_status,
  'task state transition succeeds only through RPC'
);

reset role;
set local role service_role;
select throws_ok(
  $$ update public.audit_log set action = 'tampered' where id = 91001 $$,
  '23514', 'immutable_audit_log', 'service backend cannot mutate audit log'
);
reset role;

select is(
  (select count(*)
   from pg_proc p
   join pg_namespace n on n.oid = p.pronamespace
   cross join lateral aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
   where n.nspname = 'private' and a.grantee = 0 and a.privilege_type = 'EXECUTE'),
  0::bigint,
  'PUBLIC has no execute privilege on private functions'
);

select has_index('public', 'tasks', 'tasks_idempotency_key_idx',
  'tasks have a tenant-scoped persistent idempotency key');
select has_index('public', 'messages', 'messages_client_id_idx',
  'messages have a persistent reconnect dedupe key');
select ok(exists(select 1 from pg_publication_tables where pubname='supabase_realtime'
  and schemaname='public' and tablename='messages'), 'messages publish through Realtime');
select ok(exists(select 1 from pg_publication_tables where pubname='supabase_realtime'
  and schemaname='public' and tablename='tasks'), 'tasks publish through Realtime');
select is((select count(*) from public.event_outbox
  where event_type='tasks.transitioned'
    and aggregate_id='aa400000-0000-0000-0000-000000000001'),
  1::bigint, 'task transition commits an outbox event atomically');

select * from finish();
rollback;
