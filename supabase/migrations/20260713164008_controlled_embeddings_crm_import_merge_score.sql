-- Controlled, side-by-side embedding migrations and resumable CRM ingestion.

create table private.embedding_profiles (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  model_name text not null,
  dimensions integer not null check (dimensions between 1 and 2000),
  status text not null check (status in ('reindexing','active','retired')),
  created_at timestamptz not null default now(),
  activated_at timestamptz,
  unique (provider, model_name, dimensions)
);

create unique index embedding_profiles_one_active_idx
  on private.embedding_profiles ((status)) where status = 'active';

insert into private.embedding_profiles(provider, model_name, dimensions, status, activated_at)
values ('bootstrap', 'legacy-1536', 1536, 'active', now());

drop index public.knowledge_chunks_embedding_hnsw_idx;
drop index public.memory_items_embedding_hnsw_idx;
alter table public.knowledge_chunks alter column embedding type extensions.vector
  using embedding::extensions.vector;
alter table public.memory_items alter column embedding type extensions.vector
  using embedding::extensions.vector;

alter table public.knowledge_chunks
  add column embedding_profile_id uuid references private.embedding_profiles(id);
alter table public.memory_items
  add column embedding_profile_id uuid references private.embedding_profiles(id);

update public.knowledge_chunks
set embedding_profile_id = (select id from private.embedding_profiles where status = 'active');
update public.memory_items
set embedding_profile_id = (select id from private.embedding_profiles where status = 'active');

alter table public.knowledge_chunks alter column embedding_profile_id set not null;
alter table public.memory_items alter column embedding_profile_id set not null;

create or replace function private.assign_and_validate_embedding_profile() returns trigger
language plpgsql security definer set search_path = '' as $$
declare v_dimensions integer;
begin
  if new.embedding_profile_id is null then
    select id into new.embedding_profile_id from private.embedding_profiles where status='active';
  end if;
  select dimensions into v_dimensions from private.embedding_profiles where id=new.embedding_profile_id;
  if new.embedding is not null and extensions.vector_dims(new.embedding) <> v_dimensions then
    raise exception 'embedding_dimension_mismatch' using errcode='22023';
  end if;
  return new;
end;
$$;
create trigger knowledge_chunks_embedding_profile
  before insert or update of embedding,embedding_profile_id on public.knowledge_chunks
  for each row execute function private.assign_and_validate_embedding_profile();
create trigger memory_items_embedding_profile
  before insert or update of embedding,embedding_profile_id on public.memory_items
  for each row execute function private.assign_and_validate_embedding_profile();
revoke execute on function private.assign_and_validate_embedding_profile() from public,anon,authenticated;

do $indexes$
declare v_profile_id uuid;
begin
  select id into v_profile_id from private.embedding_profiles where status='active';
  execute format(
    'create index knowledge_chunks_embedding_legacy_1536_hnsw_idx
       on public.knowledge_chunks using hnsw ((embedding::extensions.vector(1536)) extensions.vector_cosine_ops)
       where embedding is not null and embedding_profile_id=%L', v_profile_id
  );
  execute format(
    'create index memory_items_embedding_legacy_1536_hnsw_idx
       on public.memory_items using hnsw ((embedding::extensions.vector(1536)) extensions.vector_cosine_ops)
       where embedding is not null and review_status=''approved'' and embedding_profile_id=%L', v_profile_id
  );
end
$indexes$;

create or replace function public.active_embedding_dimensions() returns integer
language sql stable security definer set search_path = '' as $$
  select dimensions from private.embedding_profiles where status='active'
$$;
revoke execute on function public.active_embedding_dimensions() from public,anon;
grant execute on function public.active_embedding_dimensions() to authenticated,service_role;
create or replace function public.active_embedding_profile_id() returns uuid
language sql stable security definer set search_path = '' as $$
  select id from private.embedding_profiles where status='active'
$$;
revoke execute on function public.active_embedding_profile_id() from public,anon;
grant execute on function public.active_embedding_profile_id() to authenticated,service_role;

