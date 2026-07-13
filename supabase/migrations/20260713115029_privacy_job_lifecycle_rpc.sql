begin;

create or replace function private.protect_running_experiment()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if old.status <> 'draft' and new.status='draft' then
    raise exception 'experiment_cannot_return_to_draft' using errcode='23514';
  end if;
  if old.status <> 'draft'
     and (new.campaign_id,new.name,new.hypothesis,new.primary_metric,new.allocation,
          new.stop_rule,new.starts_at,new.ends_at)
       is distinct from
         (old.campaign_id,old.name,old.hypothesis,old.primary_metric,old.allocation,
          old.stop_rule,old.starts_at,old.ends_at) then
    raise exception 'running_experiment_configuration_immutable' using errcode='23514';
  end if;
  return new;
end $$;

create or replace function private.enforce_tenant_budget()
returns trigger language plpgsql security definer set search_path = '' as $$
declare cfg jsonb; spent numeric; used_tokens bigint; amount_limit numeric; token_limit bigint;
declare budget_action text; quota_action text;
begin
  select settings into cfg from public.organizations where id=new.organization_id;
  budget_action := coalesce(cfg->'budgets'->>'exceededAction','alert');
  quota_action := coalesce(cfg->'quotas'->>'exceededAction','alert');
  if budget_action<>'block' and quota_action<>'block' then return new; end if;
  amount_limit := nullif(coalesce(cfg->'budgets'->>'limit',cfg->'budgets'->>'amount'),'')::numeric;
  token_limit := nullif(coalesce(cfg->'quotas'->>'tokens',cfg->'quotas'->>'tokenLimit'),'')::bigint;
  select coalesce(sum(amount),0),coalesce(sum(input_tokens+output_tokens),0)
    into spent,used_tokens from public.cost_events
   where organization_id=new.organization_id and occurred_at>=date_trunc('month',now());
  if (budget_action='block' and amount_limit>0 and spent>=amount_limit)
     or (quota_action='block' and token_limit>0 and used_tokens>=token_limit) then
    raise exception 'tenant_budget_exceeded' using errcode='P0001';
  end if;
  return new;
end $$;

-- Only events created after endpoint registration are eligible for fan-out.
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
revoke execute on function public.claim_webhook_deliveries(text,integer,integer)
from public,anon,authenticated;
grant execute on function public.claim_webhook_deliveries(text,integer,integer) to service_role;

alter table private.privacy_requests add column attempts integer not null default 0,
  add column locked_by text,add column locked_until timestamptz;

create or replace function public.claim_privacy_requests(
  p_worker text,p_limit integer default 10,p_lease_seconds integer default 60
) returns table(id uuid,organization_id uuid,subject_user_id uuid,request_type text,attempts integer)
language plpgsql security definer set search_path='' as $$
begin
  update private.privacy_requests set status='failed',completed_at=now(),
    last_error='privacy_subject_missing' where status='requested' and subject_user_id is null;
  update private.privacy_requests r set status='blocked',completed_at=now(),
    evidence=r.evidence||'{"legalHold":true}'::jsonb
   where r.status='requested' and r.request_type in ('anonymize','delete') and exists(
    select 1 from private.legal_holds h where h.active and h.subject_user_id=r.subject_user_id);
  return query with candidates as (
    select r.id from private.privacy_requests r where r.status='requested'
      and r.subject_user_id is not null
      and (r.locked_until is null or r.locked_until<now()) order by r.requested_at
      for update skip locked limit greatest(p_limit,0)
  ), claimed as (
    update private.privacy_requests r set status='processing',started_at=coalesce(started_at,now()),
      attempts=r.attempts+1,locked_by=p_worker,
      locked_until=now()+make_interval(secs=>p_lease_seconds)
    from candidates c where r.id=c.id returning r.*
  ) select c.id,c.organization_id,c.subject_user_id,c.request_type,c.attempts from claimed c;
end $$;

create or replace function public.complete_privacy_request(
  p_id uuid,p_worker text,p_evidence jsonb
) returns boolean language plpgsql security definer set search_path='' as $$
declare changed integer;
begin
  update private.privacy_requests set status='completed',completed_at=now(),
    evidence=evidence||coalesce(p_evidence,'{}'),locked_by=null,locked_until=null,last_error=null
   where id=p_id and status='processing' and locked_by=p_worker;
  get diagnostics changed=row_count; return changed=1;
