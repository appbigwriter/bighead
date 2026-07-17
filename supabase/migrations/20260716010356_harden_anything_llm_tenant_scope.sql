begin;

alter table public.anything_llm_ingestions
  add constraint anything_llm_ingestions_artifact_tenant_fk
  foreign key (organization_id, artifact_id)
  references public.artifacts(organization_id, id)
  on delete cascade,
  add constraint anything_llm_ingestions_workspace_not_blank
  check (btrim(workspace) <> ''),
  add constraint anything_llm_ingestions_checksum_sha256_format
  check (checksum_sha256 ~ '^[0-9a-f]{64}$'),
  add constraint anything_llm_ingestions_size_nonnegative
  check (size_bytes >= 0);

create trigger preserve_organization_scope
before update of organization_id on public.anything_llm_ingestions
for each row execute function private.preserve_organization_scope();

revoke all on public.anything_llm_ingestions from public, anon;
grant select, insert, update on public.anything_llm_ingestions to authenticated;
grant select, insert, update on public.anything_llm_ingestions to service_role;

create index anything_llm_ingestions_pending_idx
on public.anything_llm_ingestions(created_at, artifact_id)
where status in ('pending', 'processing');

create or replace function private.pin_run_agent_version()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  task_agent_id uuid;
begin
  if tg_op = 'UPDATE' and (
    new.agent_id is distinct from old.agent_id
    or new.agent_version_id is distinct from old.agent_version_id
  ) then
    raise exception 'run_agent_context_immutable' using errcode = '23514';
  end if;

  select task.agent_id into task_agent_id
  from public.tasks as task
  where task.id = new.task_id
    and task.organization_id = new.organization_id;

  if new.agent_id is not null and new.agent_id is distinct from task_agent_id then
    raise exception 'run_agent_mismatch' using errcode = '23514';
  end if;
  new.agent_id := task_agent_id;

  if new.agent_version_id is not null then
    if not exists (
      select 1 from public.agent_versions as version
      where version.id = new.agent_version_id
        and version.organization_id = new.organization_id
        and version.agent_id = new.agent_id
        and version.published_at is not null
    ) then
      raise exception 'run_agent_version_mismatch' using errcode = '23514';
    end if;
  else
    select version.id into new.agent_version_id
    from public.agent_versions as version
    where version.organization_id = new.organization_id
      and version.agent_id = new.agent_id
      and version.published_at is not null
    order by version.version desc, version.id desc
    limit 1;
  end if;
  return new;
end;
$$;

revoke execute on function private.pin_run_agent_version()
from public, anon, authenticated;

create or replace function private.protect_published_agent_version_skills()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  old_version_id uuid;
  new_version_id uuid;
begin
  old_version_id := case when tg_op in ('UPDATE', 'DELETE') then old.agent_version_id end;
  new_version_id := case when tg_op in ('INSERT', 'UPDATE') then new.agent_version_id end;
  if exists (
    select 1
    from public.agent_versions as version
    where version.id in (old_version_id, new_version_id)
      and version.published_at is not null
  ) then
    raise exception using
      errcode = '23514',
      message = 'published_agent_version_skills_immutable';
  end if;
  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

revoke execute on function private.protect_published_agent_version_skills()
from public, anon, authenticated, service_role;

create trigger protect_published_agent_version_skills
before insert or update or delete on public.agent_version_skills
for each row execute function private.protect_published_agent_version_skills();

update public.runs as run
set agent_id = task.agent_id
from public.tasks as task
where task.id = run.task_id
  and task.organization_id = run.organization_id
  and run.agent_id is null
  and run.status in ('queued', 'waiting', 'running');

update public.runs as run
set agent_version_id = (
  select candidate.id
  from public.agent_versions as candidate
  where candidate.organization_id = run.organization_id
    and candidate.agent_id = run.agent_id
    and candidate.published_at is not null
  order by candidate.version desc, candidate.id desc
  limit 1
)
where run.agent_version_id is null
  and run.agent_id is not null
  and run.status in ('queued', 'waiting', 'running');

create trigger pin_run_agent_version
before insert or update of task_id, organization_id, agent_id, agent_version_id
on public.runs
for each row execute function private.pin_run_agent_version();

