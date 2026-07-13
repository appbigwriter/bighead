create or replace function public.fail_run(
  p_id uuid,p_worker text,p_error text
) returns public.run_status language plpgsql security invoker set search_path='' as $$
declare next_status public.run_status;
begin
  if current_user <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  update public.runs set
    status=case when attempt>=max_attempts then 'dead_letter'::public.run_status else 'queued'::public.run_status end,
    available_at=case when attempt>=max_attempts then available_at else
      now()+make_interval(secs=>least(retry_backoff_seconds*power(2,greatest(attempt-1,0))::integer,86400)) end,
    last_error=left(p_error,2000),
    error_code=case when attempt>=max_attempts then 'retry_exhausted' else 'retry_scheduled' end,
    finished_at=case when attempt>=max_attempts then now() else null end,
    locked_by=null,locked_until=null
  where id=p_id and status='running' and locked_by=p_worker and locked_until>=now()
  returning status into next_status;
  if next_status is null then
    raise exception 'run_lease_lost' using errcode='55000';
  end if;
  return next_status;
end $$;

revoke execute on function public.fail_run(uuid,text,text) from public,anon,authenticated;
grant execute on function public.fail_run(uuid,text,text) to service_role;
