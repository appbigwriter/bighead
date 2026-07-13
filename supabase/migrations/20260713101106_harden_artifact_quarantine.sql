begin;

do $$ begin
  create type public.artifact_quarantine_status as enum
    ('initiated', 'pending', 'clean', 'rejected');
exception when duplicate_object then null;
end $$;

alter table public.artifacts
  add column if not exists quarantine_status public.artifact_quarantine_status
  not null default 'initiated';

update public.artifacts
set quarantine_status = case metadata ->> 'quarantine_status'
  when 'pending' then 'pending'::public.artifact_quarantine_status
  when 'clean' then 'clean'::public.artifact_quarantine_status
  when 'rejected' then 'rejected'::public.artifact_quarantine_status
  else 'initiated'::public.artifact_quarantine_status
end;

-- A tenant member may create only their own initiated row. The worker service
-- role is the sole actor that can promote quarantine_status.
drop policy if exists artifacts_insert on public.artifacts;
create policy artifacts_insert on public.artifacts for insert to authenticated
with check (
  private.current_user_is_member(organization_id)
  and created_by = (select auth.uid())
  and quarantine_status = 'initiated'
  and storage_bucket = 'artifacts'
  and private.artifact_storage_path_is_valid(storage_path)
  and private.try_uuid((storage.foldername(storage_path))[1]) = organization_id
  and private.try_uuid((storage.foldername(storage_path))[2]) = (select auth.uid())
  and private.try_uuid((storage.foldername(storage_path))[3]) = id
);

revoke update on public.artifacts from authenticated;
grant update (task_id, room_id, name, kind, metadata) on public.artifacts to authenticated;

create or replace function private.current_user_can_read_clean_artifact(
  p_organization_id uuid,
  p_artifact_id uuid,
  p_bucket text,
  p_path text
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select (select auth.uid()) is not null
    and private.current_user_is_member(p_organization_id)
    and exists (
      select 1 from public.artifacts a
      where a.organization_id = p_organization_id
        and a.id = p_artifact_id
        and a.storage_bucket = p_bucket
        and a.storage_path = p_path
        and a.quarantine_status = 'clean'
    );
$$;
revoke all on function private.current_user_can_read_clean_artifact(uuid, uuid, text, text)
  from public, anon, authenticated;
grant execute on function private.current_user_can_read_clean_artifact(uuid, uuid, text, text)
  to authenticated;

-- Storage user_metadata is upload input and must never be an authorization
-- source. Visibility is joined to the worker-owned artifact state and exact
-- canonical object path.
drop policy if exists artifacts_select on storage.objects;
create policy artifacts_select on storage.objects for select to authenticated
using (
  bucket_id = 'artifacts'
  and private.artifact_storage_path_is_valid(name)
  and private.current_user_is_member(private.try_uuid((storage.foldername(name))[1]))
  and private.current_user_can_read_clean_artifact(
    private.try_uuid((storage.foldername(name))[1]),
    private.try_uuid((storage.foldername(name))[3]),
    storage.objects.bucket_id,
    storage.objects.name
  )
);

commit;
