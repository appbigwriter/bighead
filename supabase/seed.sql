-- Local-only deterministic seed. This file intentionally contains no schema DDL.
-- Every tenant has every supported role so RBAC and cross-tenant scenarios are
-- reproducible after `supabase db reset`.

insert into storage.buckets (id, name, public, file_size_limit)
values ('artifacts', 'artifacts', false, 52428800)
on conflict (id) do update
set public = false, file_size_limit = excluded.file_size_limit;

with seed_users(id, email, display_name) as (
  values
    ('d1000000-0000-0000-0000-000000000001'::uuid, 'owner@atlas.bighead.dev', 'Atlas Owner'),
    ('d1000000-0000-0000-0000-000000000002'::uuid, 'admin@atlas.bighead.dev', 'Atlas Admin'),
    ('d1000000-0000-0000-0000-000000000003'::uuid, 'manager@atlas.bighead.dev', 'Atlas Manager'),
    ('d1000000-0000-0000-0000-000000000004'::uuid, 'member@atlas.bighead.dev', 'Atlas Member'),
    ('d1000000-0000-0000-0000-000000000005'::uuid, 'reviewer@atlas.bighead.dev', 'Atlas Reviewer'),
    ('d1000000-0000-0000-0000-000000000006'::uuid, 'analyst@atlas.bighead.dev', 'Atlas Analyst'),
    ('d2000000-0000-0000-0000-000000000001'::uuid, 'owner@beacon.bighead.dev', 'Beacon Owner'),
    ('d2000000-0000-0000-0000-000000000002'::uuid, 'admin@beacon.bighead.dev', 'Beacon Admin'),
    ('d2000000-0000-0000-0000-000000000003'::uuid, 'manager@beacon.bighead.dev', 'Beacon Manager'),
    ('d2000000-0000-0000-0000-000000000004'::uuid, 'member@beacon.bighead.dev', 'Beacon Member'),
    ('d2000000-0000-0000-0000-000000000005'::uuid, 'reviewer@beacon.bighead.dev', 'Beacon Reviewer'),
    ('d2000000-0000-0000-0000-000000000006'::uuid, 'analyst@beacon.bighead.dev', 'Beacon Analyst')
)
insert into auth.users (
  instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
  confirmation_token, recovery_token, email_change_token_new, email_change,
  phone_change, phone_change_token, email_change_token_current,
  reauthentication_token, raw_app_meta_data, raw_user_meta_data, created_at, updated_at
)
select
  '00000000-0000-0000-0000-000000000000'::uuid,
  id,
  'authenticated',
  'authenticated',
  email,
  crypt('BigHeadLocalOnly!2026', gen_salt('bf')),
  now(),
  '', '', '', '', '', '', '', '',
  jsonb_build_object('provider', 'email', 'providers', jsonb_build_array('email')),
  jsonb_build_object('display_name', display_name),
  now(),
  now()
from seed_users
on conflict (id) do update
set email = excluded.email,
    encrypted_password = excluded.encrypted_password,
    email_confirmed_at = excluded.email_confirmed_at,
    raw_app_meta_data = excluded.raw_app_meta_data,
    raw_user_meta_data = excluded.raw_user_meta_data,
    updated_at = excluded.updated_at;

