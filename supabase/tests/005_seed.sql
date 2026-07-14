begin;
create extension if not exists pgtap with schema extensions;
select plan(9);

select is(
  (select count(*) from public.organizations where id in (
    'a7100000-0000-0000-0000-000000000001',
    'b7200000-0000-0000-0000-000000000001'
  )),
  2::bigint,
  'seed provides two deterministic tenants'
);

select is(
  (select count(*) from auth.users where email like '%@atlas.bighead.dev'),
  6::bigint,
  'Atlas has six real Auth users'
);

select is(
  (select count(*) from auth.identities i join auth.users u on u.id = i.user_id
    where u.email like '%@atlas.bighead.dev' and i.provider = 'email'),
  6::bigint,
  'Atlas users have email identities'
);

select results_eq(
  $$ select role::text from public.organization_members
       where organization_id = 'a7100000-0000-0000-0000-000000000001'
       order by role::text $$,
  $$ values ('admin'::text), ('analyst'), ('manager'), ('member'), ('owner'), ('reviewer') $$,
  'Atlas includes every supported role'
);

select results_eq(
  $$ select role::text from public.organization_members
       where organization_id = 'b7200000-0000-0000-0000-000000000001'
       order by role::text $$,
  $$ values ('admin'::text), ('analyst'), ('manager'), ('member'), ('owner'), ('reviewer') $$,
  'Beacon includes every supported role'
);

select is(
  (select count(*) from public.experiments
    where id in ('e7100000-0000-0000-0000-000000000001','e7200000-0000-0000-0000-000000000001')),
  2::bigint,
  'seed provides one deterministic experiment per tenant'
);

select is(
  (select count(*) from public.experiment_variants
    where experiment_id in ('e7100000-0000-0000-0000-000000000001','e7200000-0000-0000-0000-000000000001')),
  4::bigint,
  'seed experiments each have two weighted variants'
);

set local role authenticated;
set local request.jwt.claim.sub = 'd1000000-0000-0000-0000-000000000004';

select results_eq(
  $$ select slug from public.organizations order by slug $$,
  $$ values ('atlas-local'::text) $$,
  'seed member sees only its tenant through RLS'
);

select is(
  (select count(*) from public.organization_members),
  6::bigint,
  'seed member cannot enumerate memberships from the other tenant'
);

select * from finish();
rollback;
