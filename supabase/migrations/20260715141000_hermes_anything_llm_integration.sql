begin;

-- Adicionar colunas de telemetria na tabela public.runs
alter table public.runs
  add column agent_id uuid references public.agents(id) on delete set null,
  add column agent_version_id uuid references public.agent_versions(id) on delete set null,
  add column hermes_profile text,
  add column provider_event_id text,
  add column provider_name text,
  add column model text,
  add column input_tokens integer not null default 0,
  add column output_tokens integer not null default 0,
  add column latency_ms integer not null default 0,
  add column queue_wait_ms integer not null default 0,
  add column rag_latency_ms integer not null default 0,
  add column amount numeric(10, 4) not null default 0,
  add column currency text not null default 'USD',
  add column error_type text,
  add column error_message text,
  add column used_rag boolean not null default false,
  add column used_skill_query_knowledge_base boolean not null default false;

-- Adicionar foreign keys compostas para garantir a consistência do tenant/organization
alter table public.runs
  add constraint runs_agent_tenant_fk foreign key (organization_id, agent_id) references public.agents(organization_id, id) on delete set null,
  add constraint runs_agent_version_tenant_fk foreign key (organization_id, agent_version_id) references public.agent_versions(organization_id, id) on delete set null;

-- Criar a tabela public.anything_llm_ingestions
create table public.anything_llm_ingestions (
  artifact_id uuid primary key references public.artifacts(id) on delete cascade,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  workspace text not null,
  status text not null check (status in ('pending', 'processing', 'success', 'failed')),
  checksum_sha256 text not null,
  mime_type text not null,
  size_bytes integer not null,
  external_document_id text,
  embeddings_updated_at timestamptz,
  error_code text,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, checksum_sha256),
  unique (organization_id, artifact_id)
);

-- Ativar RLS para public.anything_llm_ingestions
alter table public.anything_llm_ingestions enable row level security;

-- Políticas de RLS
drop policy if exists anything_llm_ingestions_select on public.anything_llm_ingestions;
create policy anything_llm_ingestions_select on public.anything_llm_ingestions
  for select to authenticated using (
    private.current_user_has_role(organization_id, array['owner','admin']::public.member_role[])
  );

drop policy if exists anything_llm_ingestions_manage_insert on public.anything_llm_ingestions;
create policy anything_llm_ingestions_manage_insert on public.anything_llm_ingestions
  for insert to authenticated with check (
    private.current_user_has_role(organization_id, array['owner','admin']::public.member_role[])
  );

drop policy if exists anything_llm_ingestions_manage_update on public.anything_llm_ingestions;
create policy anything_llm_ingestions_manage_update on public.anything_llm_ingestions
  for update to authenticated using (
    private.current_user_has_role(organization_id, array['owner','admin']::public.member_role[])
  ) with check (
    private.current_user_has_role(organization_id, array['owner','admin']::public.member_role[])
  );

commit;