with seed_users(id, email) as (
  values
    ('d1000000-0000-0000-0000-000000000001'::uuid, 'owner@atlas.bighead.dev'),
    ('d1000000-0000-0000-0000-000000000002'::uuid, 'admin@atlas.bighead.dev'),
    ('d1000000-0000-0000-0000-000000000003'::uuid, 'manager@atlas.bighead.dev'),
    ('d1000000-0000-0000-0000-000000000004'::uuid, 'member@atlas.bighead.dev'),
    ('d1000000-0000-0000-0000-000000000005'::uuid, 'reviewer@atlas.bighead.dev'),
    ('d1000000-0000-0000-0000-000000000006'::uuid, 'analyst@atlas.bighead.dev'),
    ('d2000000-0000-0000-0000-000000000001'::uuid, 'owner@beacon.bighead.dev'),
    ('d2000000-0000-0000-0000-000000000002'::uuid, 'admin@beacon.bighead.dev'),
    ('d2000000-0000-0000-0000-000000000003'::uuid, 'manager@beacon.bighead.dev'),
    ('d2000000-0000-0000-0000-000000000004'::uuid, 'member@beacon.bighead.dev'),
    ('d2000000-0000-0000-0000-000000000005'::uuid, 'reviewer@beacon.bighead.dev'),
    ('d2000000-0000-0000-0000-000000000006'::uuid, 'analyst@beacon.bighead.dev')
)
insert into auth.identities (id, provider_id, user_id, identity_data, provider, created_at, updated_at)
select
  gen_random_uuid(),
  id::text,
  id,
  jsonb_build_object(
    'sub', id::text,
    'email', email,
    'email_verified', true,
    'phone_verified', false
  ),
  'email',
  now(),
  now()
from seed_users
on conflict (provider_id, provider) do update
set identity_data = excluded.identity_data, updated_at = excluded.updated_at;

insert into public.profiles (id, display_name, locale, timezone, preferences)
values
  ('d1000000-0000-0000-0000-000000000001', 'Atlas Owner', 'pt-BR', 'America/Sao_Paulo', '{"theme":"aurora-light"}'),
  ('d1000000-0000-0000-0000-000000000002', 'Atlas Admin', 'pt-BR', 'America/Sao_Paulo', '{}'),
  ('d1000000-0000-0000-0000-000000000003', 'Atlas Manager', 'pt-BR', 'America/Sao_Paulo', '{}'),
  ('d1000000-0000-0000-0000-000000000004', 'Atlas Member', 'pt-BR', 'America/Sao_Paulo', '{}'),
  ('d1000000-0000-0000-0000-000000000005', 'Atlas Reviewer', 'pt-BR', 'America/Sao_Paulo', '{}'),
  ('d1000000-0000-0000-0000-000000000006', 'Atlas Analyst', 'pt-BR', 'America/Sao_Paulo', '{}'),
  ('d2000000-0000-0000-0000-000000000001', 'Beacon Owner', 'en-US', 'UTC', '{"theme":"radar-dark"}'),
  ('d2000000-0000-0000-0000-000000000002', 'Beacon Admin', 'en-US', 'UTC', '{}'),
  ('d2000000-0000-0000-0000-000000000003', 'Beacon Manager', 'en-US', 'UTC', '{}'),
  ('d2000000-0000-0000-0000-000000000004', 'Beacon Member', 'en-US', 'UTC', '{}'),
  ('d2000000-0000-0000-0000-000000000005', 'Beacon Reviewer', 'en-US', 'UTC', '{}'),
  ('d2000000-0000-0000-0000-000000000006', 'Beacon Analyst', 'en-US', 'UTC', '{}')
on conflict (id) do update
set display_name = excluded.display_name,
    locale = excluded.locale,
    timezone = excluded.timezone,
    preferences = excluded.preferences;

insert into public.organizations (id, name, slug, timezone, locale, created_by)
values
  ('a7100000-0000-0000-0000-000000000001', 'Atlas Local', 'atlas-local', 'America/Sao_Paulo', 'pt-BR', 'd1000000-0000-0000-0000-000000000001'),
  ('b7200000-0000-0000-0000-000000000001', 'Beacon Local', 'beacon-local', 'UTC', 'en-US', 'd2000000-0000-0000-0000-000000000001')
on conflict (id) do update
set name = excluded.name,
    slug = excluded.slug,
    timezone = excluded.timezone,
    locale = excluded.locale,
    created_by = excluded.created_by;

