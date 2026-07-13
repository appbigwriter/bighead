begin;
create extension if not exists pgtap with schema extensions;
select plan(6);

select is(
  (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind = 'r'),
  46::bigint,
  'Sprint 3 exposes exactly 46 public domain tables'
);

select is(
  (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind = 'r' and c.relrowsecurity),
  46::bigint,
  'RLS is enabled on all 46 public domain tables'
);

insert into auth.users (id, instance_id, aud, role, email, encrypted_password, created_at, updated_at)
values
  ('31000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'domain-a@example.test', '', now(), now()),
  ('32000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'domain-b@example.test', '', now(), now());
insert into public.profiles(id, display_name) values
  ('31000000-0000-0000-0000-000000000001', 'Domain A'),
  ('32000000-0000-0000-0000-000000000002', 'Domain B');
insert into public.organizations(id, name, slug, created_by) values
  ('ca000000-0000-0000-0000-000000000001', 'Domain Tenant A', 'domain-tenant-a', '31000000-0000-0000-0000-000000000001'),
  ('cb000000-0000-0000-0000-000000000002', 'Domain Tenant B', 'domain-tenant-b', '32000000-0000-0000-0000-000000000002');
insert into public.organization_members(organization_id, user_id, role, status) values
  ('ca000000-0000-0000-0000-000000000001', '31000000-0000-0000-0000-000000000001', 'owner', 'active'),
  ('cb000000-0000-0000-0000-000000000002', '32000000-0000-0000-0000-000000000002', 'owner', 'active');
insert into public.rooms(id, organization_id, name, created_by) values
  ('da000000-0000-0000-0000-000000000001', 'ca000000-0000-0000-0000-000000000001', 'Room A', '31000000-0000-0000-0000-000000000001'),
  ('db000000-0000-0000-0000-000000000002', 'cb000000-0000-0000-0000-000000000002', 'Room B', '32000000-0000-0000-0000-000000000002');
insert into public.tasks(id, organization_id, room_id, title, objective, requester_id) values
  ('ea000000-0000-0000-0000-000000000001', 'ca000000-0000-0000-0000-000000000001', 'da000000-0000-0000-0000-000000000001', 'Task A', 'Tenant A objective', '31000000-0000-0000-0000-000000000001'),
  ('ea000000-0000-0000-0000-000000000002', 'ca000000-0000-0000-0000-000000000001', 'da000000-0000-0000-0000-000000000001', 'Task A2', 'Tenant A dependency', '31000000-0000-0000-0000-000000000001'),
  ('eb000000-0000-0000-0000-000000000002', 'cb000000-0000-0000-0000-000000000002', 'db000000-0000-0000-0000-000000000002', 'Task B', 'Tenant B objective', '32000000-0000-0000-0000-000000000002');
insert into public.task_dependencies(organization_id, task_id, depends_on_task_id)
values ('ca000000-0000-0000-0000-000000000001', 'ea000000-0000-0000-0000-000000000001', 'ea000000-0000-0000-0000-000000000002');
select throws_ok(
  $$ insert into public.task_dependencies(organization_id, task_id, depends_on_task_id)
     values ('ca000000-0000-0000-0000-000000000001', 'ea000000-0000-0000-0000-000000000002', 'ea000000-0000-0000-0000-000000000001') $$,
  '23514', 'task_dependency_cycle', 'indirect task dependency cycle is rejected'
);

set local role authenticated;
set local request.jwt.claim.sub = '31000000-0000-0000-0000-000000000001';
select results_eq(
  $$ select name from public.rooms order by name $$,
  $$ values ('Room A'::text) $$,
  'room listing cannot disclose another tenant'
);
select results_eq(
  $$ select title from public.tasks order by title $$,
  $$ values ('Task A'::text), ('Task A2'::text) $$,
  'task listing cannot disclose another tenant'
);
select results_eq(
  $$ update public.tasks set title = 'Cross tenant mutation'
     where id = 'eb000000-0000-0000-0000-000000000002' returning id $$,
  $$ select null::uuid where false $$,
  'task update cannot mutate another tenant'
);

select * from finish();
rollback;
