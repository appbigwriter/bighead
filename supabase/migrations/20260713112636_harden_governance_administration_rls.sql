begin;

-- External approval decisions are idempotent without exposing rate-limit state.
alter table public.approval_decisions add column idempotency_key text;
create unique index approval_decisions_idempotency_key_idx
on public.approval_decisions(idempotency_key)
where idempotency_key is not null;

create table private.portal_access_events (
  id bigint generated always as identity primary key,
  token_hash text not null,
  action text not null check (action in ('decision')),
  occurred_at timestamptz not null default now()
);
create index portal_access_events_rate_limit_idx
on private.portal_access_events(token_hash, occurred_at desc);
revoke all on private.portal_access_events from public, anon, authenticated;

-- Serialize last-owner changes per tenant before checking the invariant.
create or replace function private.protect_last_owner()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if old.role = 'owner' and old.status = 'active'
     and (tg_op = 'DELETE' or new.role <> 'owner' or new.status <> 'active') then
    perform pg_advisory_xact_lock(hashtextextended('last-owner:' || old.organization_id::text, 0));
    if not exists (
      select 1 from public.organization_members m
      where m.organization_id = old.organization_id
        and m.user_id <> old.user_id and m.role = 'owner' and m.status = 'active'
    ) then
      raise exception 'last_owner_required' using errcode = '23514';
    end if;
  end if;
  if tg_op = 'DELETE' then return old; end if;
  return new;
end;
$$;

-- Every experiment configuration field and all variants freeze after start.
create or replace function private.protect_running_experiment()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if old.status <> 'draft'
     and (new.campaign_id,new.name,new.hypothesis,new.primary_metric,new.allocation,
          new.stop_rule,new.starts_at,new.ends_at)
       is distinct from
         (old.campaign_id,old.name,old.hypothesis,old.primary_metric,old.allocation,
          old.stop_rule,old.starts_at,old.ends_at) then
    raise exception 'running_experiment_configuration_immutable' using errcode = '23514';
  end if;
  return new;
end;
$$;

create or replace function private.protect_running_experiment_variant()
returns trigger language plpgsql security definer set search_path = '' as $$
declare v_experiment_id uuid := case when tg_op='DELETE' then old.experiment_id else new.experiment_id end;
begin
  if exists(select 1 from public.experiments e where e.id=v_experiment_id and e.status <> 'draft') then
    raise exception 'running_experiment_variants_immutable' using errcode = '23514';
  end if;
  if tg_op='DELETE' then return old; end if;
  return new;
end;
$$;
drop trigger if exists experiment_variants_protect_running on public.experiment_variants;
create trigger experiment_variants_protect_running
before insert or update or delete on public.experiment_variants
for each row execute function private.protect_running_experiment_variant();

-- Remove broad read/write policies and align the Data API with the endpoint matrix.
drop policy if exists approval_requests_select on public.approval_requests;
create policy approval_requests_select on public.approval_requests for select to authenticated using (
  private.current_user_has_role(organization_id,array['owner','admin']::public.member_role[])
  or (assigned_to=(select auth.uid()) and private.current_user_has_role(organization_id,array['reviewer']::public.member_role[]))
);
drop policy if exists approval_requests_insert on public.approval_requests;
create policy approval_requests_insert on public.approval_requests for insert to authenticated with check (
  private.current_user_is_member(organization_id) and requested_by=(select auth.uid()) and status='pending'
);

drop policy if exists approval_decisions_select on public.approval_decisions;
create policy approval_decisions_select on public.approval_decisions for select to authenticated using (
  exists(select 1 from public.approval_requests ar where ar.id=approval_request_id
    and ar.organization_id=approval_decisions.organization_id and (
      private.current_user_has_role(ar.organization_id,array['owner','admin']::public.member_role[])
      or (ar.assigned_to=(select auth.uid()) and private.current_user_has_role(ar.organization_id,array['reviewer']::public.member_role[]))
    ))
);
drop policy if exists approval_decisions_insert_reviewer on public.approval_decisions;
create policy approval_decisions_insert_reviewer on public.approval_decisions for insert to authenticated with check (
  decided_by=(select auth.uid()) and external_reviewer_name is null
  and exists(select 1 from public.approval_requests ar join public.organizations o on o.id=ar.organization_id
    where ar.id=approval_request_id and ar.organization_id=approval_decisions.organization_id
      and ar.status='pending'
      and (not coalesce((o.settings->'approval_policy'->>'segregation')::boolean,true)
           or ar.requested_by is distinct from (select auth.uid()))
      and (private.current_user_has_role(ar.organization_id,array['owner','admin']::public.member_role[])
        or (ar.assigned_to=(select auth.uid()) and private.current_user_has_role(ar.organization_id,array['reviewer']::public.member_role[]))))
);

