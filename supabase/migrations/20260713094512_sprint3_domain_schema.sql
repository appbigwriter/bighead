begin;

do $$ begin create type public.risk_level as enum ('low','medium','high','critical'); exception when duplicate_object then null; end $$;
do $$ begin create type public.task_status as enum ('new','triaged','in_progress','waiting_tool','waiting_human','ready_for_review','approved','failed','done','canceled'); exception when duplicate_object then null; end $$;
do $$ begin create type public.run_status as enum ('queued','running','waiting','succeeded','failed','canceled','dead_letter'); exception when duplicate_object then null; end $$;
do $$ begin create type public.approval_status as enum ('pending','approved','rejected','changes_requested','expired','canceled'); exception when duplicate_object then null; end $$;
do $$ begin create type public.memory_kind as enum ('fact','inference','decision','summary'); exception when duplicate_object then null; end $$;
do $$ begin create type public.review_status as enum ('draft','pending','approved','contested','expired','archived'); exception when duplicate_object then null; end $$;
do $$ begin create type public.content_status as enum ('draft','review','approved','scheduled','published','failed','archived'); exception when duplicate_object then null; end $$;
do $$ begin create type public.lead_status as enum ('new','qualified','nurturing','opportunity','won','lost','disqualified'); exception when duplicate_object then null; end $$;
do $$ begin create type public.experiment_status as enum ('draft','running','paused','completed','canceled'); exception when duplicate_object then null; end $$;

-- -----------------------------------------------------------------------------
-- Colaboracao
-- -----------------------------------------------------------------------------

create table public.rooms (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null check (char_length(name) between 1 and 120),
  description text,
  is_private boolean not null default false,
  archived_at timestamptz,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, name)
);

create table public.room_members (
  organization_id uuid not null,
  room_id uuid not null,
  user_id uuid not null references auth.users(id) on delete cascade,
  is_moderator boolean not null default false,
  last_read_at timestamptz,
  created_at timestamptz not null default now(),
  primary key (room_id, user_id),
  foreign key (organization_id, room_id) references public.rooms(organization_id, id) on delete cascade
);

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  room_id uuid not null,
  parent_message_id uuid references public.messages(id) on delete set null,
  author_user_id uuid references auth.users(id) on delete set null,
  author_agent_id uuid,
  body text not null check (char_length(body) <= 100000),
  metadata jsonb not null default '{}'::jsonb,
  edited_at timestamptz,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  foreign key (organization_id, room_id) references public.rooms(organization_id, id) on delete cascade,
  check ((author_user_id is not null)::int + (author_agent_id is not null)::int <= 1)
);

create index messages_room_created_idx on public.messages(room_id, created_at desc);

-- -----------------------------------------------------------------------------
-- Agentes, modelos, skills e workflows
-- -----------------------------------------------------------------------------

create table public.model_providers (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null,
  provider_key text not null,
  secret_reference text,
  is_enabled boolean not null default true,
  settings jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, provider_key), unique (organization_id, id)
);

create table public.models (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  provider_id uuid not null,
  model_key text not null,
  capabilities jsonb not null default '{}'::jsonb,
  input_cost_per_million numeric(14,6) check (input_cost_per_million >= 0),
  output_cost_per_million numeric(14,6) check (output_cost_per_million >= 0),
  price_valid_from timestamptz not null default now(),
  is_enabled boolean not null default true,
  created_at timestamptz not null default now(),
  unique (organization_id, model_key), unique (organization_id, id),
  foreign key (organization_id, provider_id) references public.model_providers(organization_id, id) on delete cascade
);

create table public.agents (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null,
  slug text not null,
  description text,
  owner_user_id uuid references auth.users(id) on delete set null,
  risk_level public.risk_level not null default 'low',
  trust_score numeric(5,2) not null default 0 check (trust_score between 0 and 100),
  is_enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, slug), unique (organization_id, id)
);

alter table public.messages add constraint messages_author_agent_fk foreign key (organization_id, author_agent_id) references public.agents(organization_id, id) on delete set null;

create table public.agent_versions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  agent_id uuid not null,
  version integer not null check (version > 0),
  model_id uuid,
  system_prompt text not null,
  configuration jsonb not null default '{}'::jsonb,
  published_at timestamptz,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (agent_id, version), unique (organization_id, id),
  foreign key (organization_id, agent_id) references public.agents(organization_id, id) on delete cascade,
  foreign key (organization_id, model_id) references public.models(organization_id, id) on delete restrict
);

create table public.skills (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null,
  slug text not null,
  description text,
  input_schema jsonb not null default '{}'::jsonb,
  output_schema jsonb not null default '{}'::jsonb,
  risk_level public.risk_level not null default 'medium',
  requires_approval boolean not null default false,
  timeout_seconds integer not null default 60 check (timeout_seconds between 1 and 3600),
  max_retries smallint not null default 2 check (max_retries between 0 and 10),
  secret_reference text,
  is_enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, slug), unique (organization_id, id)
);