create or replace function public.match_knowledge(
  p_organization_id uuid, p_embedding extensions.vector,
  p_threshold double precision default 0.75, p_limit integer default 10
) returns table(chunk_id uuid, document_id uuid, content text, metadata jsonb, similarity double precision)
language plpgsql stable security invoker set search_path = '' as $$
declare v_profile_id uuid; v_dimensions integer;
begin
  select public.active_embedding_profile_id(),public.active_embedding_dimensions()
    into v_profile_id,v_dimensions;
  if extensions.vector_dims(p_embedding) <> v_dimensions then
    raise exception 'embedding_dimension_mismatch' using errcode='22023';
  end if;
  return query execute format(
    'select c.id,c.document_id,c.content,c.metadata,
       1 - ((c.embedding::extensions.vector(%1$s)) OPERATOR(extensions.<=>)
            ($2::extensions.vector(%1$s))) as similarity
       from public.knowledge_chunks c
       join public.knowledge_documents d on d.id=c.document_id and d.organization_id=$1
      where c.organization_id=$1 and c.embedding_profile_id=$5
        and private.current_user_is_member($1)
        and d.review_status=''approved'' and (d.valid_until is null or d.valid_until > now())
        and c.embedding is not null
        and 1 - ((c.embedding::extensions.vector(%1$s)) OPERATOR(extensions.<=>)
                 ($2::extensions.vector(%1$s))) >= $3
      order by (c.embedding::extensions.vector(%1$s)) OPERATOR(extensions.<=>)
               ($2::extensions.vector(%1$s))
      limit least(greatest($4,1),50)', v_dimensions
  ) using p_organization_id,p_embedding,p_threshold,p_limit,v_profile_id;
end;
$$;

create table private.embedding_reindex_runs (
  id uuid primary key default gen_random_uuid(),
  target_profile_id uuid not null references private.embedding_profiles(id),
  status text not null default 'running' check (status in ('running','ready','activated','failed')),
  requested_by uuid references auth.users(id) on delete set null,
  started_at timestamptz not null default now(),
  activated_at timestamptz
);

create table private.embedding_reindex_items (
  run_id uuid not null references private.embedding_reindex_runs(id) on delete cascade,
  entity_type text not null check (entity_type in ('knowledge_chunk','memory_item')),
  entity_id uuid not null,
  status text not null default 'pending' check (status in ('pending','ready','failed')),
  target_embedding extensions.vector,
  attempts integer not null default 0,
  error text,
  updated_at timestamptz not null default now(),
  primary key (run_id, entity_type, entity_id)
);

create index embedding_reindex_items_pending_idx
  on private.embedding_reindex_items(run_id, status, entity_type, entity_id);

create or replace function private.start_embedding_reindex(
  p_provider text, p_model_name text, p_dimensions integer, p_requested_by uuid default null
) returns uuid
language plpgsql security invoker set search_path = '' as $$
declare v_profile_id uuid; v_run_id uuid;
begin
  if p_dimensions not between 1 and 2000 then
    raise exception 'unsupported_embedding_dimensions' using errcode = '22023';
  end if;
  if exists (select 1 from private.embedding_reindex_runs where status in ('running','ready')) then
    raise exception 'embedding_reindex_already_running' using errcode = '55000';
  end if;
  insert into private.embedding_profiles(provider, model_name, dimensions, status)
  values (p_provider, p_model_name, p_dimensions, 'reindexing')
  on conflict (provider, model_name, dimensions) do update set status = 'reindexing'
  returning id into v_profile_id;
  insert into private.embedding_reindex_runs(target_profile_id, requested_by)
  values (v_profile_id, p_requested_by) returning id into v_run_id;
  insert into private.embedding_reindex_items(run_id, entity_type, entity_id)
  select v_run_id, 'knowledge_chunk', id from public.knowledge_chunks
  union all
  select v_run_id, 'memory_item', id from public.memory_items;
  return v_run_id;
end;
$$;

create or replace function private.complete_embedding_reindex_item(
  p_run_id uuid, p_entity_type text, p_entity_id uuid, p_embedding extensions.vector
) returns void
language plpgsql security invoker set search_path = '' as $$
declare v_dimensions integer;
begin
  select p.dimensions into v_dimensions
    from private.embedding_reindex_runs r
    join private.embedding_profiles p on p.id = r.target_profile_id
   where r.id = p_run_id and r.status = 'running';
  if not found then raise exception 'embedding_reindex_not_running' using errcode = '55000'; end if;
  if extensions.vector_dims(p_embedding) <> v_dimensions then
    raise exception 'embedding_dimension_mismatch' using errcode = '22023';
  end if;
  update private.embedding_reindex_items
     set target_embedding = p_embedding, status = 'ready', attempts = attempts + 1,
         error = null, updated_at = now()
   where run_id = p_run_id and entity_type = p_entity_type and entity_id = p_entity_id;
  if not found then raise exception 'embedding_reindex_item_not_found' using errcode = 'P0002'; end if;
  if not exists (select 1 from private.embedding_reindex_items where run_id=p_run_id and status <> 'ready') then
    update private.embedding_reindex_runs set status='ready' where id=p_run_id;
  end if;