end $$;

create or replace function public.fail_privacy_request(
  p_id uuid,p_worker text,p_error text,p_max_attempts integer default 5
) returns boolean language plpgsql security definer set search_path='' as $$
declare changed integer;
begin
  update private.privacy_requests set status=case when attempts>=p_max_attempts then 'failed' else 'requested' end,
    last_error=left(p_error,2000),locked_by=null,locked_until=null,
    completed_at=case when attempts>=p_max_attempts then now() else null end
   where id=p_id and status='processing' and locked_by=p_worker;
  get diagnostics changed=row_count; return changed=1;
end $$;

create or replace function public.build_privacy_export(p_id uuid,p_worker text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare r private.privacy_requests; result jsonb;
begin
  select * into r from private.privacy_requests where id=p_id and status='processing'
    and locked_by=p_worker and request_type='export';
  if not found then raise exception 'privacy_request_not_leased'; end if;
  select jsonb_build_object(
    'requestId',r.id,'organizationId',r.organization_id,'subjectUserId',r.subject_user_id,
    'generatedAt',now(),
    'profile',(select to_jsonb(p)-array['updated_at'] from public.profiles p where p.id=r.subject_user_id),
    'memberships',(select coalesce(jsonb_agg(to_jsonb(m)),'[]') from public.organization_members m
      where m.organization_id=r.organization_id and m.user_id=r.subject_user_id),
    'tasks',(select coalesce(jsonb_agg(to_jsonb(t)),'[]') from public.tasks t
      where t.organization_id=r.organization_id and t.requester_id=r.subject_user_id),
    'messages',(select coalesce(jsonb_agg(to_jsonb(m)),'[]') from public.messages m
      where m.organization_id=r.organization_id and m.author_user_id=r.subject_user_id),
    'audit',(select coalesce(jsonb_agg(to_jsonb(a)),'[]') from public.audit_log a
      where a.organization_id=r.organization_id and a.actor_user_id=r.subject_user_id)
  ) into result;
  return result;
end $$;

create or replace function public.execute_privacy_mutation(p_id uuid,p_worker text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare r private.privacy_requests; affected integer;
begin
  select * into r from private.privacy_requests where id=p_id and status='processing'
    and locked_by=p_worker and request_type in ('anonymize','delete') for update;
  if not found then raise exception 'privacy_request_not_leased'; end if;
  if exists(select 1 from private.legal_holds h where h.active and h.subject_user_id=r.subject_user_id)
  then raise exception 'privacy_legal_hold'; end if;
  update public.messages set body='[redacted]' where organization_id=r.organization_id
    and author_user_id=r.subject_user_id;
  get diagnostics affected=row_count;
  update public.profiles set display_name='Anonymized user',preferences='{}'
    where id=r.subject_user_id;
  if r.request_type='delete' then
    if exists(select 1 from public.organization_members m where m.user_id=r.subject_user_id
      and m.organization_id<>r.organization_id) then
      raise exception 'privacy_delete_shared_identity';
    end if;
    if exists(select 1 from public.organization_members m where m.user_id=r.subject_user_id
      and m.organization_id=r.organization_id and m.role='owner' and m.status='active'
      and not exists(select 1 from public.organization_members o where o.organization_id=m.organization_id
        and o.user_id<>m.user_id and o.role='owner' and o.status='active')) then
      raise exception 'privacy_delete_last_owner';
    end if;
    delete from auth.users where id=r.subject_user_id;
  end if;
  return jsonb_build_object('mutation',r.request_type,'messagesRedacted',affected,
    'identityDeleted',r.request_type='delete');
end $$;

revoke execute on function public.claim_privacy_requests(text,integer,integer),
 public.complete_privacy_request(uuid,text,jsonb),
 public.fail_privacy_request(uuid,text,text,integer),
 public.build_privacy_export(uuid,text),public.execute_privacy_mutation(uuid,text)
 from public,anon,authenticated;
grant execute on function public.claim_privacy_requests(text,integer,integer),
 public.complete_privacy_request(uuid,text,jsonb),
 public.fail_privacy_request(uuid,text,text,integer),
 public.build_privacy_export(uuid,text),public.execute_privacy_mutation(uuid,text)
 to service_role;

commit;
