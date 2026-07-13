begin;
create extension if not exists pgtap with schema extensions;
select plan(6);

insert into auth.users (id, instance_id, aud, role, email, encrypted_password, created_at, updated_at)
values
  ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'a@example.test', '', now(), now()),
  ('20000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'b@example.test', '', now(), now());
insert into public.profiles(id, display_name) values
  ('10000000-0000-0000-0000-000000000001', 'User A'),
  ('20000000-0000-0000-0000-000000000002', 'User B');
insert into public.organizations(id, name, slug, created_by) values
  ('a0000000-0000-0000-0000-000000000001', 'Tenant A', 'tenant-a', '10000000-0000-0000-0000-000000000001'),
  ('b0000000-0000-0000-0000-000000000002', 'Tenant B', 'tenant-b', '20000000-0000-0000-0000-000000000002');
insert into public.organization_members(organization_id, user_id, role, status) values
  ('a0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'owner', 'active'),
  ('b0000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', 'owner', 'active');
insert into public.organization_invites(organization_id, email, token_hash, expires_at) values
  ('a0000000-0000-0000-0000-000000000001', 'invite@example.test', 'hash-a', now() + interval '1 day'),
  ('b0000000-0000-0000-0000-000000000002', 'invite@example.test', 'hash-b', now() + interval '1 day');

set local role authenticated;
set local request.jwt.claim.sub = '10000000-0000-0000-0000-000000000001';
select results_eq(
  $$ select slug from public.organizations order by slug $$,
  $$ values ('tenant-a'::text) $$,
  'member cannot list another tenant'
);
select is((select count(*) from public.organization_members), 1::bigint,
  'member cannot count memberships in another tenant');
select is((select count(*) from public.organization_invites), 1::bigint,
  'owner cannot read invitations in another tenant');
select is((select count(*) from public.profiles), 1::bigint,
  'user cannot read another profile');
select results_eq(
  $$ update public.organizations set name = 'Cross tenant'
     where id = 'b0000000-0000-0000-0000-000000000002' returning id $$,
  $$ select null::uuid where false $$,
  'owner cannot update another tenant'
);

reset role;
select throws_ok(
  $$ update public.organization_members set role = 'admin'
     where organization_id = 'a0000000-0000-0000-0000-000000000001'
       and user_id = '10000000-0000-0000-0000-000000000001' $$,
  '23514', 'last_owner_required', 'last active owner cannot be demoted'
);

select * from finish();
rollback;