create table public.agent_version_skills (
  organization_id uuid not null,
  agent_version_id uuid not null,
  skill_id uuid not null,
  configuration jsonb not null default '{}'::jsonb,
  primary key (agent_version_id, skill_id),
  foreign key (organization_id, agent_version_id) references public.agent_versions(organization_id, id) on delete cascade,
  foreign key (organization_id, skill_id) references public.skills(organization_id, id) on delete cascade
);

create table public.workflows (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null,
  slug text not null,
  description text,
  owner_user_id uuid references auth.users(id) on delete set null,
  is_archived boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, slug), unique (organization_id, id)
);

create table public.workflow_versions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  workflow_id uuid not null,
  version integer not null check (version > 0),
  definition jsonb not null check (jsonb_typeof(definition) = 'object'),
  published_at timestamptz,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (workflow_id, version), unique (organization_id, id),
  foreign key (organization_id, workflow_id) references public.workflows(organization_id, id) on delete cascade
);

create table public.playbooks (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  workflow_version_id uuid not null,
  name text not null,
  description text,
  default_inputs jsonb not null default '{}'::jsonb,
  is_enabled boolean not null default true,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, workflow_version_id) references public.workflow_versions(organization_id, id) on delete restrict
);

-- -----------------------------------------------------------------------------
-- Tarefas, execucoes, custos e artefatos
-- -----------------------------------------------------------------------------

create table public.tasks (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  room_id uuid,
  source_message_id uuid references public.messages(id) on delete set null,
  title text not null check (char_length(title) between 1 and 240),
  objective text not null,
  status public.task_status not null default 'new',
  priority smallint not null default 3 check (priority between 1 and 5),
  risk_level public.risk_level not null default 'low',
  requester_id uuid references auth.users(id) on delete set null,
  assignee_id uuid references auth.users(id) on delete set null,
  agent_id uuid,
  workflow_version_id uuid,
  due_at timestamptz,
  sla_at timestamptz,
  version integer not null default 1,
  estimated_cost numeric(14,6) check (estimated_cost >= 0),
  metadata jsonb not null default '{}'::jsonb,
  completed_at timestamptz,
  canceled_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, room_id) references public.rooms(organization_id, id) on delete set null,
  foreign key (organization_id, agent_id) references public.agents(organization_id, id) on delete set null,
  foreign key (organization_id, workflow_version_id) references public.workflow_versions(organization_id, id) on delete set null,
  check (sla_at is null or sla_at >= created_at)
);

create index tasks_org_status_idx on public.tasks(organization_id, status, created_at desc);
create index tasks_assignee_open_idx on public.tasks(assignee_id, sla_at) where status not in ('done','canceled');

create table public.task_dependencies (
  organization_id uuid not null,
  task_id uuid not null,
  depends_on_task_id uuid not null,
  created_at timestamptz not null default now(),
  primary key (task_id, depends_on_task_id),
  foreign key (organization_id, task_id) references public.tasks(organization_id, id) on delete cascade,
  foreign key (organization_id, depends_on_task_id) references public.tasks(organization_id, id) on delete cascade,
  check (task_id <> depends_on_task_id)
);

create table public.task_transitions (
  id bigint generated always as identity primary key,
  organization_id uuid not null,
  task_id uuid not null,
  from_status public.task_status not null,
  to_status public.task_status not null,
  actor_user_id uuid references auth.users(id) on delete set null,
  actor_agent_id uuid,
  reason text,
  created_at timestamptz not null default now(),
  foreign key (organization_id, task_id) references public.tasks(organization_id, id) on delete cascade,
  foreign key (organization_id, actor_agent_id) references public.agents(organization_id, id) on delete set null
);

create table public.runs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  task_id uuid not null,
  workflow_version_id uuid,
  status public.run_status not null default 'queued',
  idempotency_key text not null,
  attempt integer not null default 1 check (attempt > 0),
  locked_by text,
  locked_until timestamptz,
  heartbeat_at timestamptz,
  started_at timestamptz,
  finished_at timestamptz,
  error_code text,
  error_detail jsonb,
  created_at timestamptz not null default now(),
  unique (organization_id, idempotency_key), unique (organization_id, id),
  foreign key (organization_id, task_id) references public.tasks(organization_id, id) on delete cascade,
  foreign key (organization_id, workflow_version_id) references public.workflow_versions(organization_id, id) on delete set null
);

create index runs_queue_idx on public.runs(status, created_at) where status in ('queued','waiting');
create index runs_expired_lease_idx on public.runs(locked_until) where status = 'running';

create table public.run_steps (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  run_id uuid not null,
  step_key text not null,
  step_type text not null check (step_type in ('agent','skill','condition','approval','wait','end')),
  status public.run_status not null default 'queued',
  attempt integer not null default 1,
  input jsonb,
  output jsonb,
  error_code text,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  unique (run_id, step_key, attempt), unique (organization_id, id),
  foreign key (organization_id, run_id) references public.runs(organization_id, id) on delete cascade
);