do $$
declare t text;
begin
  foreach t in array array['model_providers','models','agents','agent_versions','skills',
    'agent_version_skills','workflow_versions','playbooks','qa_scorecards','webhook_endpoints'] loop
    execute format('drop policy if exists %I on public.%I',t||'_select',t);
    execute format('create policy %I on public.%I for select to authenticated using (private.current_user_has_role(organization_id,array[''owner'',''admin'']::public.member_role[]))',t||'_select',t);
    execute format('drop policy if exists %I on public.%I',t||'_manage_insert',t);
    execute format('drop policy if exists %I on public.%I',t||'_manage_update',t);
    execute format('create policy %I on public.%I for insert to authenticated with check (private.current_user_has_role(organization_id,array[''owner'',''admin'']::public.member_role[]))',t||'_manage_insert',t);
    execute format('create policy %I on public.%I for update to authenticated using (private.current_user_has_role(organization_id,array[''owner'',''admin'']::public.member_role[])) with check (private.current_user_has_role(organization_id,array[''owner'',''admin'']::public.member_role[]))',t||'_manage_update',t);
  end loop;
end $$;

drop policy if exists workflows_select on public.workflows;
create policy workflows_select on public.workflows for select to authenticated using (
  private.current_user_has_role(organization_id,array['owner','admin','manager']::public.member_role[])
);
drop policy if exists workflows_manage_insert on public.workflows;
drop policy if exists workflows_manage_update on public.workflows;
create policy workflows_manage_insert on public.workflows for insert to authenticated with check (
  private.current_user_has_role(organization_id,array['owner','admin']::public.member_role[]));
create policy workflows_manage_update on public.workflows for update to authenticated using (
  private.current_user_has_role(organization_id,array['owner','admin']::public.member_role[])) with check (
  private.current_user_has_role(organization_id,array['owner','admin']::public.member_role[]));

drop policy if exists qa_evaluations_select on public.qa_evaluations;
create policy qa_evaluations_select on public.qa_evaluations for select to authenticated using (
  private.current_user_has_role(organization_id,array['owner','admin','reviewer']::public.member_role[]));
drop policy if exists analytics_events_select on public.analytics_events;
create policy analytics_events_select on public.analytics_events for select to authenticated using (
  private.current_user_has_role(organization_id,array['owner','admin','manager','analyst']::public.member_role[]));
drop policy if exists cost_events_select on public.cost_events;
create policy cost_events_select on public.cost_events for select to authenticated using (
  private.current_user_has_role(organization_id,array['owner','admin']::public.member_role[]));
drop policy if exists audit_log_select on public.audit_log;
create policy audit_log_select on public.audit_log for select to authenticated using (
  private.current_user_has_role(organization_id,array['owner','admin']::public.member_role[]));

drop policy if exists experiments_select on public.experiments;
drop policy if exists experiments_insert on public.experiments;
drop policy if exists experiments_update on public.experiments;
create policy experiments_select on public.experiments for select to authenticated using (
  private.current_user_has_role(organization_id,array['owner','analyst']::public.member_role[]));
create policy experiments_insert on public.experiments for insert to authenticated with check (
  private.current_user_has_role(organization_id,array['owner','analyst']::public.member_role[]));
create policy experiments_update on public.experiments for update to authenticated using (
  private.current_user_has_role(organization_id,array['owner','analyst']::public.member_role[])) with check (
  private.current_user_has_role(organization_id,array['owner','analyst']::public.member_role[]));
drop policy if exists experiment_variants_select on public.experiment_variants;
drop policy if exists experiment_variants_insert on public.experiment_variants;
drop policy if exists experiment_variants_update on public.experiment_variants;
create policy experiment_variants_select on public.experiment_variants for select to authenticated using (
  private.current_user_has_role(organization_id,array['owner','analyst']::public.member_role[]));
create policy experiment_variants_insert on public.experiment_variants for insert to authenticated with check (
  private.current_user_has_role(organization_id,array['owner','analyst']::public.member_role[]));
create policy experiment_variants_update on public.experiment_variants for update to authenticated using (
  private.current_user_has_role(organization_id,array['owner','analyst']::public.member_role[])) with check (
  private.current_user_has_role(organization_id,array['owner','analyst']::public.member_role[]));

drop policy if exists organization_members_select on public.organization_members;
create policy organization_members_select on public.organization_members for select to authenticated using (
  user_id=(select auth.uid()) or private.current_user_has_role(organization_id,array['owner','admin']::public.member_role[]));

commit;