with memberships(organization_id, user_id, role) as (
  values
    ('a7100000-0000-0000-0000-000000000001'::uuid, 'd1000000-0000-0000-0000-000000000001'::uuid, 'owner'::public.member_role),
    ('a7100000-0000-0000-0000-000000000001'::uuid, 'd1000000-0000-0000-0000-000000000002'::uuid, 'admin'::public.member_role),
    ('a7100000-0000-0000-0000-000000000001'::uuid, 'd1000000-0000-0000-0000-000000000003'::uuid, 'manager'::public.member_role),
    ('a7100000-0000-0000-0000-000000000001'::uuid, 'd1000000-0000-0000-0000-000000000004'::uuid, 'member'::public.member_role),
    ('a7100000-0000-0000-0000-000000000001'::uuid, 'd1000000-0000-0000-0000-000000000005'::uuid, 'reviewer'::public.member_role),
    ('a7100000-0000-0000-0000-000000000001'::uuid, 'd1000000-0000-0000-0000-000000000006'::uuid, 'analyst'::public.member_role),
    ('b7200000-0000-0000-0000-000000000001'::uuid, 'd2000000-0000-0000-0000-000000000001'::uuid, 'owner'::public.member_role),
    ('b7200000-0000-0000-0000-000000000001'::uuid, 'd2000000-0000-0000-0000-000000000002'::uuid, 'admin'::public.member_role),
    ('b7200000-0000-0000-0000-000000000001'::uuid, 'd2000000-0000-0000-0000-000000000003'::uuid, 'manager'::public.member_role),
    ('b7200000-0000-0000-0000-000000000001'::uuid, 'd2000000-0000-0000-0000-000000000004'::uuid, 'member'::public.member_role),
    ('b7200000-0000-0000-0000-000000000001'::uuid, 'd2000000-0000-0000-0000-000000000005'::uuid, 'reviewer'::public.member_role),
    ('b7200000-0000-0000-0000-000000000001'::uuid, 'd2000000-0000-0000-0000-000000000006'::uuid, 'analyst'::public.member_role)
)
insert into public.organization_members (organization_id, user_id, role, status, joined_at)
select organization_id, user_id, role, 'active', now()
from memberships
on conflict (organization_id, user_id) do update
set role = excluded.role, status = 'active', joined_at = excluded.joined_at;

insert into public.experiments(
  id,organization_id,name,hypothesis,status,primary_metric,stop_rule,starts_at,ends_at
) values
  (
    'e7100000-0000-0000-0000-000000000001',
    'a7100000-0000-0000-0000-000000000001',
    'Atlas onboarding conversion','A shorter onboarding increases activation',
    'draft','activation_rate','{"minimumSample":100}',null,null
  ),
  (
    'e7200000-0000-0000-0000-000000000001',
    'b7200000-0000-0000-0000-000000000001',
    'Beacon response time','A guided brief reduces response time',
    'draft','median_response_time','{"minimumSample":100}',null,null
  )
on conflict (id) do update set
  name=excluded.name,hypothesis=excluded.hypothesis,status='draft',
  primary_metric=excluded.primary_metric,stop_rule=excluded.stop_rule,
  starts_at=null,ends_at=null,result=null;

insert into public.experiment_variants(
  id,organization_id,experiment_id,name,weight,configuration
) values
  ('e7110000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001','e7100000-0000-0000-0000-000000000001','Control',0.5,'{}'),
  ('e7110000-0000-0000-0000-000000000002','a7100000-0000-0000-0000-000000000001','e7100000-0000-0000-0000-000000000001','Guided',0.5,'{}'),
  ('e7210000-0000-0000-0000-000000000001','b7200000-0000-0000-0000-000000000001','e7200000-0000-0000-0000-000000000001','Control',0.5,'{}'),
  ('e7210000-0000-0000-0000-000000000002','b7200000-0000-0000-0000-000000000001','e7200000-0000-0000-0000-000000000001','Guided',0.5,'{}')
on conflict (id) do update set
  name=excluded.name,weight=excluded.weight,configuration=excluded.configuration;