create table public.tool_calls (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  run_step_id uuid not null,
  skill_id uuid,
  request_redacted jsonb,
  response_redacted jsonb,
  status public.run_status not null,
  latency_ms integer check (latency_ms >= 0),
  created_at timestamptz not null default now(),
  finished_at timestamptz,
  foreign key (organization_id, run_step_id) references public.run_steps(organization_id, id) on delete cascade,
  foreign key (organization_id, skill_id) references public.skills(organization_id, id) on delete set null
);

create table public.cost_events (
  id bigint generated always as identity primary key,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  task_id uuid,
  run_id uuid,
  model_id uuid,
  provider_event_id text,
  input_tokens bigint not null default 0 check (input_tokens >= 0),
  output_tokens bigint not null default 0 check (output_tokens >= 0),
  amount numeric(14,6) not null check (amount >= 0),
  currency char(3) not null default 'USD',
  occurred_at timestamptz not null default now(),
  unique nulls not distinct (organization_id, provider_event_id),
  foreign key (organization_id, task_id) references public.tasks(organization_id, id) on delete set null,
  foreign key (organization_id, run_id) references public.runs(organization_id, id) on delete set null,
  foreign key (organization_id, model_id) references public.models(organization_id, id) on delete set null
);

create index cost_events_org_time_idx on public.cost_events(organization_id, occurred_at desc);

create table public.artifacts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  task_id uuid,
  room_id uuid,
  name text not null,
  kind text not null,
  storage_bucket text,
  storage_path text,
  mime_type text,
  size_bytes bigint check (size_bytes >= 0),
  checksum_sha256 text,
  metadata jsonb not null default '{}'::jsonb,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique nulls not distinct (storage_bucket, storage_path),
  foreign key (organization_id, task_id) references public.tasks(organization_id, id) on delete set null,
  foreign key (organization_id, room_id) references public.rooms(organization_id, id) on delete set null
);

-- -----------------------------------------------------------------------------
-- Aprovacoes e portal externo
-- -----------------------------------------------------------------------------

create table public.approval_requests (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  task_id uuid not null,
  artifact_id uuid,
  requested_by uuid references auth.users(id) on delete set null,
  assigned_to uuid references auth.users(id) on delete set null,
  status public.approval_status not null default 'pending',
  risk_level public.risk_level not null,
  round integer not null default 1 check (round > 0),
  due_at timestamptz,
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, task_id) references public.tasks(organization_id, id) on delete cascade,
  foreign key (organization_id, artifact_id) references public.artifacts(organization_id, id) on delete set null
);

create table public.approval_decisions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  approval_request_id uuid not null unique,
  decision public.approval_status not null check (decision in ('approved','rejected','changes_requested')),
  decided_by uuid references auth.users(id) on delete set null,
  external_reviewer_name text,
  comment text,
  created_at timestamptz not null default now(),
  foreign key (organization_id, approval_request_id) references public.approval_requests(organization_id, id) on delete cascade,
  check (decided_by is not null or external_reviewer_name is not null)
);

create table public.external_approval_links (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  approval_request_id uuid not null,
  token_hash text not null unique,
  expires_at timestamptz not null,
  max_uses integer not null default 1 check (max_uses > 0),
  use_count integer not null default 0 check (use_count >= 0),
  revoked_at timestamptz,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  foreign key (organization_id, approval_request_id) references public.approval_requests(organization_id, id) on delete cascade,
  check (expires_at > created_at), check (use_count <= max_uses)
);

create table public.qa_scorecards (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null,
  version integer not null,
  criteria jsonb not null check (jsonb_typeof(criteria) = 'array'),
  pass_threshold numeric(5,2) not null check (pass_threshold between 0 and 100),
  published_at timestamptz,
  created_at timestamptz not null default now(),
  unique (organization_id, name, version), unique (organization_id, id)
);

create table public.qa_evaluations (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  task_id uuid not null,
  artifact_id uuid,
  scorecard_id uuid not null,
  score numeric(5,2) not null check (score between 0 and 100),
  passed boolean not null,
  results jsonb not null,
  evaluator_agent_id uuid,
  created_at timestamptz not null default now(),
  foreign key (organization_id, task_id) references public.tasks(organization_id, id) on delete cascade,
  foreign key (organization_id, artifact_id) references public.artifacts(organization_id, id) on delete set null,
  foreign key (organization_id, scorecard_id) references public.qa_scorecards(organization_id, id) on delete restrict,
  foreign key (organization_id, evaluator_agent_id) references public.agents(organization_id, id) on delete set null
);

-- -----------------------------------------------------------------------------
-- Conhecimento e memoria
-- -----------------------------------------------------------------------------

create table public.knowledge_documents (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  title text not null,
  source_type text not null check (source_type in ('upload','url','text','task','integration')),
  source_uri text,
  storage_path text,
  confidentiality public.risk_level not null default 'medium',
  review_status public.review_status not null default 'draft',
  valid_from timestamptz,
  valid_until timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  check (valid_until is null or valid_from is null or valid_until > valid_from)
);

