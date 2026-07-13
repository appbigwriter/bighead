begin;

-- Storage paths are canonical and tenant-scoped:
-- <organization_uuid>/<uploader_uuid>/<object_uuid>/<safe_filename>.
create or replace function private.try_uuid(p_value text)
returns uuid
language plpgsql
immutable
security invoker
set search_path = ''
as $$
begin
  return p_value::uuid;
exception when invalid_text_representation then
  return null;
end;
$$;

create or replace function private.artifact_storage_path_is_valid(p_name text)
returns boolean
language sql
immutable
security invoker
set search_path = ''
as $$
  with path as (
    select storage.foldername(p_name) as folders,
           storage.filename(p_name) as filename,
           lower(storage.extension(p_name)) as extension
  )
  select cardinality(folders) = 3
    and private.try_uuid(folders[1]) is not null
    and folders[1] = private.try_uuid(folders[1])::text
    and private.try_uuid(folders[2]) is not null
    and folders[2] = private.try_uuid(folders[2])::text
    and private.try_uuid(folders[3]) is not null
    and folders[3] = private.try_uuid(folders[3])::text
    and filename ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$'
    and filename not in ('.', '..')
    and extension = any (array[
      'pdf','png','jpg','jpeg','webp','txt','md','csv','json',
      'docx','xlsx','pptx','zip'
    ])
  from path;
$$;

create or replace function private.artifact_storage_metadata_is_valid(
  p_name text,
  p_metadata jsonb,
  p_user_metadata jsonb
)
returns boolean
language sql
immutable
security invoker
set search_path = ''
as $$
  select jsonb_typeof(p_metadata) = 'object'
    and jsonb_typeof(p_metadata -> 'size') = 'number'
    and (p_metadata ->> 'size')::numeric between 1 and 52428800
    and case lower(storage.extension(p_name))
      when 'pdf' then lower(p_metadata ->> 'mimetype') = 'application/pdf'
      when 'png' then lower(p_metadata ->> 'mimetype') = 'image/png'
      when 'jpg' then lower(p_metadata ->> 'mimetype') = 'image/jpeg'
      when 'jpeg' then lower(p_metadata ->> 'mimetype') = 'image/jpeg'
      when 'webp' then lower(p_metadata ->> 'mimetype') = 'image/webp'
      when 'txt' then lower(p_metadata ->> 'mimetype') = 'text/plain'
      when 'md' then lower(p_metadata ->> 'mimetype') in ('text/markdown', 'text/plain')
      when 'csv' then lower(p_metadata ->> 'mimetype') in ('text/csv', 'application/csv')
      when 'json' then lower(p_metadata ->> 'mimetype') = 'application/json'
      when 'docx' then lower(p_metadata ->> 'mimetype') = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      when 'xlsx' then lower(p_metadata ->> 'mimetype') = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      when 'pptx' then lower(p_metadata ->> 'mimetype') = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
      when 'zip' then lower(p_metadata ->> 'mimetype') in ('application/zip', 'application/x-zip-compressed')
      else false
    end
    and jsonb_typeof(p_user_metadata) = 'object'
    and lower(p_user_metadata ->> 'checksum_sha256') ~ '^[0-9a-f]{64}$'
    and p_user_metadata ->> 'quarantine_status' = 'pending';
$$;

revoke all on function private.try_uuid(text) from public, anon, authenticated;
revoke all on function private.artifact_storage_path_is_valid(text) from public, anon, authenticated;
revoke all on function private.artifact_storage_metadata_is_valid(text, jsonb, jsonb) from public, anon, authenticated;
grant execute on function private.try_uuid(text) to authenticated;
grant execute on function private.artifact_storage_path_is_valid(text) to authenticated;
grant execute on function private.artifact_storage_metadata_is_valid(text, jsonb, jsonb) to authenticated;

insert into storage.buckets (
  id, name, public, file_size_limit, allowed_mime_types
)
values (
  'artifacts',
  'artifacts',
  false,
  52428800,
  array[
    'application/pdf','image/png','image/jpeg','image/webp','text/plain',
    'text/markdown','text/csv','application/csv','application/json',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/zip','application/x-zip-compressed'
  ]::text[]
)
on conflict (id) do update
set name = excluded.name,
    public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists artifacts_select on storage.objects;
drop policy if exists artifacts_insert on storage.objects;
drop policy if exists artifacts_update on storage.objects;
drop policy if exists artifacts_delete on storage.objects;

-- Clean objects are available to active tenant members. Pending uploads are
-- visible only to Storage's upload/update operations so INSERT ... RETURNING
-- and upsert work without making quarantined content downloadable/listable.
create policy artifacts_select
on storage.objects for select to authenticated
using (
  bucket_id = 'artifacts'
  and private.artifact_storage_path_is_valid(name)
  and private.current_user_is_member(private.try_uuid((storage.foldername(name))[1]))
  and (
    user_metadata ->> 'quarantine_status' = 'clean'
    or (
      (storage.foldername(name))[2] = (select auth.uid())::text
      and storage.allow_any_operation(array[
        'storage.object.upload',
        'storage.object.upload_update',
        'storage.object.upload_signed',
        'storage.tus.upload.create',
        'storage.tus.upload.part'
      ])
    )
  )
);

create policy artifacts_insert
on storage.objects for insert to authenticated
with check (
  bucket_id = 'artifacts'
  and private.artifact_storage_path_is_valid(name)
  and (storage.foldername(name))[2] = (select auth.uid())::text
  and private.current_user_is_member(private.try_uuid((storage.foldername(name))[1]))
  and private.artifact_storage_metadata_is_valid(name, metadata, user_metadata)
);

create policy artifacts_update
on storage.objects for update to authenticated
using (
  bucket_id = 'artifacts'
  and private.artifact_storage_path_is_valid(name)
  and (storage.foldername(name))[2] = (select auth.uid())::text
  and private.current_user_is_member(private.try_uuid((storage.foldername(name))[1]))
)
with check (
  bucket_id = 'artifacts'
  and private.artifact_storage_path_is_valid(name)
  and (storage.foldername(name))[2] = (select auth.uid())::text
  and private.current_user_is_member(private.try_uuid((storage.foldername(name))[1]))
  and private.artifact_storage_metadata_is_valid(name, metadata, user_metadata)
);

create policy artifacts_delete
on storage.objects for delete to authenticated
using (
  bucket_id = 'artifacts'
  and private.artifact_storage_path_is_valid(name)
  and private.current_user_is_member(private.try_uuid((storage.foldername(name))[1]))
  and (
    (storage.foldername(name))[2] = (select auth.uid())::text
    or private.current_user_has_role(
      private.try_uuid((storage.foldername(name))[1]),
      array['owner','admin','manager']::public.member_role[]
    )
  )
);

commit;
