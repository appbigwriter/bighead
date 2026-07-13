begin;

create extension if not exists citext with schema extensions;

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

do $$ begin
  create type public.member_role as enum ('owner','admin','manager','member','reviewer','analyst');
exception when duplicate_object then null; end $$;
do $$ begin
  create type public.member_status as enum ('invited','active','suspended','removed');
exception when duplicate_object then null; end $$;

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null check (char_length(display_name) between 1 and 120),
  avatar_path text,
  locale text not null default 'pt-BR',
  timezone text not null default 'America/Sao_Paulo',
  preferences jsonb not null default '{}'::jsonb check (jsonb_typeof(preferences) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 2 and 160),
  slug text not null unique check (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
  timezone text not null default 'America/Sao_Paulo',
  locale text not null default 'pt-BR',
  settings jsonb not null default '{}'::jsonb check (jsonb_typeof(settings) = 'object'),
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.organization_members (
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role public.member_role not null default 'member',
  status public.member_status not null default 'active',
  joined_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (organization_id, user_id)
);
create index organization_members_user_active_idx
  on public.organization_members(user_id, organization_id) where status = 'active';

create table public.organization_invites (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  email extensions.citext not null,
  role public.member_role not null default 'member',
  token_hash text not null unique,
  invited_by uuid references auth.users(id) on delete set null,
  expires_at timestamptz not null,
  accepted_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  check (expires_at > created_at)
);
create unique index organization_invites_pending_email_idx
  on public.organization_invites (organization_id, email)
  where accepted_at is null and revoked_at is null;

create or replace function private.set_updated_at()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin new.updated_at = now(); return new; end;
$$;

create or replace function private.current_user_is_member(p_org_id uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.organization_members m
    where m.organization_id = p_org_id
      and m.user_id = (select auth.uid())
      and m.status = 'active'
  );
$$;

create or replace function private.current_user_has_role(p_org_id uuid, p_roles public.member_role[])
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.organization_members m
    where m.organization_id = p_org_id
      and m.user_id = (select auth.uid())
      and m.status = 'active' and m.role = any(p_roles)
  );
$$;

create or replace function private.protect_last_owner()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if old.role = 'owner' and old.status = 'active'
     and (tg_op = 'DELETE' or new.role <> 'owner' or new.status <> 'active')
     and not exists (
       select 1 from public.organization_members m
       where m.organization_id = old.organization_id
         and m.user_id <> old.user_id and m.role = 'owner' and m.status = 'active'
     ) then
    raise exception 'last_owner_required' using errcode = '23514';
  end if;
  if tg_op = 'DELETE' then return old; end if;
  return new;
end;
$$;

create trigger profiles_set_updated_at before update on public.profiles
for each row execute function private.set_updated_at();
create trigger organizations_set_updated_at before update on public.organizations
for each row execute function private.set_updated_at();
create trigger organization_members_set_updated_at before update on public.organization_members
for each row execute function private.set_updated_at();
create trigger organization_members_protect_last_owner
before update or delete on public.organization_members
for each row execute function private.protect_last_owner();

revoke all on all functions in schema private from public, anon, authenticated;
grant usage on schema private to authenticated;
grant execute on function private.current_user_is_member(uuid) to authenticated;
grant execute on function private.current_user_has_role(uuid, public.member_role[]) to authenticated;

alter table public.profiles enable row level security;
alter table public.organizations enable row level security;
alter table public.organization_members enable row level security;
alter table public.organization_invites enable row level security;

create policy profiles_select on public.profiles for select to authenticated
using (id = (select auth.uid()));
create policy profiles_update on public.profiles for update to authenticated
using (id = (select auth.uid())) with check (id = (select auth.uid()));
create policy organizations_select on public.organizations for select to authenticated
using (private.current_user_is_member(id));
create policy organizations_update on public.organizations for update to authenticated
using (private.current_user_has_role(id, array['owner','admin']::public.member_role[]))
with check (private.current_user_has_role(id, array['owner','admin']::public.member_role[]));
create policy organization_members_select on public.organization_members for select to authenticated
using (private.current_user_is_member(organization_id));
create policy organization_invites_select on public.organization_invites for select to authenticated
using (private.current_user_has_role(organization_id, array['owner','admin']::public.member_role[]));

revoke all on all tables in schema public from anon, authenticated;
grant select, update on public.profiles, public.organizations to authenticated;
grant select on public.organization_members, public.organization_invites to authenticated;
grant usage, select on all sequences in schema public to authenticated;

commit;