end;
$$;

create or replace function private.activate_embedding_reindex(p_run_id uuid) returns void
language plpgsql security invoker set search_path = '' as $$
declare v_profile_id uuid; v_dimensions integer; v_suffix text;
begin
  select r.target_profile_id, p.dimensions into v_profile_id, v_dimensions
    from private.embedding_reindex_runs r join private.embedding_profiles p on p.id=r.target_profile_id
   where r.id=p_run_id and r.status='ready' for update of r;
  if not found then raise exception 'embedding_reindex_not_ready' using errcode = '55000'; end if;

  update public.knowledge_chunks c set embedding=i.target_embedding, embedding_profile_id=v_profile_id
    from private.embedding_reindex_items i
   where i.run_id=p_run_id and i.entity_type='knowledge_chunk' and i.entity_id=c.id;
  update public.memory_items m set embedding=i.target_embedding, embedding_profile_id=v_profile_id
    from private.embedding_reindex_items i
   where i.run_id=p_run_id and i.entity_type='memory_item' and i.entity_id=m.id;

  update private.embedding_profiles set status='retired' where status='active';
  update private.embedding_profiles set status='active', activated_at=now() where id=v_profile_id;
  update private.embedding_reindex_runs set status='activated', activated_at=now() where id=p_run_id;

  v_suffix := replace(left(v_profile_id::text, 8), '-', '');
  execute format(
    'create index %I on public.knowledge_chunks using hnsw ((embedding::extensions.vector(%s)) extensions.vector_cosine_ops) where embedding_profile_id=%L and embedding is not null',
    'knowledge_chunks_embedding_' || v_suffix || '_hnsw_idx', v_dimensions, v_profile_id
  );
  execute format(
    'create index %I on public.memory_items using hnsw ((embedding::extensions.vector(%s)) extensions.vector_cosine_ops) where embedding_profile_id=%L and embedding is not null and review_status=''approved''',
    'memory_items_embedding_' || v_suffix || '_hnsw_idx', v_dimensions, v_profile_id
  );
end;
$$;

revoke all on private.embedding_profiles, private.embedding_reindex_runs,
  private.embedding_reindex_items from public, anon, authenticated;
revoke execute on function private.start_embedding_reindex(text,text,integer,uuid),
  private.complete_embedding_reindex_item(uuid,text,uuid,extensions.vector),
  private.activate_embedding_reindex(uuid) from public, anon, authenticated;
grant select, insert, update on private.embedding_profiles, private.embedding_reindex_runs,
  private.embedding_reindex_items to service_role;
grant execute on function private.start_embedding_reindex(text,text,integer,uuid),
  private.complete_embedding_reindex_item(uuid,text,uuid,extensions.vector),
  private.activate_embedding_reindex(uuid) to service_role;

-- Durable per-row CRM import reports and resume state.
create table public.crm_imports (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  source text not null,
  consent_basis text not null,
  idempotency_key text not null,
  fingerprint text not null,
  status text not null default 'processing' check (status in ('processing','partial','completed','failed')),
  total_rows integer not null check (total_rows > 0),
  accepted_rows integer not null default 0,
  failed_rows integer not null default 0,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  resume_of_id uuid,
  unique (organization_id, id),
  unique (organization_id, idempotency_key),
  foreign key (organization_id, resume_of_id) references public.crm_imports(organization_id, id) on delete restrict
);

create table public.crm_import_rows (
  import_id uuid not null,
  organization_id uuid not null,
  row_number integer not null check (row_number >= 0),
  payload jsonb not null,
  status text not null default 'pending' check (status in ('pending','accepted','failed')),
  action text,
  account_id uuid,
  contact_id uuid,
  lead_id uuid,
  attempts integer not null default 0,
  error_code text,
  error_detail text,
  updated_at timestamptz not null default now(),
  primary key (import_id, row_number),
  foreign key (organization_id, import_id) references public.crm_imports(organization_id, id) on delete cascade,
  foreign key (organization_id, account_id) references public.crm_accounts(organization_id, id) on delete restrict,
  foreign key (organization_id, contact_id) references public.crm_contacts(organization_id, id) on delete restrict,
  foreign key (organization_id, lead_id) references public.leads(organization_id, id) on delete restrict
);

