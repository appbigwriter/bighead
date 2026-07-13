create unique index if not exists event_outbox_run_failed_once_idx
  on public.event_outbox(organization_id,event_type,aggregate_type,aggregate_id)
  where event_type='run.failed';

grant insert on public.event_outbox to service_role;

create or replace function public.claim_runs(
  p_worker text,p_limit integer default 10,p_lease_seconds integer default 60
) returns setof public.runs language plpgsql security invoker set search_path='' as $$
begin
  if current_user <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if length(trim(p_worker))=0 then
    raise exception 'worker_required' using errcode='22023';
  end if;

  with exhausted as (
    update public.runs set status='dead_letter',finished_at=now(),locked_by=null,
      locked_until=null,error_code='lease_recovery_exhausted',
      last_error=coalesce(last_error,'worker_lease_expired')
     where status='running' and locked_until<now() and attempt>=max_attempts
    returning organization_id,id,attempt,max_attempts,error_code
  )
  insert into public.event_outbox(
    organization_id,event_type,aggregate_type,aggregate_id,payload
  )
  select organization_id,'run.failed','run',id,
    jsonb_build_object(
      'runId',id,'status','dead_letter','errorCode',error_code,
      'attempt',attempt,'maxAttempts',max_attempts,'reason','lease_expired'
    )
  from exhausted
  on conflict do nothing;

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
    last_error=case when c.expired then coalesce(r.last_error,'worker_lease_expired')
      else r.last_error end
  from candidates c where r.id=c.id
  returning r.*;
end $$;

create or replace function public.fail_run(
  p_id uuid,p_worker text,p_error text
) returns public.run_status language plpgsql security invoker set search_path='' as $$
declare updated_run public.runs%rowtype;
begin
  if current_user <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  update public.runs set
    status=case when attempt>=max_attempts then 'dead_letter'::public.run_status
      else 'queued'::public.run_status end,
    available_at=case when attempt>=max_attempts then available_at else
      now()+make_interval(secs=>least(
        retry_backoff_seconds*power(2,greatest(attempt-1,0))::integer,86400
      )) end,
    last_error=left(p_error,2000),
    error_code=case when attempt>=max_attempts then 'retry_exhausted'
      else 'retry_scheduled' end,
    finished_at=case when attempt>=max_attempts then now() else null end,
    locked_by=null,locked_until=null
  where id=p_id and status='running' and locked_by=p_worker and locked_until>=now()
  returning * into updated_run;
  if updated_run.id is null then
    raise exception 'run_lease_lost' using errcode='55000';
  end if;
  if updated_run.status='dead_letter' then
    insert into public.event_outbox(
      organization_id,event_type,aggregate_type,aggregate_id,payload
    ) values (
      updated_run.organization_id,'run.failed','run',updated_run.id,
      jsonb_build_object(
        'runId',updated_run.id,'status',updated_run.status,
        'errorCode',updated_run.error_code,'attempt',updated_run.attempt,
        'maxAttempts',updated_run.max_attempts,'reason','retry_exhausted'
      )
    ) on conflict do nothing;
  end if;
  return updated_run.status;
end $$;

revoke execute on function public.claim_runs(text,integer,integer)
  from public,anon,authenticated;
revoke execute on function public.fail_run(uuid,text,text)
  from public,anon,authenticated;
grant execute on function public.claim_runs(text,integer,integer) to service_role;
grant execute on function public.fail_run(uuid,text,text) to service_role;
