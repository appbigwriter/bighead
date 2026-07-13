alter table public.runs
  add column if not exists available_at timestamptz not null default now(),
  add column if not exists max_attempts smallint not null default 3,
  add column if not exists retry_backoff_seconds integer not null default 30,
  add column if not exists last_error text,
  add column if not exists policy_snapshot jsonb not null default '{}'::jsonb;

do $$
begin
  if not exists (select 1 from pg_constraint where conname='runs_max_attempts_check'
    and conrelid='public.runs'::regclass) then
    alter table public.runs add constraint runs_max_attempts_check
      check (max_attempts between 1 and 11);
  end if;
  if not exists (select 1 from pg_constraint where conname='runs_retry_backoff_seconds_check'
    and conrelid='public.runs'::regclass) then
    alter table public.runs add constraint runs_retry_backoff_seconds_check
      check (retry_backoff_seconds between 1 and 3600);
  end if;
  if not exists (select 1 from pg_constraint where conname='runs_policy_snapshot_object_check'
    and conrelid='public.runs'::regclass) then
    alter table public.runs add constraint runs_policy_snapshot_object_check
      check (jsonb_typeof(policy_snapshot)='object');
  end if;
end $$;

drop index if exists public.runs_queue_idx;
create index runs_queue_idx on public.runs(available_at,created_at,id)
  where status='queued';
create index if not exists runs_recoverable_lease_idx on public.runs(locked_until,created_at,id)
  where status='running';

create table if not exists private.run_effect_ledger (
  id bigint generated always as identity primary key,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  run_id uuid not null,
  effect_key text not null,
  effect_type text not null,
  request_fingerprint text not null,
  provider_event_id text,
  created_at timestamptz not null default now(),
  unique(organization_id,effect_key),
  foreign key(organization_id,run_id) references public.runs(organization_id,id) on delete cascade,
  check (length(effect_key) between 8 and 240),
  check (length(request_fingerprint) between 16 and 128)
);
create index if not exists run_effect_ledger_run_idx
  on private.run_effect_ledger(organization_id,run_id,created_at);

create or replace function public.claim_runs(
  p_worker text,p_limit integer default 10,p_lease_seconds integer default 60
) returns setof public.runs language plpgsql security invoker set search_path='' as $$
begin
  if current_user <> 'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if length(trim(p_worker))=0 then raise exception 'worker_required' using errcode='22023'; end if;
  update public.runs set status='dead_letter',finished_at=now(),locked_by=null,locked_until=null,
    error_code='lease_recovery_exhausted',last_error=coalesce(last_error,'worker_lease_expired')
   where status='running' and locked_until<now() and attempt>=max_attempts;
  return query
  with candidates as (
    select r.id,(r.status='running' or r.error_code='retry_scheduled') retry_attempt,
      (r.status='running') expired
      from public.runs r
     where ((r.status='queued' and r.available_at<=now())
        or (r.status='running' and r.locked_until<now()))
       and (r.error_code is distinct from 'retry_scheduled' or r.attempt<r.max_attempts)
       and (r.status is distinct from 'running' or r.attempt<r.max_attempts)
     order by case when r.status='running' then 0 else 1 end,r.available_at,r.created_at,r.id
     for update skip locked limit least(greatest(p_limit,1),100)
  )
  update public.runs r set
    status='running',
    attempt=r.attempt+case when c.retry_attempt then 1 else 0 end,
    locked_by=p_worker,
    locked_until=now()+make_interval(secs=>least(greatest(p_lease_seconds,10),900)),
    heartbeat_at=now(),
    started_at=coalesce(r.started_at,now()),
    error_code=null,
    last_error=case when c.expired then coalesce(r.last_error,'worker_lease_expired') else r.last_error end
  from candidates c where r.id=c.id
  returning r.*;
end $$;

create or replace function public.heartbeat_run(
  p_id uuid,p_worker text,p_lease_seconds integer default 60
) returns boolean language sql security invoker set search_path='' as $$
  update public.runs set heartbeat_at=now(),
    locked_until=now()+make_interval(secs=>least(greatest(p_lease_seconds,10),900))
   where id=p_id and status='running' and locked_by=p_worker and locked_until>=now()
  returning true
$$;

