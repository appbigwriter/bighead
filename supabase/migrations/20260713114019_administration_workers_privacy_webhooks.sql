begin;

create table private.webhook_deliveries (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  endpoint_id uuid not null references public.webhook_endpoints(id) on delete cascade,
  event_id uuid not null references public.event_outbox(id) on delete cascade,
  status text not null default 'pending'
    check (status in ('pending','delivering','retrying','delivered','dead_letter')),
  attempts integer not null default 0 check (attempts >= 0),
  available_at timestamptz not null default now(),
  locked_by text,
  locked_until timestamptz,
  response_status integer,
  response_body_hash text,
  last_error text,
  delivered_at timestamptz,
  dead_lettered_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (endpoint_id, event_id)
);
create index webhook_deliveries_claim_idx
on private.webhook_deliveries(available_at, created_at)
where status in ('pending','retrying');
revoke all on private.webhook_deliveries from public, anon, authenticated;

create or replace function public.claim_webhook_deliveries(
  p_worker text, p_limit integer default 25, p_lease_seconds integer default 30
)
returns table (
  id uuid, organization_id uuid, endpoint_id uuid, event_id uuid, url text,
  secret_reference text, event_type text, aggregate_type text,
  aggregate_id uuid, payload jsonb, attempts integer
)
language plpgsql security definer set search_path = '' as $$
begin
  if p_worker is null or char_length(p_worker) not between 1 and 200 then
    raise exception 'invalid_worker';
  end if;
  insert into private.webhook_deliveries(organization_id,endpoint_id,event_id)
  select e.organization_id,w.id,e.id
    from public.event_outbox e
    join public.webhook_endpoints w on w.organization_id=e.organization_id
     and w.is_enabled and e.event_type=any(w.event_types)
  on conflict (endpoint_id,event_id) do nothing;

  return query
  with candidates as (
    select d.id from private.webhook_deliveries d
     where d.status in ('pending','retrying') and d.available_at<=now()
       and (d.locked_until is null or d.locked_until<now())
     order by d.available_at,d.created_at for update skip locked limit greatest(p_limit,0)
  ), claimed as (
    update private.webhook_deliveries d set status='delivering',attempts=d.attempts+1,
      locked_by=p_worker,locked_until=now()+make_interval(secs=>p_lease_seconds),updated_at=now()
      from candidates c where d.id=c.id returning d.*
  )
  select c.id,c.organization_id,c.endpoint_id,c.event_id,w.url,w.secret_reference,
         e.event_type,e.aggregate_type,e.aggregate_id,e.payload,c.attempts
    from claimed c join public.webhook_endpoints w on w.id=c.endpoint_id
    join public.event_outbox e on e.id=c.event_id;
end $$;

create or replace function public.ack_webhook_delivery(
  p_id uuid, p_worker text, p_response_status integer, p_response_body_hash text
) returns boolean language plpgsql security definer set search_path = '' as $$
declare changed integer;
begin
  update private.webhook_deliveries set status='delivered',delivered_at=now(),
    response_status=p_response_status,response_body_hash=p_response_body_hash,
    last_error=null,locked_by=null,locked_until=null,updated_at=now()
   where id=p_id and locked_by=p_worker and status='delivering';
  get diagnostics changed = row_count;
  return changed=1;
end $$;

create or replace function public.nack_webhook_delivery(
  p_id uuid, p_worker text, p_error text, p_response_status integer default null,
  p_max_attempts integer default 8
) returns boolean language plpgsql security definer set search_path = '' as $$
declare changed integer;
begin
  update private.webhook_deliveries set
    status=case when attempts>=p_max_attempts then 'dead_letter' else 'retrying' end,
    dead_lettered_at=case when attempts>=p_max_attempts then now() else null end,
    available_at=now()+make_interval(secs=>least(300,power(2,attempts)::integer)),
    response_status=p_response_status,last_error=left(p_error,2000),
    locked_by=null,locked_until=null,updated_at=now()
   where id=p_id and locked_by=p_worker and status='delivering';
  get diagnostics changed = row_count;
  return changed=1;
end $$;

