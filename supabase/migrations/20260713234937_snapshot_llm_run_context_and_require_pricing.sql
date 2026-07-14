create table private.run_llm_context (
  run_id uuid primary key,
  organization_id uuid not null,
  task_title text,
  task_objective text,
  task_metadata jsonb not null default '{}'::jsonb
    check (jsonb_typeof(task_metadata) = 'object'),
  agent_id uuid,
  agent_name text,
  agent_enabled boolean,
  agent_version_id uuid,
  system_prompt text,
  output_schema jsonb,
  model_prices jsonb not null default '{}'::jsonb
    check (jsonb_typeof(model_prices) = 'object'),
  snapshotted_at timestamptz not null default now(),
  foreign key (organization_id, run_id)
    references public.runs(organization_id, id) on delete cascade
);

revoke all on private.run_llm_context from public, anon, authenticated;
grant select, insert on private.run_llm_context to service_role;

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
    run_id,
    organization_id,
    task_title,
    task_objective,
    task_metadata,
    agent_id,
    agent_name,
    agent_enabled,
    agent_version_id,
    system_prompt,
    output_schema,
    model_prices
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
    on agent.id = task.agent_id
   and agent.organization_id = run.organization_id
  left join lateral (
    select av.id, av.system_prompt, av.configuration
    from public.agent_versions as av
    where av.agent_id = agent.id
      and av.organization_id = run.organization_id
      and av.published_at is not null
    order by av.version desc, av.id desc
    limit 1
  ) as version on true
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
          select 1
          from public.agent_version_skills as avs
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

revoke execute on function private.snapshot_run_llm_context(uuid)
  from public, anon, authenticated;
grant execute on function private.snapshot_run_llm_context(uuid) to service_role;

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
    claimed.policy_snapshot,
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

revoke execute on function public.claim_llm_runs(text, integer, integer)
  from public, anon, authenticated;
grant execute on function public.claim_llm_runs(text, integer, integer) to service_role;
