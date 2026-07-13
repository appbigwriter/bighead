create or replace function private.audit_task_transition()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.audit_log(
    organization_id,
    actor_user_id,
    actor_type,
    action,
    resource_type,
    resource_id,
    changes_redacted
  ) values (
    new.organization_id,
    new.actor_user_id,
    case
      when new.actor_user_id is not null then 'user'
      when new.actor_agent_id is not null then 'agent'
      else 'system'
    end,
    'task.transitioned',
    'task',
    new.task_id::text,
    jsonb_build_object(
      'fromStatus', new.from_status,
      'toStatus', new.to_status,
      'reason', new.reason
    )
  );
  return new;
end;
$$;

revoke all on function private.audit_task_transition() from public;

drop trigger if exists task_transitions_audit on public.task_transitions;
create trigger task_transitions_audit
after insert on public.task_transitions
for each row execute function private.audit_task_transition();
