create or replace function private.redact_run_metadata(p_value jsonb)
returns jsonb
language sql
immutable
security invoker
set search_path = ''
as $$
  select case jsonb_typeof(p_value)
    when 'object' then coalesce((
      select jsonb_object_agg(
        entry.key,
        case
          when entry.key ~* '(api.?key|authorization|password|secret|token|credential)'
            then '"[REDACTED]"'::jsonb
          else private.redact_run_metadata(entry.value)
        end
      )
      from jsonb_each(p_value) as entry
    ), '{}'::jsonb)
    when 'array' then coalesce((
      select jsonb_agg(private.redact_run_metadata(item.value) order by item.ordinality)
      from jsonb_array_elements(p_value) with ordinality as item(value, ordinality)
    ), '[]'::jsonb)
    else p_value
  end
$$;

revoke execute on function private.redact_run_metadata(jsonb)
  from public, anon, authenticated;
grant execute on function private.redact_run_metadata(jsonb) to service_role;

-- The worker role receives only columns needed to assemble an execution
-- request. Provider secret references remain inaccessible and never cross RPC.
grant select (id, organization_id, agent_id, workflow_version_id, title, objective, metadata)
  on public.tasks to service_role;
grant select (id, organization_id, name, is_enabled)
  on public.agents to service_role;
grant select (id, organization_id, agent_id, version, system_prompt, configuration, published_at)
  on public.agent_versions to service_role;
grant select (id, organization_id, definition)
  on public.workflow_versions to service_role;
grant select (id, organization_id, output_schema, is_enabled)
  on public.skills to service_role;
grant select (organization_id, agent_version_id, skill_id)
  on public.agent_version_skills to service_role;
grant select (
  id, organization_id, model_key, input_cost_per_million,
  output_cost_per_million, is_enabled
) on public.models to service_role;
grant update (input_tokens, output_tokens, model_id)
  on public.cost_events to service_role;

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
    task.title,
    task.objective,
    private.redact_run_metadata(task.metadata),
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
  from public.claim_runs(p_worker, p_limit, p_lease_seconds) as claimed
  left join public.tasks as task
    on task.id = claimed.task_id
   and task.organization_id = claimed.organization_id
  left join public.agents as agent
    on agent.id = task.agent_id
   and agent.organization_id = claimed.organization_id
  left join lateral (
    select av.id, av.system_prompt, av.configuration
    from public.agent_versions as av
    where av.agent_id = agent.id
      and av.organization_id = claimed.organization_id
      and av.published_at is not null
    order by av.version desc, av.id desc
    limit 1
  ) as version on true
  left join public.workflow_versions as workflow
    on workflow.id = claimed.workflow_version_id
   and workflow.organization_id = claimed.organization_id
  left join lateral (
    select
      count(distinct skill.output_schema) filter (
        where skill.output_schema <> '{}'::jsonb
      ) as schema_count,
      (array_agg(distinct skill.output_schema) filter (
        where skill.output_schema <> '{}'::jsonb
      ))[1] as output_schema
    from public.skills as skill
    where skill.organization_id = claimed.organization_id
      and skill.is_enabled
      and (
        exists (
          select 1
          from public.agent_version_skills as avs
          where avs.organization_id = claimed.organization_id
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
    where model.organization_id = claimed.organization_id
      and model.is_enabled
  ) as prices on true
$$;

revoke execute on function public.claim_llm_runs(text, integer, integer)
  from public, anon, authenticated;
grant execute on function public.claim_llm_runs(text, integer, integer) to service_role;

create or replace function public.complete_llm_run(
  p_id uuid,
  p_worker text,
  p_effect_key text,
  p_provider_event_id text,
  p_amount numeric default 0,
  p_currency text default 'USD',
  p_input_tokens bigint default 0,
  p_output_tokens bigint default 0,
  p_model_id uuid default null
) returns boolean
language plpgsql
security invoker
set search_path = ''
as $$
declare
  completed boolean;
begin
  if current_user <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_input_tokens < 0 or p_output_tokens < 0 then
    raise exception 'token_counts_must_be_non_negative' using errcode = '22023';
  end if;
  if p_model_id is not null and not exists (
    select 1
    from public.models as model
    join public.runs as run
      on run.id = p_id
     and run.organization_id = model.organization_id
    where model.id = p_model_id
  ) then
    raise exception 'run_model_tenant_mismatch' using errcode = '23503';
  end if;

  completed := public.complete_run(
    p_id,
    p_worker,
    p_effect_key,
    p_provider_event_id,
    p_amount,
    p_currency
  );
  if not completed then
    return false;
  end if;

  update public.cost_events
     set input_tokens = p_input_tokens,
         output_tokens = p_output_tokens,
         model_id = p_model_id
   where run_id = p_id
     and provider_event_id = p_provider_event_id;
  return true;
end
$$;

revoke execute on function public.complete_llm_run(
  uuid, text, text, text, numeric, text, bigint, bigint, uuid
) from public, anon, authenticated;
grant execute on function public.complete_llm_run(
  uuid, text, text, text, numeric, text, bigint, bigint, uuid
) to service_role;