create or replace function public.register_run_effect(
  p_run_id uuid,p_worker text,p_effect_key text,p_effect_type text,p_request_fingerprint text
) returns boolean language plpgsql security invoker set search_path='' as $$
declare inserted_count integer;
begin
  if current_user <> 'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if not exists(select 1 from public.runs where id=p_run_id and status='running'
    and locked_by=p_worker and locked_until>=now()) then
    raise exception 'run_lease_lost' using errcode='55000';
  end if;
  insert into private.run_effect_ledger(organization_id,run_id,effect_key,effect_type,request_fingerprint)
  select organization_id,id,p_effect_key,p_effect_type,p_request_fingerprint from public.runs where id=p_run_id
  on conflict(organization_id,effect_key) do nothing;
  get diagnostics inserted_count=row_count;
  return inserted_count=1;
end $$;

create or replace function public.complete_run(
  p_id uuid,p_worker text,p_effect_key text,p_provider_event_id text,
  p_amount numeric default 0,p_currency text default 'USD'
) returns boolean language plpgsql security invoker set search_path='' as $$
declare run_row public.runs%rowtype;
begin
  if current_user <> 'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  select * into run_row from public.runs where id=p_id and status='running'
    and locked_by=p_worker and locked_until>=now() for update;
  if not found then return false; end if;
  update private.run_effect_ledger set provider_event_id=coalesce(provider_event_id,p_provider_event_id)
    where organization_id=run_row.organization_id and run_id=p_id and effect_key=p_effect_key;
  if not found then raise exception 'effect_not_registered' using errcode='55000'; end if;
  if p_provider_event_id is not null then
    insert into public.cost_events(organization_id,task_id,run_id,provider_event_id,amount,currency)
    values(run_row.organization_id,run_row.task_id,p_id,p_provider_event_id,greatest(p_amount,0),upper(p_currency)::char(3))
    on conflict(organization_id,provider_event_id) do nothing;
  end if;
  update public.runs set status='succeeded',finished_at=now(),locked_by=null,locked_until=null,
    heartbeat_at=now(),last_error=null where id=p_id;
  return true;
end $$;

create or replace function public.fail_run(
  p_id uuid,p_worker text,p_error text
) returns public.run_status language plpgsql security invoker set search_path='' as $$
declare next_status public.run_status;
begin
  if current_user <> 'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  update public.runs set
    status=case when attempt>=max_attempts then 'dead_letter'::public.run_status else 'queued'::public.run_status end,
    available_at=case when attempt>=max_attempts then available_at else
      now()+make_interval(secs=>least(retry_backoff_seconds*power(2,greatest(attempt-1,0))::integer,86400)) end,
    last_error=left(p_error,2000),error_code=case when attempt>=max_attempts then 'retry_exhausted' else 'retry_scheduled' end,
    finished_at=case when attempt>=max_attempts then now() else null end,
    locked_by=null,locked_until=null
  where id=p_id and status='running' and locked_by=p_worker
  returning status into next_status;
  if next_status is null then raise exception 'run_lease_lost' using errcode='55000'; end if;
  return next_status;
end $$;

create or replace function public.reconcile_run_cost(p_run_id uuid)
returns table(provider_total numeric,task_total numeric,provider_events bigint,task_events bigint,reconciled boolean)
language sql stable security invoker set search_path='' as $$
  select coalesce(sum(c.amount),0),
    coalesce(sum(c.amount) filter(where c.task_id=r.task_id),0),
    count(c.id),count(c.id) filter(where c.task_id=r.task_id),
    count(c.id)=count(c.id) filter(where c.task_id=r.task_id)
      and coalesce(sum(c.amount),0)=coalesce(sum(c.amount) filter(where c.task_id=r.task_id),0)
  from public.runs r left join public.cost_events c
    on c.organization_id=r.organization_id and c.run_id=r.id
  where r.id=p_run_id group by r.id
$$;

revoke all on private.run_effect_ledger from public,anon,authenticated;
revoke execute on function public.claim_runs(text,integer,integer) from public,anon,authenticated;
revoke execute on function public.heartbeat_run(uuid,text,integer) from public,anon,authenticated;
revoke execute on function public.register_run_effect(uuid,text,text,text,text) from public,anon,authenticated;
revoke execute on function public.complete_run(uuid,text,text,text,numeric,text) from public,anon,authenticated;
revoke execute on function public.fail_run(uuid,text,text) from public,anon,authenticated;
revoke execute on function public.reconcile_run_cost(uuid) from public,anon,authenticated;
grant execute on function public.claim_runs(text,integer,integer) to service_role;
grant execute on function public.heartbeat_run(uuid,text,integer) to service_role;
grant execute on function public.register_run_effect(uuid,text,text,text,text) to service_role;
grant execute on function public.complete_run(uuid,text,text,text,numeric,text) to service_role;
grant execute on function public.fail_run(uuid,text,text) to service_role;
grant execute on function public.reconcile_run_cost(uuid) to service_role;