create table public.knowledge_chunks (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  document_id uuid not null,
  ordinal integer not null check (ordinal >= 0),
  content text not null,
  embedding extensions.vector(1536),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (document_id, ordinal),
  foreign key (organization_id, document_id) references public.knowledge_documents(organization_id, id) on delete cascade
);

create index knowledge_chunks_embedding_hnsw_idx on public.knowledge_chunks using hnsw (embedding vector_cosine_ops) where embedding is not null;
create index knowledge_chunks_document_idx on public.knowledge_chunks(document_id, ordinal);

create table public.memory_items (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  task_id uuid,
  room_id uuid,
  kind public.memory_kind not null,
  content text not null,
  source_reference jsonb not null default '{}'::jsonb,
  confidence numeric(5,2) check (confidence between 0 and 100),
  review_status public.review_status not null default 'pending',
  valid_until timestamptz,
  embedding extensions.vector(1536),
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (organization_id, task_id) references public.tasks(organization_id, id) on delete set null,
  foreign key (organization_id, room_id) references public.rooms(organization_id, id) on delete set null
);

create index memory_items_embedding_hnsw_idx on public.memory_items using hnsw (embedding vector_cosine_ops) where embedding is not null and review_status = 'approved';

-- -----------------------------------------------------------------------------
-- CRM, conteudo e experimentos
-- -----------------------------------------------------------------------------

create table public.crm_accounts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null,
  domain text,
  segment text,
  owner_user_id uuid references auth.users(id) on delete set null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique (organization_id, id), unique nulls not distinct (organization_id, domain)
);

create table public.crm_contacts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  account_id uuid,
  name text not null,
  email extensions.citext,
  phone text,
  consent_status text not null default 'unknown' check (consent_status in ('unknown','granted','denied','revoked')),
  legal_basis text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique (organization_id, id), unique nulls not distinct (organization_id, email),
  foreign key (organization_id, account_id) references public.crm_accounts(organization_id, id) on delete set null
);

create table public.leads (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  account_id uuid,
  contact_id uuid,
  owner_user_id uuid references auth.users(id) on delete set null,
  status public.lead_status not null default 'new',
  source text,
  icp_score numeric(5,2) check (icp_score between 0 and 100),
  score_factors jsonb not null default '{}'::jsonb,
  next_action text,
  next_action_at timestamptz,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, account_id) references public.crm_accounts(organization_id, id) on delete set null,
  foreign key (organization_id, contact_id) references public.crm_contacts(organization_id, id) on delete set null
);

create index leads_org_status_idx on public.leads(organization_id, status, next_action_at);

create table public.lead_signals (
  id bigint generated always as identity primary key,
  organization_id uuid not null,
  lead_id uuid not null,
  signal_type text not null,
  strength numeric(5,2) check (strength between 0 and 100),
  source text,
  payload jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null,
  created_at timestamptz not null default now(),
  foreign key (organization_id, lead_id) references public.leads(organization_id, id) on delete cascade
);

create table public.opportunities (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  lead_id uuid,
  account_id uuid,
  name text not null,
  stage text not null,
  amount numeric(14,2) check (amount >= 0),
  currency char(3) not null default 'BRL',
  probability numeric(5,2) check (probability between 0 and 100),
  expected_close_date date,
  closed_at timestamptz,
  loss_reason text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, lead_id) references public.leads(organization_id, id) on delete set null,
  foreign key (organization_id, account_id) references public.crm_accounts(organization_id, id) on delete set null
);

create table public.campaigns (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null,
  objective text,
  status text not null default 'draft' check (status in ('draft','review','active','paused','completed','canceled')),
  budget numeric(14,2) check (budget >= 0),
  starts_at timestamptz, ends_at timestamptz,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique (organization_id, id), check (ends_at is null or starts_at is null or ends_at > starts_at)
);

create table public.content_assets (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  campaign_id uuid,
  task_id uuid,
  title text not null,
  content_type text not null,
  status public.content_status not null default 'draft',
  body jsonb not null default '{}'::jsonb,
  channel text,
  scheduled_at timestamptz,
  published_at timestamptz,
  external_id text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, campaign_id) references public.campaigns(organization_id, id) on delete set null,
  foreign key (organization_id, task_id) references public.tasks(organization_id, id) on delete set null
);

create table public.experiments (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  campaign_id uuid,
  name text not null,
  hypothesis text not null,
  status public.experiment_status not null default 'draft',
  primary_metric text not null,
  allocation jsonb not null default '{}'::jsonb,
  stop_rule jsonb not null default '{}'::jsonb,
  starts_at timestamptz, ends_at timestamptz,
  result jsonb,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, campaign_id) references public.campaigns(organization_id, id) on delete set null
);

create table public.experiment_variants (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  experiment_id uuid not null,
  name text not null,
  content_asset_id uuid,
  weight numeric(6,5) not null check (weight > 0 and weight <= 1),
  configuration jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (experiment_id, name),
  foreign key (organization_id, experiment_id) references public.experiments(organization_id, id) on delete cascade,
  foreign key (organization_id, content_asset_id) references public.content_assets(organization_id, id) on delete set null
);