create or replace function public.resolve_webhook_secret(p_reference text)
returns text language plpgsql security definer set search_path = '' as $$
declare resolved text;
begin
  if p_reference is null or p_reference='' then raise exception 'invalid_secret_reference'; end if;
  begin
    execute 'select decrypted_secret from vault.decrypted_secrets where name=$1 order by created_at desc limit 1'
      into resolved using p_reference;
  exception when undefined_table or invalid_schema_name then
    raise exception 'vault_unavailable';
  end;
  if resolved is null then raise exception 'webhook_secret_not_found'; end if;
  return resolved;
end $$;

revoke execute on function public.claim_webhook_deliveries(text,integer,integer) from public,anon,authenticated;
revoke execute on function public.ack_webhook_delivery(uuid,text,integer,text) from public,anon,authenticated;
revoke execute on function public.nack_webhook_delivery(uuid,text,text,integer,integer) from public,anon,authenticated;
revoke execute on function public.resolve_webhook_secret(text) from public,anon,authenticated;
grant execute on function public.claim_webhook_deliveries(text,integer,integer) to service_role;
grant execute on function public.ack_webhook_delivery(uuid,text,integer,text) to service_role;
grant execute on function public.nack_webhook_delivery(uuid,text,text,integer,integer) to service_role;
grant execute on function public.resolve_webhook_secret(text) to service_role;

create table private.retention_policies (
  organization_id uuid primary key references public.organizations(id) on delete cascade,
  audit_days integer not null default 2555 check (audit_days>=365),
  analytics_days integer not null default 730 check (analytics_days>=30),
  updated_by uuid references auth.users(id) on delete set null,
  updated_at timestamptz not null default now()
);
create table private.legal_holds (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  subject_user_id uuid references auth.users(id) on delete restrict,
  reason text not null,
  active boolean not null default true,
  created_by uuid references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(), released_at timestamptz
);
create unique index legal_holds_active_subject_idx
on private.legal_holds(organization_id,subject_user_id) where active;
create table private.privacy_requests (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  subject_user_id uuid references auth.users(id) on delete set null,
  request_type text not null check (request_type in ('export','anonymize','delete')),
  status text not null default 'requested'
    check (status in ('requested','processing','completed','blocked','failed')),
  idempotency_key text not null,
  evidence jsonb not null default '{}'::jsonb,
  requested_by uuid references auth.users(id) on delete set null,
  requested_at timestamptz not null default now(),
  started_at timestamptz,completed_at timestamptz,last_error text,
  unique (organization_id,idempotency_key)
);
create index privacy_requests_claim_idx on private.privacy_requests(requested_at)
where status='requested';
revoke all on private.retention_policies,private.legal_holds,private.privacy_requests
from public,anon,authenticated;

-- Hard budget/quota enforcement applies before additional work is accepted.
create or replace function private.enforce_tenant_budget()
returns trigger language plpgsql security definer set search_path = '' as $$
declare cfg jsonb; spent numeric; used_tokens bigint; amount_limit numeric; token_limit bigint;
begin
  select settings into cfg from public.organizations where id=new.organization_id;
  if coalesce(cfg->'budgets'->>'exceededAction','alert') <> 'block' then return new; end if;
  amount_limit := nullif(cfg->'budgets'->>'limit','')::numeric;
  token_limit := nullif(cfg->'quotas'->>'tokenLimit','')::bigint;
  select coalesce(sum(amount),0),coalesce(sum(input_tokens+output_tokens),0)
    into spent,used_tokens from public.cost_events
   where organization_id=new.organization_id and occurred_at>=date_trunc('month',now());
  if (amount_limit is not null and spent>=amount_limit)
     or (token_limit is not null and used_tokens>=token_limit) then
    raise exception 'tenant_budget_exceeded' using errcode='P0001';
  end if;
  return new;
end $$;
revoke all on function private.enforce_tenant_budget() from public,anon,authenticated;
create trigger tasks_enforce_tenant_budget before insert on public.tasks
for each row execute function private.enforce_tenant_budget();
create trigger runs_enforce_tenant_budget before insert on public.runs
for each row execute function private.enforce_tenant_budget();

commit;
