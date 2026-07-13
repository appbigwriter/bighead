begin;

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
  on conflict on constraint webhook_deliveries_endpoint_id_event_id_key do nothing;

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

revoke execute on function public.claim_webhook_deliveries(text,integer,integer)
from public,anon,authenticated;
grant execute on function public.claim_webhook_deliveries(text,integer,integer)
to service_role;

commit;