create table public.analytics_events (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  event_name text not null,
  actor_user_id uuid references auth.users(id) on delete set null,
  task_id uuid,
  lead_id uuid,
  campaign_id uuid,
  content_asset_id uuid,
  properties jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null,
  received_at timestamptz not null default now(),
  idempotency_key text,
  unique nulls not distinct (organization_id, idempotency_key)
);

create index analytics_events_org_time_idx on public.analytics_events(organization_id, occurred_at desc);

-- -----------------------------------------------------------------------------
-- Notificacoes, webhooks, outbox e auditoria
-- -----------------------------------------------------------------------------

create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  kind text not null,
  title text not null,
  body text,
  resource_type text,
  resource_id uuid,
  read_at timestamptz,
  created_at timestamptz not null default now()
);
create index notifications_user_unread_idx on public.notifications(user_id, created_at desc) where read_at is null;

create table public.webhook_endpoints (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  url text not null check (url ~ '^https://'),
  event_types text[] not null,
  secret_reference text not null,
  is_enabled boolean not null default true,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);

create table public.event_outbox (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  event_type text not null,
  aggregate_type text not null,
  aggregate_id uuid not null,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  published_at timestamptz,
  attempts integer not null default 0
);
create index event_outbox_pending_idx on public.event_outbox(created_at) where published_at is null;

create table public.audit_log (
  id bigint generated always as identity primary key,
  organization_id uuid references public.organizations(id) on delete set null,
  actor_user_id uuid references auth.users(id) on delete set null,
  actor_type text not null check (actor_type in ('user','agent','system','external')),
  action text not null,
  resource_type text not null,
  resource_id text,
  risk_level public.risk_level not null default 'low',
  trace_id text,
  ip inet,
  user_agent text,
  changes_redacted jsonb,
  created_at timestamptz not null default now()
);
create index audit_log_org_time_idx on public.audit_log(organization_id, created_at desc);

create or replace function private.protect_audit_log()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if session_user <> 'postgres' or current_user <> 'postgres' then
    raise exception 'immutable_audit_log' using errcode = '23514';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end;
$$;
create trigger audit_log_immutable
before update or delete on public.audit_log
for each row execute function private.protect_audit_log();

-- Tenant and FK predicates drive both API joins and RLS. PostgreSQL does not
-- create indexes for foreign keys, so generate deterministic supporting indexes.
do $$
declare r record;
begin
  for r in
    select c.oid::regclass as relation_name, c.relname as table_name
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    join pg_attribute a on a.attrelid = c.oid
    where n.nspname = 'public' and c.relkind = 'r'
      and a.attname = 'organization_id' and not a.attisdropped
  loop
    execute format('create index if not exists %I on %s (organization_id)',
      r.table_name || '_organization_id_idx', r.relation_name);
  end loop;

  for r in
    select c.conrelid::regclass as relation_name, c.conname,
      string_agg(quote_ident(a.attname), ', ' order by k.ordinality) as columns
    from pg_constraint c
    cross join lateral unnest(c.conkey) with ordinality as k(attnum, ordinality)
    join pg_attribute a on a.attrelid = c.conrelid and a.attnum = k.attnum
    join pg_namespace n on n.oid = c.connamespace
    where c.contype = 'f' and n.nspname = 'public'
      and not exists (
        select 1
        from pg_index i
        where i.indrelid = c.conrelid
          and i.indisvalid
          and (i.indkey::smallint[])[0:cardinality(c.conkey) - 1]
              = c.conkey::smallint[]
      )
    group by c.conrelid, c.conname
  loop
    execute format('create index if not exists %I on %s (%s)',
      left(r.conname, 55) || '_idx', r.relation_name, r.columns);
  end loop;
end $$;

-- -----------------------------------------------------------------------------
-- Triggers e regras de dominio
-- -----------------------------------------------------------------------------

do $$
declare t text;
begin
  foreach t in array array[
    'rooms','model_providers','agents','skills',
    'workflows','knowledge_documents','memory_items','crm_accounts','crm_contacts','leads',
    'opportunities','campaigns','content_assets','experiments','webhook_endpoints'
  ] loop
    execute format('create trigger %I_set_updated_at before update on public.%I for each row execute function private.set_updated_at()', t, t);
  end loop;
end $$;

create or replace function private.prevent_task_dependency_cycle()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if exists (
    with recursive ancestors(task_id) as (
      select d.depends_on_task_id
      from public.task_dependencies d
      where d.organization_id = new.organization_id
        and d.task_id = new.depends_on_task_id
      union
      select d.depends_on_task_id
      from public.task_dependencies d
      join ancestors a on a.task_id = d.task_id
      where d.organization_id = new.organization_id
    )
    select 1 from ancestors where task_id = new.task_id
  ) then
    raise exception 'task_dependency_cycle' using errcode = '23514';
  end if;
  return new;
end;
$$;
create trigger task_dependencies_prevent_cycle
before insert or update on public.task_dependencies
for each row execute function private.prevent_task_dependency_cycle();

