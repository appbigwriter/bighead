begin;

-- Idempotency is tenant-scoped and survives API retries/restarts.
create unique index if not exists tasks_idempotency_key_idx
on public.tasks (organization_id, (metadata ->> 'idempotency_key'))
where metadata ? 'idempotency_key';

create unique index if not exists messages_client_id_idx
on public.messages (organization_id, room_id, author_user_id, (metadata ->> 'client_id'))
where metadata ? 'client_id';

-- Task state and its event are committed together. The outbox is consumed after
-- commit; Realtime handles low-latency table changes independently.
create or replace function public.transition_task(
  p_task_id uuid,
  p_to public.task_status,
  p_reason text default null,
  p_expected_version integer default null
)
returns public.tasks language plpgsql security definer set search_path = '' as $$
declare v_task public.tasks;
begin
  select * into v_task from public.tasks where id = p_task_id for update;
  if not found then raise exception 'task_not_found' using errcode = 'P0002'; end if;
  if not private.current_user_is_member(v_task.organization_id) then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  if p_expected_version is not null and v_task.version <> p_expected_version then
    raise exception 'version_conflict' using errcode = '40001';
  end if;
  if not private.valid_task_transition(v_task.status, p_to) then
    raise exception 'invalid_task_transition';
  end if;

  insert into public.task_transitions(
    organization_id, task_id, from_status, to_status, actor_user_id, reason
  ) values (
    v_task.organization_id, v_task.id, v_task.status, p_to, (select auth.uid()), p_reason
  );

  update public.tasks set status = p_to, version = version + 1,
    completed_at = case when p_to = 'done' then now() else completed_at end,
    canceled_at = case when p_to = 'canceled' then now() else canceled_at end
  where id = p_task_id returning * into v_task;

  insert into public.event_outbox(
    organization_id, event_type, aggregate_type, aggregate_id, payload
  ) values (
    v_task.organization_id, 'tasks.transitioned', 'task', v_task.id,
    jsonb_build_object(
      'taskId', v_task.id,
      'status', v_task.status,
      'version', v_task.version,
      'actorUserId', (select auth.uid()),
      'reason', p_reason
    )
  );
  return v_task;
end;
$$;

revoke execute on function public.transition_task(uuid, public.task_status, text, integer)
from public, anon;
grant execute on function public.transition_task(uuid, public.task_status, text, integer)
to authenticated;

alter table public.messages replica identity full;
alter table public.tasks replica identity full;
alter table public.notifications replica identity full;

do $$
declare relation_name text;
begin
  foreach relation_name in array array['messages', 'tasks', 'notifications'] loop
    if not exists (
      select 1 from pg_publication_tables
      where pubname = 'supabase_realtime'
        and schemaname = 'public'
        and tablename = relation_name
    ) then
      execute format('alter publication supabase_realtime add table public.%I', relation_name);
    end if;
  end loop;
end;
$$;

commit;
