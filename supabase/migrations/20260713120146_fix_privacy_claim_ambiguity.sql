begin;

create or replace function public.claim_privacy_requests(
  p_worker text,p_limit integer default 10,p_lease_seconds integer default 60
) returns table(id uuid,organization_id uuid,subject_user_id uuid,request_type text,attempts integer)
language plpgsql security definer set search_path='' as $$
begin
  update private.privacy_requests r set status='failed',completed_at=now(),
    last_error='privacy_subject_missing'
   where r.status='requested' and r.subject_user_id is null;
  update private.privacy_requests r set status='blocked',completed_at=now(),
    evidence=r.evidence||'{"legalHold":true}'::jsonb
   where r.status='requested' and r.request_type in ('anonymize','delete') and exists(
    select 1 from private.legal_holds h where h.active
      and h.subject_user_id=r.subject_user_id);
  return query with candidates as (
    select r.id from private.privacy_requests r where r.status='requested'
      and r.subject_user_id is not null
      and (r.locked_until is null or r.locked_until<now()) order by r.requested_at
      for update skip locked limit greatest(p_limit,0)
  ), claimed as (
    update private.privacy_requests r set status='processing',
      started_at=coalesce(r.started_at,now()),attempts=r.attempts+1,
      locked_by=p_worker,locked_until=now()+make_interval(secs=>p_lease_seconds)
    from candidates c where r.id=c.id returning r.*
  ) select c.id,c.organization_id,c.subject_user_id,c.request_type,c.attempts from claimed c;
end $$;

revoke execute on function public.claim_privacy_requests(text,integer,integer)
from public,anon,authenticated;
grant execute on function public.claim_privacy_requests(text,integer,integer) to service_role;

commit;