create or replace function private.reject_immutable_row()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  raise exception 'immutable_record' using errcode = '23514';
end;
$$;
create trigger approval_decisions_immutable
before update or delete on public.approval_decisions
for each row execute function private.reject_immutable_row();

create or replace function private.protect_published_workflow_version()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if old.published_at is not null then
    raise exception 'published_workflow_version_immutable' using errcode = '23514';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end;
$$;
create trigger workflow_versions_protect_published
before update or delete on public.workflow_versions
for each row execute function private.protect_published_workflow_version();

create or replace function private.protect_running_experiment()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if old.status <> 'draft'
     and (new.primary_metric, new.allocation, new.stop_rule)
         is distinct from (old.primary_metric, old.allocation, old.stop_rule) then
    raise exception 'running_experiment_configuration_immutable' using errcode = '23514';
  end if;
  return new;
end;
$$;
create trigger experiments_protect_running_configuration
before update on public.experiments
for each row execute function private.protect_running_experiment();

create or replace function private.valid_task_transition(p_from public.task_status, p_to public.task_status)
returns boolean language sql immutable security invoker set search_path = '' as $$
  select case p_from
    when 'new' then p_to in ('triaged','canceled')
    when 'triaged' then p_to in ('in_progress','waiting_human','canceled')
    when 'in_progress' then p_to in ('waiting_tool','waiting_human','ready_for_review','failed','canceled')
    when 'waiting_tool' then p_to in ('in_progress','failed','canceled')
    when 'waiting_human' then p_to in ('in_progress','ready_for_review','canceled')
    when 'ready_for_review' then p_to in ('approved','in_progress','canceled')
    when 'approved' then p_to in ('done','in_progress')
    when 'failed' then p_to in ('in_progress','canceled')
    else false
  end;
$$;

create or replace function public.transition_task(p_task_id uuid, p_to public.task_status, p_reason text default null, p_expected_version integer default null)
returns public.tasks language plpgsql security definer set search_path = '' as $$
declare v_task public.tasks;
begin
  select * into v_task from public.tasks where id = p_task_id for update;
  if not found then raise exception 'task_not_found' using errcode = 'P0002'; end if;
  if not private.current_user_is_member(v_task.organization_id) then raise exception 'forbidden' using errcode = '42501'; end if;
  if p_expected_version is not null and v_task.version <> p_expected_version then raise exception 'version_conflict' using errcode = '40001'; end if;
  if not private.valid_task_transition(v_task.status, p_to) then raise exception 'invalid_task_transition'; end if;
  insert into public.task_transitions(organization_id, task_id, from_status, to_status, actor_user_id, reason)
  values (v_task.organization_id, v_task.id, v_task.status, p_to, (select auth.uid()), p_reason);
  update public.tasks set status = p_to, version = version + 1,
    completed_at = case when p_to = 'done' then now() else completed_at end,
    canceled_at = case when p_to = 'canceled' then now() else canceled_at end
  where id = p_task_id returning * into v_task;
  return v_task;
end;
$$;

create or replace function public.match_knowledge(p_organization_id uuid, p_embedding extensions.vector(1536), p_threshold double precision default 0.75, p_limit integer default 10)
returns table(chunk_id uuid, document_id uuid, content text, metadata jsonb, similarity double precision)
language sql stable security invoker set search_path = '' as $$
  select c.id, c.document_id, c.content, c.metadata,
    1 - (c.embedding OPERATOR(extensions.<=>) p_embedding) as similarity
  from public.knowledge_chunks c join public.knowledge_documents d on d.id = c.document_id
  where c.organization_id = p_organization_id
    and private.current_user_is_member(p_organization_id)
    and d.review_status = 'approved'
    and (d.valid_until is null or d.valid_until > now())
    and c.embedding is not null
    and 1 - (c.embedding OPERATOR(extensions.<=>) p_embedding) >= p_threshold
  order by c.embedding OPERATOR(extensions.<=>) p_embedding
  limit least(greatest(p_limit, 1), 50);
$$;

revoke execute on function public.transition_task(uuid, public.task_status, text, integer) from public, anon;
grant execute on function public.transition_task(uuid, public.task_status, text, integer) to authenticated;
revoke execute on function public.match_knowledge(uuid, extensions.vector, double precision, integer) from public, anon;
grant execute on function public.match_knowledge(uuid, extensions.vector, double precision, integer) to authenticated;

