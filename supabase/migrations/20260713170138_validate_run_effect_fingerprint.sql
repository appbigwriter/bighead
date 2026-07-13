create or replace function public.register_run_effect(
  p_run_id uuid,p_worker text,p_effect_key text,p_effect_type text,p_request_fingerprint text
) returns boolean language plpgsql security invoker set search_path='' as $$
declare
  inserted_count integer;
  existing private.run_effect_ledger%rowtype;
begin
  if current_user <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if not exists(
    select 1 from public.runs where id=p_run_id and status='running'
      and locked_by=p_worker and locked_until>=now()
  ) then
    raise exception 'run_lease_lost' using errcode='55000';
  end if;

  insert into private.run_effect_ledger(
    organization_id,run_id,effect_key,effect_type,request_fingerprint
  )
  select organization_id,id,p_effect_key,p_effect_type,p_request_fingerprint
    from public.runs where id=p_run_id
  on conflict(organization_id,effect_key) do nothing;
  get diagnostics inserted_count=row_count;
  if inserted_count=1 then return true; end if;

  select ledger.* into existing
    from private.run_effect_ledger ledger
    join public.runs run on run.organization_id=ledger.organization_id
   where run.id=p_run_id and ledger.effect_key=p_effect_key;
  if not found
    or existing.run_id is distinct from p_run_id
    or existing.effect_type is distinct from p_effect_type
    or existing.request_fingerprint is distinct from p_request_fingerprint then
    raise exception 'idempotency_conflict' using errcode='23505';
  end if;
  return false;
end $$;

revoke execute on function public.register_run_effect(uuid,text,text,text,text)
  from public,anon,authenticated;
grant execute on function public.register_run_effect(uuid,text,text,text,text)
  to service_role;
