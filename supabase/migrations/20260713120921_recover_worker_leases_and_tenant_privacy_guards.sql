begin;

alter table private.privacy_requests
  add column side_effect_completed_at timestamptz,
  add column side_effect_evidence jsonb not null default '{}'::jsonb;

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
  if p_worker is null or char_length(p_worker) not between 1 and 200 then raise exception 'invalid_worker'; end if;
  update private.webhook_deliveries d set status='retrying',locked_by=null,locked_until=null,
    available_at=now(),last_error=coalesce(d.last_error,'worker_lease_expired'),updated_at=now()
   where d.status='delivering' and d.locked_until<now();
  insert into private.webhook_deliveries(organization_id,endpoint_id,event_id)
  select e.organization_id,w.id,e.id from public.event_outbox e
  join public.webhook_endpoints w on w.organization_id=e.organization_id
   and w.is_enabled and e.event_type=any(w.event_types) and e.created_at>=w.created_at
  on conflict on constraint webhook_deliveries_endpoint_id_event_id_key do nothing;
  return query with candidates as (
    select d.id from private.webhook_deliveries d
     where d.status in ('pending','retrying') and d.available_at<=now()
       and (d.locked_until is null or d.locked_until<now())
     order by d.available_at,d.created_at for update skip locked limit greatest(p_limit,0)
  ), claimed as (
    update private.webhook_deliveries d set status='delivering',attempts=d.attempts+1,
      locked_by=p_worker,locked_until=now()+make_interval(secs=>p_lease_seconds),updated_at=now()
      from candidates c where d.id=c.id returning d.*
  ) select c.id,c.organization_id,c.endpoint_id,c.event_id,w.url,w.secret_reference,
      e.event_type,e.aggregate_type,e.aggregate_id,e.payload,c.attempts
    from claimed c join public.webhook_endpoints w on w.id=c.endpoint_id
    join public.event_outbox e on e.id=c.event_id;
end $$;

create or replace function public.claim_privacy_requests(
  p_worker text,p_limit integer default 10,p_lease_seconds integer default 60
) returns table(id uuid,organization_id uuid,subject_user_id uuid,request_type text,attempts integer)
language plpgsql security definer set search_path='' as $$
begin
  update private.privacy_requests r set status='requested',locked_by=null,locked_until=null,
    last_error=coalesce(r.last_error,'worker_lease_expired')
   where r.status='processing' and r.locked_until<now();
  update private.privacy_requests r set status='failed',completed_at=now(),
    last_error='privacy_subject_missing'
   where r.status='requested' and r.subject_user_id is null
     and r.side_effect_completed_at is null;
  update private.privacy_requests r set status='blocked',completed_at=now(),
    evidence=r.evidence||'{"legalHold":true}'::jsonb
   where r.status='requested' and r.request_type in ('anonymize','delete') and exists(
    select 1 from private.legal_holds h where h.active
      and h.organization_id=r.organization_id and h.subject_user_id=r.subject_user_id);
  return query with candidates as (
    select r.id from private.privacy_requests r where r.status='requested'
      and (r.subject_user_id is not null or r.side_effect_completed_at is not null)
      and (r.locked_until is null or r.locked_until<now()) order by r.requested_at
      for update skip locked limit greatest(p_limit,0)
  ), claimed as (
    update private.privacy_requests r set status='processing',
      started_at=coalesce(r.started_at,now()),attempts=r.attempts+1,
      locked_by=p_worker,locked_until=now()+make_interval(secs=>p_lease_seconds)
    from candidates c where r.id=c.id returning r.*
  ) select c.id,c.organization_id,c.subject_user_id,c.request_type,c.attempts from claimed c;
end $$;

create or replace function public.execute_privacy_mutation(p_id uuid,p_worker text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare r private.privacy_requests; affected integer; result jsonb;
begin
  select * into r from private.privacy_requests where id=p_id and status='processing'
    and locked_by=p_worker and request_type in ('anonymize','delete') for update;
  if not found then raise exception 'privacy_request_not_leased'; end if;
  if r.side_effect_completed_at is not null then return r.side_effect_evidence; end if;
  if exists(select 1 from private.legal_holds h where h.active
    and h.organization_id=r.organization_id and h.subject_user_id=r.subject_user_id)
  then raise exception 'privacy_legal_hold'; end if;
  if exists(select 1 from public.organization_members m where m.user_id=r.subject_user_id
    and m.organization_id=r.organization_id and m.role='owner' and m.status='active'
    and not exists(select 1 from public.organization_members o where o.organization_id=m.organization_id
      and o.user_id<>m.user_id and o.role='owner' and o.status='active')) then
    raise exception 'privacy_last_owner';
  end if;
  update public.messages set body='[redacted]',author_user_id=null
    where organization_id=r.organization_id and author_user_id=r.subject_user_id;
  get diagnostics affected=row_count;
  update public.tasks set requester_id=null,assignee_id=case when assignee_id=r.subject_user_id
    then null else assignee_id end where organization_id=r.organization_id
    and (requester_id=r.subject_user_id or assignee_id=r.subject_user_id);
  delete from public.organization_members where organization_id=r.organization_id
    and user_id=r.subject_user_id;
  if r.request_type='delete' then
    if exists(select 1 from public.organization_members m where m.user_id=r.subject_user_id) then
      raise exception 'privacy_delete_shared_identity';
    end if;
    delete from auth.users where id=r.subject_user_id;
  elsif not exists(select 1 from public.organization_members m where m.user_id=r.subject_user_id) then
    update public.profiles set display_name='Anonymized user',preferences='{}'
      where id=r.subject_user_id;
    update auth.users set email='anonymized+'||r.subject_user_id||'@invalid.bighead.local',
      phone=null,raw_user_meta_data='{}',updated_at=now() where id=r.subject_user_id;
  end if;
  result := jsonb_build_object('mutation',r.request_type,'messagesRedacted',affected,
    'identityDeleted',r.request_type='delete','auditIdentifiersRetained',true);
  update private.privacy_requests set side_effect_completed_at=now(),
    side_effect_evidence=result where id=r.id;
  return result;
end $$;

revoke execute on function public.claim_webhook_deliveries(text,integer,integer),
 public.claim_privacy_requests(text,integer,integer),
 public.execute_privacy_mutation(uuid,text) from public,anon,authenticated;
grant execute on function public.claim_webhook_deliveries(text,integer,integer),
 public.claim_privacy_requests(text,integer,integer),
 public.execute_privacy_mutation(uuid,text) to service_role;

commit;