-- Politicas padrao para entidades tenant-scoped. Escrita direta e permitida a
-- membros operacionais; endpoints devem restringir acoes de alto risco.
do $$
declare t text;
begin
  foreach t in array array[
    'model_providers','models','agents','agent_versions',
    'skills','agent_version_skills','workflows','workflow_versions','playbooks','tasks','task_dependencies',
    'task_transitions','runs','run_steps','tool_calls','cost_events','artifacts','approval_requests',
    'approval_decisions','external_approval_links','qa_scorecards','qa_evaluations','knowledge_documents',
    'knowledge_chunks','memory_items','crm_accounts','crm_contacts','leads','lead_signals','opportunities',
    'campaigns','content_assets','experiments','experiment_variants','analytics_events',
    'webhook_endpoints','event_outbox','audit_log'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('create policy %I on public.%I for select to authenticated using (private.current_user_is_member(organization_id))', t || '_select', t);
  end loop;
end $$;

-- Salas privadas exigem membership explicita; owner/admin preservam acesso de
-- governanca. Mensagens herdam exatamente a visibilidade da sala.
alter table public.rooms enable row level security;
alter table public.room_members enable row level security;
alter table public.messages enable row level security;

create or replace function private.current_user_is_room_member(p_room_id uuid, p_moderator_only boolean default false)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.room_members rm
    where rm.room_id = p_room_id
      and rm.user_id = (select auth.uid())
      and (not p_moderator_only or rm.is_moderator)
  );
$$;
revoke all on function private.current_user_is_room_member(uuid, boolean) from public, anon, authenticated;
grant execute on function private.current_user_is_room_member(uuid, boolean) to authenticated;

create policy rooms_select on public.rooms for select to authenticated using (
  private.current_user_is_member(organization_id)
  and (
    not is_private
    or private.current_user_has_role(organization_id, array['owner','admin']::public.member_role[])
    or private.current_user_is_room_member(rooms.id)
  )
);
create policy rooms_insert on public.rooms for insert to authenticated
with check (private.current_user_is_member(organization_id) and created_by = (select auth.uid()));
create policy rooms_update on public.rooms for update to authenticated using (
  private.current_user_has_role(organization_id, array['owner','admin','manager']::public.member_role[])
  or private.current_user_is_room_member(rooms.id, true)
) with check (private.current_user_is_member(organization_id));

create policy room_members_select on public.room_members for select to authenticated using (
  private.current_user_has_role(organization_id, array['owner','admin']::public.member_role[])
  or private.current_user_is_room_member(room_members.room_id)
  or exists (select 1 from public.rooms r where r.id = room_members.room_id and not r.is_private and private.current_user_is_member(r.organization_id))
);
create policy room_members_insert on public.room_members for insert to authenticated with check (
  private.current_user_has_role(organization_id, array['owner','admin','manager']::public.member_role[])
  or private.current_user_is_room_member(room_members.room_id, true)
);
create policy room_members_delete on public.room_members for delete to authenticated using (
  user_id = (select auth.uid())
  or private.current_user_has_role(organization_id, array['owner','admin']::public.member_role[])
  or private.current_user_is_room_member(room_members.room_id, true)
);

create policy messages_select on public.messages for select to authenticated using (
  exists (select 1 from public.rooms r where r.id = messages.room_id and (
    (not r.is_private and private.current_user_is_member(r.organization_id))
    or private.current_user_has_role(r.organization_id, array['owner','admin']::public.member_role[])
    or private.current_user_is_room_member(r.id)
  ))
);
create policy messages_insert on public.messages for insert to authenticated with check (
  author_user_id = (select auth.uid()) and exists (
    select 1 from public.rooms r where r.id = messages.room_id and (
      (not r.is_private and private.current_user_is_member(r.organization_id))
      or private.current_user_is_room_member(r.id)
    )
  )
);
create policy messages_update_own on public.messages for update to authenticated
using (
  author_user_id = (select auth.uid()) and deleted_at is null
  and exists (
    select 1 from public.rooms r where r.id = messages.room_id and r.organization_id = messages.organization_id
      and ((not r.is_private and private.current_user_is_member(r.organization_id))
        or private.current_user_is_room_member(r.id))
  )
)
with check (
  author_user_id = (select auth.uid())
  and exists (
    select 1 from public.rooms r where r.id = messages.room_id and r.organization_id = messages.organization_id
      and ((not r.is_private and private.current_user_is_member(r.organization_id))
        or private.current_user_is_room_member(r.id))
  )
);

create or replace function private.preserve_message_scope()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if (new.organization_id, new.room_id) is distinct from (old.organization_id, old.room_id) then
    raise exception 'message_retarget_forbidden' using errcode = '23514';
  end if;
  return new;
end;
$$;
create trigger messages_preserve_scope
before update on public.messages
for each row execute function private.preserve_message_scope();

-- Escrita colaborativa.
do $$
declare t text;
begin
  foreach t in array array['task_dependencies','artifacts','knowledge_documents','memory_items','crm_accounts','crm_contacts','leads','lead_signals','opportunities','campaigns','content_assets','experiments','experiment_variants'] loop
    execute format('create policy %I on public.%I for insert to authenticated with check (private.current_user_is_member(organization_id))', t || '_insert', t);
    execute format('create policy %I on public.%I for update to authenticated using (private.current_user_is_member(organization_id)) with check (private.current_user_is_member(organization_id))', t || '_update', t);
  end loop;
end $$;

create policy tasks_insert on public.tasks for insert to authenticated
with check (private.current_user_is_member(organization_id));
create policy tasks_update_safe on public.tasks for update to authenticated
using (private.current_user_is_member(organization_id))
with check (private.current_user_is_member(organization_id));

