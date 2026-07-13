create or replace function private.protect_published_scorecard_version()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if old.published_at is not null then
    raise exception 'published_scorecard_version_immutable' using errcode = '23514';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end;
$$;

revoke all on function private.protect_published_scorecard_version() from public;
revoke all on function private.protect_published_scorecard_version() from anon, authenticated;

drop trigger if exists qa_scorecards_protect_published_version on public.qa_scorecards;
create trigger qa_scorecards_protect_published_version
before update or delete on public.qa_scorecards
for each row execute function private.protect_published_scorecard_version();

create or replace function private.require_published_evaluation_scorecard()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  scorecard_is_published boolean;
begin
  select scorecard.published_at is not null
    into scorecard_is_published
    from public.qa_scorecards as scorecard
   where scorecard.organization_id = new.organization_id
     and scorecard.id = new.scorecard_id
   for key share;

  if scorecard_is_published is not true then
    raise exception 'qa_evaluation_requires_published_scorecard' using errcode = '23514';
  end if;
  return new;
end;
$$;

create or replace function private.protect_qa_evaluation_history()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'qa_evaluation_immutable' using errcode = '23514';
end;
$$;

revoke all on function private.require_published_evaluation_scorecard() from public;
revoke all on function private.require_published_evaluation_scorecard() from anon, authenticated;
revoke all on function private.protect_qa_evaluation_history() from public;
revoke all on function private.protect_qa_evaluation_history() from anon, authenticated;

drop trigger if exists qa_evaluations_require_published_scorecard on public.qa_evaluations;
create trigger qa_evaluations_require_published_scorecard
before insert on public.qa_evaluations
for each row execute function private.require_published_evaluation_scorecard();

drop trigger if exists qa_evaluations_protect_history on public.qa_evaluations;
create trigger qa_evaluations_protect_history
before update or delete on public.qa_evaluations
for each row execute function private.protect_qa_evaluation_history();

alter table public.artifacts
  add column if not exists scan_attempts integer not null default 0,
  add column if not exists scan_available_at timestamptz not null default now(),
  add column if not exists scan_locked_by text,
  add column if not exists scan_locked_until timestamptz,
  add column if not exists scan_last_error text;

create index if not exists artifacts_pending_scan_idx
  on public.artifacts(scan_available_at, created_at)
  where quarantine_status = 'pending';

create or replace function public.claim_artifact_scans(
  p_worker text, p_limit integer default 25, p_lease_seconds integer default 60
)
returns table(artifact_id uuid)
language sql
security definer
set search_path = ''
as $$
  with candidates as (
    select artifact.id
      from public.artifacts as artifact
     where artifact.quarantine_status = 'pending'
       and artifact.scan_available_at <= now()
       and (artifact.scan_locked_until is null or artifact.scan_locked_until < now())
     order by artifact.scan_available_at, artifact.created_at
     for update skip locked
     limit least(greatest(p_limit, 1), 100)
  ), claimed as (
    update public.artifacts as artifact
       set scan_attempts = artifact.scan_attempts + 1,
           scan_locked_by = p_worker,
           scan_locked_until = now() + make_interval(
             secs => least(greatest(p_lease_seconds, 10), 900)
           ),
           scan_last_error = case
             when artifact.scan_locked_until < now()
             then coalesce(artifact.scan_last_error, 'scan_lease_expired')
             else artifact.scan_last_error
           end
      from candidates
     where artifact.id = candidates.id
     returning artifact.id
  )
  select claimed.id from claimed;
$$;

create or replace function public.retry_artifact_scan(
  p_artifact_id uuid, p_worker text, p_error text
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  updated boolean;
begin
  update public.artifacts as artifact
     set scan_available_at = now() + make_interval(
           secs => least(3600, (power(2, least(artifact.scan_attempts, 10)) * 5)::integer)
         ),
         scan_locked_by = null,
         scan_locked_until = null,
         scan_last_error = left(p_error, 500)
   where artifact.id = p_artifact_id
     and artifact.quarantine_status = 'pending'
     and artifact.scan_locked_by = p_worker;
  updated := found;
  return updated;
end;
$$;

create or replace function public.complete_artifact_scan(
  p_artifact_id uuid,
  p_worker text,
  p_clean boolean,
  p_actual_mime_type text,
  p_actual_size_bytes bigint,
  p_actual_checksum_sha256 text,
  p_reason text
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  updated boolean;
begin
  update public.artifacts as artifact
     set quarantine_status = case
           when p_clean then 'clean'::public.artifact_quarantine_status
           else 'rejected'::public.artifact_quarantine_status
         end,
         metadata = artifact.metadata || jsonb_build_object(
           'actual_mime_type', p_actual_mime_type,
           'actual_size_bytes', p_actual_size_bytes,
           'actual_checksum_sha256', p_actual_checksum_sha256,
           'rejection_reason', p_reason
         ),
         scan_locked_by = null,
         scan_locked_until = null,
         scan_last_error = p_reason
   where artifact.id = p_artifact_id
     and artifact.quarantine_status = 'pending'
     and artifact.scan_locked_by = p_worker;
  updated := found;
  return updated;
end;
$$;

revoke all on function public.claim_artifact_scans(text, integer, integer) from public, anon, authenticated;
revoke all on function public.retry_artifact_scan(uuid, text, text) from public, anon, authenticated;
revoke all on function public.complete_artifact_scan(uuid, text, boolean, text, bigint, text, text) from public, anon, authenticated;
grant execute on function public.claim_artifact_scans(text, integer, integer) to service_role;
grant execute on function public.retry_artifact_scan(uuid, text, text) to service_role;
grant execute on function public.complete_artifact_scan(uuid, text, boolean, text, bigint, text, text) to service_role;
