begin;

alter table public.content_assets
  add column approval_request_id uuid,
  add constraint content_assets_approval_request_fk
    foreign key (organization_id, approval_request_id)
    references public.approval_requests(organization_id, id) on delete restrict,
  add constraint content_assets_approval_request_unique
    unique (organization_id, approval_request_id);

create or replace function private.protect_content_asset_approval_binding()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if old.approval_request_id is distinct from new.approval_request_id then
    raise exception 'immutable_approval_binding' using errcode = '23514';
  end if;
  return new;
end;
$$;

revoke all on function private.protect_content_asset_approval_binding()
from public, anon, authenticated;

create trigger content_assets_approval_binding_immutable
before update of approval_request_id on public.content_assets
for each row execute function private.protect_content_asset_approval_binding();

revoke insert, update on table public.content_assets from authenticated;
grant insert (
  id, organization_id, campaign_id, task_id, title, content_type, status, body,
  channel, scheduled_at, published_at, external_id, created_at, updated_at
) on public.content_assets to authenticated;
grant update (
  campaign_id, task_id, title, content_type, status, body, channel, scheduled_at,
  published_at, external_id, updated_at
) on public.content_assets to authenticated;

commit;
