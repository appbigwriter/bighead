begin;

alter table public.content_assets
  add column approval_payload_hash text;

update public.content_assets set approval_payload_hash=repeat('0',64)
where approval_request_id is not null;

alter table public.content_assets
  add constraint content_assets_approval_payload_hash_check check (
    (approval_request_id is null and approval_payload_hash is null)
    or (approval_request_id is not null and approval_payload_hash ~ '^[0-9a-f]{64}$')
  );

create or replace function private.validate_content_asset_approval_subject()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if new.approval_request_id is not null and not exists (
    select 1 from public.approval_requests ar
    where ar.organization_id=new.organization_id
      and ar.id=new.approval_request_id
      and ar.task_id=new.task_id
      and ar.status='pending' and ar.decided_at is null
  ) then
    raise exception 'approval_subject_mismatch' using errcode='23514';
  end if;
  return new;
end;
$$;
revoke all on function private.validate_content_asset_approval_subject()
from public,anon,authenticated;
create trigger content_assets_validate_approval_subject
before insert on public.content_assets
for each row execute function private.validate_content_asset_approval_subject();

create or replace function private.protect_content_asset_approval_binding()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if (old.approval_request_id,old.approval_payload_hash,
      case when old.approval_request_id is null then null else old.task_id end)
       is distinct from
     (new.approval_request_id,new.approval_payload_hash,
      case when new.approval_request_id is null then null else new.task_id end) then
    raise exception 'immutable_approval_binding' using errcode = '23514';
  end if;
  return new;
end;
$$;
revoke all on function private.protect_content_asset_approval_binding()
from public,anon,authenticated;
drop trigger if exists content_assets_approval_binding_immutable on public.content_assets;
create trigger content_assets_approval_binding_immutable
before update of approval_request_id,approval_payload_hash,task_id on public.content_assets
for each row execute function private.protect_content_asset_approval_binding();

revoke update on public.content_assets from authenticated;
grant update (campaign_id,title,updated_at)
on public.content_assets to authenticated;

create table private.publication_attempts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  content_asset_id uuid not null,
  idempotency_key text not null,
  request_fingerprint text not null check (request_fingerprint ~ '^[0-9a-f]{64}$'),
  channel text not null,
  reason text not null,
  status text not null check (status in ('queued','delivering','delivered','failed')),
  preserved_payload jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (organization_id,content_asset_id)
    references public.content_assets(organization_id,id) on delete cascade,
  unique (organization_id,idempotency_key)
);
create index publication_attempts_asset_created_idx
on private.publication_attempts(organization_id,content_asset_id,created_at desc);
revoke all on private.publication_attempts from public,anon,authenticated;

commit;