create or replace function private.snapshot_run_llm_context(p_run_id uuid)
returns setof private.run_llm_context
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if current_user <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;

  insert into private.run_llm_context (
    run_id, organization_id, task_title, task_objective, task_metadata,
    agent_id, agent_name, agent_enabled, agent_version_id, system_prompt,
    output_schema, model_prices
  )
  select
    run.id,
    run.organization_id,
    task.title,
    task.objective,
    coalesce(private.redact_run_metadata(task.metadata), '{}'::jsonb),
    agent.id,
    agent.name,
    agent.is_enabled,
    version.id,
    version.system_prompt,
    case
      when jsonb_typeof(task.metadata -> 'outputSchema') = 'object'
        and task.metadata -> 'outputSchema' <> '{}'::jsonb
        then task.metadata -> 'outputSchema'
      when jsonb_typeof(version.configuration -> 'outputSchema') = 'object'
        and version.configuration -> 'outputSchema' <> '{}'::jsonb
        then version.configuration -> 'outputSchema'
      when jsonb_typeof(workflow.definition -> 'outputSchema') = 'object'
        and workflow.definition -> 'outputSchema' <> '{}'::jsonb
        then workflow.definition -> 'outputSchema'
      when skill_schema.schema_count = 1 then skill_schema.output_schema
      else null
    end,
    coalesce(prices.value, '{}'::jsonb)
  from public.runs as run
  left join public.tasks as task
    on task.id = run.task_id
   and task.organization_id = run.organization_id
  left join public.agents as agent
    on agent.id = run.agent_id
   and agent.organization_id = run.organization_id
  left join public.agent_versions as version
    on version.id = run.agent_version_id
   and version.agent_id = run.agent_id
   and version.organization_id = run.organization_id
   and version.published_at is not null
  left join public.workflow_versions as workflow
    on workflow.id = run.workflow_version_id
   and workflow.organization_id = run.organization_id
  left join lateral (
    select
      count(distinct skill.output_schema) filter (
        where skill.output_schema <> '{}'::jsonb
      ) as schema_count,
      (array_agg(distinct skill.output_schema) filter (
        where skill.output_schema <> '{}'::jsonb
      ))[1] as output_schema
    from public.skills as skill
    where skill.organization_id = run.organization_id
      and skill.is_enabled
      and (
        exists (
          select 1 from public.agent_version_skills as avs
          where avs.organization_id = run.organization_id
            and avs.agent_version_id = version.id
            and avs.skill_id = skill.id
        )
        or exists (
          select 1
          from jsonb_array_elements(
            case
              when jsonb_typeof(workflow.definition -> 'nodes') = 'array'
                then workflow.definition -> 'nodes'
              else '[]'::jsonb
            end
          ) as node
          where coalesce(node ->> 'skillId', node ->> 'skill_id') = skill.id::text
        )
      )
  ) as skill_schema on true
  left join lateral (
    select jsonb_object_agg(
      model.model_key,
      jsonb_build_object(
        'modelId', model.id,
        'inputCostPerMillion', model.input_cost_per_million,
        'outputCostPerMillion', model.output_cost_per_million
      )
    ) as value
    from public.models as model
    where model.organization_id = run.organization_id
      and model.is_enabled
  ) as prices on true
  where run.id = p_run_id
  on conflict (run_id) do nothing;

  return query
  select snapshot.*
  from private.run_llm_context as snapshot
  where snapshot.run_id = p_run_id;
end
$$;

grant select (id, organization_id, slug, is_enabled)
  on public.skills to service_role;

grant select (organization_id, agent_version_id, skill_id)
  on public.agent_version_skills to service_role;

create or replace function public.claim_llm_runs(
  p_worker text,
  p_limit integer default 10,
  p_lease_seconds integer default 60
) returns table (
  id uuid,
  organization_id uuid,
  task_id uuid,
  workflow_version_id uuid,
  attempt integer,
  max_attempts integer,
  retry_backoff_seconds integer,
  policy_snapshot jsonb,
  task_title text,
  task_objective text,
  task_metadata jsonb,
  agent_id uuid,
  agent_name text,
  agent_enabled boolean,
  agent_version_id uuid,
  system_prompt text,
  output_schema jsonb,
  model_prices jsonb
)
language sql
security invoker
set search_path = ''
as $$
  select
    claimed.id,
    claimed.organization_id,
    claimed.task_id,
    claimed.workflow_version_id,
    claimed.attempt,
    claimed.max_attempts,
    claimed.retry_backoff_seconds,
    jsonb_set(
      coalesce(claimed.policy_snapshot, '{}'::jsonb),
      '{skills}',
      coalesce(claimed.policy_snapshot -> 'skills', '[]'::jsonb) || coalesce((
        select jsonb_agg(jsonb_build_object('id', skill.id, 'slug', skill.slug))
        from public.agent_version_skills as link
        join public.skills as skill
          on skill.id = link.skill_id
         and skill.organization_id = link.organization_id
        where link.organization_id = claimed.organization_id
          and link.agent_version_id = snapshot.agent_version_id
          and skill.is_enabled
          and not exists (
            select 1
            from jsonb_array_elements(
              coalesce(claimed.policy_snapshot -> 'skills', '[]'::jsonb)
            ) as existing
            where existing ->> 'slug' = skill.slug
          )
      ), '[]'::jsonb),
      true
    ),
    snapshot.task_title,
    snapshot.task_objective,
    snapshot.task_metadata,
    snapshot.agent_id,
    snapshot.agent_name,
    snapshot.agent_enabled,
    snapshot.agent_version_id,
    snapshot.system_prompt,
    snapshot.output_schema,
    snapshot.model_prices
  from public.claim_runs(p_worker, p_limit, p_lease_seconds) as claimed
  cross join lateral private.snapshot_run_llm_context(claimed.id) as snapshot
$$;

commit;