create index crm_imports_org_created_idx on public.crm_imports(organization_id, created_at desc);
create index crm_import_rows_resume_idx on public.crm_import_rows(organization_id, import_id, status, row_number);
alter table public.crm_imports enable row level security;
alter table public.crm_import_rows enable row level security;
create policy crm_imports_select on public.crm_imports for select to authenticated
  using ((select private.current_user_is_member(organization_id)));
create policy crm_import_rows_select on public.crm_import_rows for select to authenticated
  using ((select private.current_user_is_member(organization_id)));
revoke insert, update, delete on public.crm_imports, public.crm_import_rows from authenticated;
grant select on public.crm_imports, public.crm_import_rows to authenticated;
grant all on public.crm_imports, public.crm_import_rows to service_role;

-- Duplicate accounts are tombstoned after references move; they are never deleted.
alter table public.crm_accounts
  add column merged_into_id uuid,
  add column merged_at timestamptz,
  add constraint crm_accounts_merged_target_fk
    foreign key (organization_id, merged_into_id) references public.crm_accounts(organization_id, id) on delete restrict,
  add constraint crm_accounts_no_self_merge check (merged_into_id is null or merged_into_id <> id),
  add constraint crm_accounts_merge_state check ((merged_into_id is null) = (merged_at is null));
create index crm_accounts_merged_into_idx on public.crm_accounts(organization_id, merged_into_id)
  where merged_into_id is not null;

create or replace function private.merge_crm_accounts(
  p_organization_id uuid, p_source_id uuid, p_target_id uuid, p_actor_user_id uuid, p_reason text
) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare v_source public.crm_accounts; v_target public.crm_accounts; v_contacts integer; v_leads integer; v_opportunities integer;
begin
  if p_source_id = p_target_id or nullif(btrim(p_reason),'') is null then
    raise exception 'invalid_account_merge' using errcode='22023';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(p_organization_id::text || least(p_source_id,p_target_id)::text, 0));
  select * into v_source from public.crm_accounts where organization_id=p_organization_id and id=p_source_id for update;
  select * into v_target from public.crm_accounts where organization_id=p_organization_id and id=p_target_id for update;
  if v_source.id is null or v_target.id is null or v_source.merged_into_id is not null or v_target.merged_into_id is not null then
    raise exception 'account_merge_target_not_active' using errcode='P0002';
  end if;
  update public.crm_contacts set account_id=p_target_id where organization_id=p_organization_id and account_id=p_source_id;
  get diagnostics v_contacts = row_count;
  update public.leads set account_id=p_target_id where organization_id=p_organization_id and account_id=p_source_id;
  get diagnostics v_leads = row_count;
  update public.opportunities set account_id=p_target_id where organization_id=p_organization_id and account_id=p_source_id;
  get diagnostics v_opportunities = row_count;
  update public.crm_accounts set merged_into_id=p_target_id, merged_at=now(),
    metadata=metadata || jsonb_build_object('merge_reason',p_reason,'merged_by',p_actor_user_id)
  where id=p_source_id and organization_id=p_organization_id;
  insert into public.audit_log(
    organization_id,actor_user_id,actor_type,action,resource_type,resource_id,risk_level,changes_redacted
  ) values (
    p_organization_id,p_actor_user_id,'user','crm.account.merged','crm_account',p_source_id::text,'medium',
    jsonb_build_object('mergedIntoId',p_target_id,'reason',p_reason,
      'references',jsonb_build_object('contacts',v_contacts,'leads',v_leads,'opportunities',v_opportunities))
  );
  return jsonb_build_object('sourceId',p_source_id,'targetId',p_target_id,
    'references',jsonb_build_object('contacts',v_contacts,'leads',v_leads,'opportunities',v_opportunities));
end;
$$;
revoke execute on function private.merge_crm_accounts(uuid,uuid,uuid,uuid,text) from public,anon,authenticated;
grant execute on function private.merge_crm_accounts(uuid,uuid,uuid,uuid,text) to service_role;

-- Scored leads must carry explainable factors and the algorithm version used.
alter table public.leads add column score_algorithm_version text;
update public.leads set score_algorithm_version='legacy-v1' where icp_score is not null;
alter table public.leads add constraint leads_explainable_score_check check (
  icp_score is null or (
    nullif(btrim(score_algorithm_version),'') is not null
    and jsonb_typeof(score_factors)='object'
    and score_factors <> '{}'::jsonb
  )
);