create policy approval_requests_insert on public.approval_requests for insert to authenticated
with check (private.current_user_is_member(organization_id));
create policy approval_requests_update_admin on public.approval_requests for update to authenticated
using (private.current_user_has_role(organization_id, array['owner','admin']::public.member_role[]))
with check (private.current_user_has_role(organization_id, array['owner','admin']::public.member_role[]));

create policy approval_decisions_insert_reviewer on public.approval_decisions for insert to authenticated
with check (
  decided_by = (select auth.uid())
  and exists (
    select 1 from public.approval_requests ar
    where ar.id = approval_decisions.approval_request_id
      and ar.organization_id = approval_decisions.organization_id
      and ar.status = 'pending'
      and (
        private.current_user_has_role(ar.organization_id, array['owner','admin']::public.member_role[])
        or (
          ar.assigned_to = (select auth.uid())
          and private.current_user_has_role(ar.organization_id, array['reviewer']::public.member_role[])
        )
      )
  )
);

-- Configuracao administrativa.
do $$
declare t text;
begin
  foreach t in array array['organization_invites','model_providers','models','agents','agent_versions','skills','agent_version_skills','workflows','workflow_versions','playbooks','qa_scorecards','webhook_endpoints'] loop
    execute format('create policy %I on public.%I for insert to authenticated with check (private.current_user_has_role(organization_id, array[''owner'',''admin'',''manager'']::public.member_role[]))', t || '_manage_insert', t);
    execute format('create policy %I on public.%I for update to authenticated using (private.current_user_has_role(organization_id, array[''owner'',''admin'',''manager'']::public.member_role[])) with check (private.current_user_has_role(organization_id, array[''owner'',''admin'',''manager'']::public.member_role[]))', t || '_manage_update', t);
    execute format('create policy %I on public.%I for delete to authenticated using (private.current_user_has_role(organization_id, array[''owner'',''admin'']::public.member_role[]))', t || '_manage_delete', t);
  end loop;
end $$;

-- Tabelas append-only/worker: sem INSERT/UPDATE para authenticated por padrao.
-- runs, run_steps, tool_calls, cost_events, task_transitions, qa_evaluations,
-- analytics_events, event_outbox e audit_log sao escritas pelo backend service_role.

alter table public.notifications enable row level security;
create policy notifications_update_own on public.notifications for update to authenticated
using (user_id = (select auth.uid()) and private.current_user_is_member(organization_id))
with check (user_id = (select auth.uid()) and private.current_user_is_member(organization_id));
create policy notifications_select_own_or_elevated on public.notifications for select to authenticated
using (
  private.current_user_is_member(organization_id)
  and (user_id = (select auth.uid())
    or exists (
      select 1 from public.organization_members m
      where m.organization_id = notifications.organization_id
        and m.user_id = (select auth.uid())
        and m.status = 'active'
        and m.role in ('owner','admin')
    ))
);

-- -----------------------------------------------------------------------------
-- Grants explicitos para Data API. RLS continua sendo aplicada.
-- -----------------------------------------------------------------------------

revoke all on all tables in schema public from anon, authenticated;
grant select, insert, update, delete on table
  public.profiles, public.organizations, public.organization_members, public.organization_invites,
  public.rooms, public.room_members, public.messages, public.model_providers, public.models,
  public.agents, public.agent_versions, public.skills, public.agent_version_skills,
  public.workflows, public.workflow_versions, public.playbooks,
  public.task_dependencies, public.artifacts,
  public.qa_scorecards, public.knowledge_documents, public.memory_items, public.crm_accounts,
  public.crm_contacts, public.leads, public.lead_signals, public.opportunities, public.campaigns,
  public.content_assets, public.experiments, public.experiment_variants,
  public.webhook_endpoints
to authenticated;

grant select, insert, delete on public.tasks to authenticated;
grant update (
  room_id, source_message_id, title, objective, priority, risk_level, requester_id,
  assignee_id, agent_id, workflow_version_id, due_at, sla_at, estimated_cost, metadata
) on public.tasks to authenticated;
grant select, insert on public.approval_requests to authenticated;
grant update (assigned_to, due_at) on public.approval_requests to authenticated;
grant select, insert on public.approval_decisions to authenticated;
grant select, update on public.notifications to authenticated;

grant select on table
  public.task_transitions, public.runs, public.run_steps, public.tool_calls, public.cost_events,
  public.qa_evaluations, public.knowledge_chunks, public.analytics_events, public.audit_log
to authenticated;

grant select, insert, update, delete on public.audit_log to service_role;

grant usage, select on all sequences in schema public to authenticated;

revoke execute on all functions in schema private from public;
alter default privileges for role postgres in schema private revoke execute on functions from public;
grant execute on function private.current_user_is_member(uuid) to authenticated;
grant execute on function private.current_user_has_role(uuid, public.member_role[]) to authenticated;
grant execute on function private.current_user_is_room_member(uuid, boolean) to authenticated;

commit;
