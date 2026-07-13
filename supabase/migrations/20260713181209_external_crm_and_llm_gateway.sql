-- External CRM control plane. Credentials are secret-manager references only.
create table public.crm_connections (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  provider_key text not null check (provider_key ~ '^[a-z0-9][a-z0-9_-]{1,62}$'),
  display_name text not null,
  secret_ref text not null check (secret_ref ~ '^[A-Za-z0-9/_:.-]{3,500}$'),
  status text not null default 'active' check (status in ('active','paused','error','revoked')),
  webhook_secret_ref text check (webhook_secret_ref ~ '^[A-Za-z0-9/_:.-]{3,500}$'),
  configuration jsonb not null default '{}'::jsonb,
  last_synced_at timestamptz,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, provider_key, display_name),
  unique (organization_id, id)
);

create table public.crm_sync_cursors (
  connection_id uuid primary key,
  organization_id uuid not null,
  cursor text,
  high_watermark timestamptz,
  version bigint not null default 0 check (version >= 0),
  updated_at timestamptz not null default now(),
  foreign key (organization_id, connection_id)
    references public.crm_connections(organization_id, id) on delete cascade
);

create table public.crm_external_links (
  organization_id uuid not null,
  connection_id uuid not null,
  entity_type text not null check (entity_type in ('account','contact','lead','opportunity')),
  external_id text not null,
  local_id uuid not null,
  external_updated_at timestamptz,
  payload_hash text not null check (payload_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (connection_id, entity_type, external_id),
  unique (connection_id, entity_type, local_id),
  foreign key (organization_id, connection_id)
    references public.crm_connections(organization_id, id) on delete cascade
);

create table public.crm_webhook_inbox (
  id bigint generated always as identity primary key,
  organization_id uuid not null,
  connection_id uuid not null,
  provider_event_id text not null,
  event_type text not null,
  payload jsonb not null,
  payload_hash text not null check (payload_hash ~ '^[0-9a-f]{64}$'),
  occurred_at timestamptz,
  received_at timestamptz not null default now(),
  status text not null default 'pending' check (status in ('pending','processing','completed','failed','ignored')),
  attempts integer not null default 0 check (attempts >= 0),
  last_error text,
  processed_at timestamptz,
  unique (connection_id, provider_event_id),
  foreign key (organization_id, connection_id)
    references public.crm_connections(organization_id, id) on delete cascade
);

create table public.crm_effect_ledger (
  id bigint generated always as identity primary key,
  organization_id uuid not null,
  connection_id uuid not null,
  idempotency_key text not null,
  operation text not null,
  request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
  provider_event_id text,
  status text not null default 'reserved' check (status in ('reserved','completed','failed','unknown')),
  response_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  unique (connection_id, idempotency_key),
  foreign key (organization_id, connection_id)
    references public.crm_connections(organization_id, id) on delete cascade
);

create index crm_connections_org_status_idx on public.crm_connections(organization_id, status);
create index crm_webhook_inbox_pending_idx on public.crm_webhook_inbox(status, received_at) where status in ('pending','failed');
create index crm_effect_ledger_unknown_idx on public.crm_effect_ledger(connection_id, created_at) where status in ('reserved','unknown');

create trigger crm_connections_updated_at before update on public.crm_connections
for each row execute function private.set_updated_at();
create trigger crm_external_links_updated_at before update on public.crm_external_links
for each row execute function private.set_updated_at();

alter table public.crm_connections enable row level security;
alter table public.crm_sync_cursors enable row level security;
alter table public.crm_external_links enable row level security;
alter table public.crm_webhook_inbox enable row level security;
alter table public.crm_effect_ledger enable row level security;

create policy crm_connections_select on public.crm_connections for select to authenticated
using (private.current_user_has_role(organization_id, array['owner','admin','manager']::public.member_role[]));
create policy crm_connections_insert on public.crm_connections for insert to authenticated
with check (private.current_user_has_role(organization_id, array['owner','admin']::public.member_role[]) and created_by = (select auth.uid()));
create policy crm_connections_update on public.crm_connections for update to authenticated
using (private.current_user_has_role(organization_id, array['owner','admin']::public.member_role[]))
with check (private.current_user_has_role(organization_id, array['owner','admin']::public.member_role[]));
create policy crm_connections_delete on public.crm_connections for delete to authenticated
using (private.current_user_has_role(organization_id, array['owner','admin']::public.member_role[]));

do $$ declare t text; begin
  foreach t in array array['crm_sync_cursors','crm_external_links','crm_webhook_inbox','crm_effect_ledger'] loop
    execute format('create policy %I on public.%I for select to authenticated using (private.current_user_has_role(organization_id, array[''owner'',''admin'',''manager'']::public.member_role[]))', t || '_select', t);
  end loop;
end $$;

-- Runtime writes use the dedicated server role. Browser clients receive read-only
-- admin visibility and cannot forge cursors, webhook receipts or effect records.
grant select, insert, update, delete on public.crm_connections to authenticated;
grant select on public.crm_sync_cursors, public.crm_external_links, public.crm_webhook_inbox, public.crm_effect_ledger to authenticated;
grant usage, select on sequence public.crm_webhook_inbox_id_seq, public.crm_effect_ledger_id_seq to authenticated;
