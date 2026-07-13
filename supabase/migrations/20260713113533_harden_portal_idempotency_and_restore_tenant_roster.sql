begin;

-- Idempotency keys are tenant-scoped and portal replays are additionally bound
-- to the approval addressed by the presented token.
drop index if exists public.approval_decisions_idempotency_key_idx;
create unique index approval_decisions_tenant_idempotency_key_idx
on public.approval_decisions(organization_id, idempotency_key)
where idempotency_key is not null;

alter table private.portal_access_events
  drop constraint if exists portal_access_events_action_check;
alter table private.portal_access_events
  add constraint portal_access_events_action_check
  check (action in ('view', 'decision'));

-- Every active member may read the roster of their current tenant. RLS still
-- rejects memberships belonging to every other tenant.
drop policy if exists organization_members_select on public.organization_members;
create policy organization_members_select
on public.organization_members
for select to authenticated
using (private.current_user_is_member(organization_id));

commit;
