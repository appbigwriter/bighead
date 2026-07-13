-- Serialize embedding migrations and include rows created while a run is open.

create unique index embedding_reindex_runs_one_open_idx
  on private.embedding_reindex_runs ((true))
  where status in ('running','ready');

create or replace function private.start_embedding_reindex(
  p_provider text, p_model_name text, p_dimensions integer, p_requested_by uuid default null
) returns uuid
language plpgsql security invoker set search_path = '' as $$
declare v_profile_id uuid; v_run_id uuid; v_active private.embedding_profiles;
begin
  perform pg_advisory_xact_lock(hashtextextended('bighead.embedding.reindex',0));
  if p_dimensions not between 1 and 2000 then
    raise exception 'unsupported_embedding_dimensions' using errcode = '22023';
  end if;
  select * into v_active from private.embedding_profiles where status='active' for update;
  if v_active.provider=p_provider and v_active.model_name=p_model_name
     and v_active.dimensions=p_dimensions then
    raise exception 'embedding_profile_already_active' using errcode='55000';
  end if;
  if exists (select 1 from private.embedding_reindex_runs where status in ('running','ready')) then
    raise exception 'embedding_reindex_already_running' using errcode = '55000';
  end if;
  insert into private.embedding_profiles(provider,model_name,dimensions,status)
  values(p_provider,p_model_name,p_dimensions,'reindexing')
  on conflict(provider,model_name,dimensions) do update set status='reindexing'
    where private.embedding_profiles.status='retired'
  returning id into v_profile_id;
  if v_profile_id is null then
    raise exception 'embedding_profile_not_reusable' using errcode='55000';
  end if;
  insert into private.embedding_reindex_runs(target_profile_id,requested_by)
  values(v_profile_id,p_requested_by) returning id into v_run_id;
  insert into private.embedding_reindex_items(run_id,entity_type,entity_id)
  select v_run_id,'knowledge_chunk',id from public.knowledge_chunks
  union all
  select v_run_id,'memory_item',id from public.memory_items;
  if not found then
    update private.embedding_reindex_runs set status='ready' where id=v_run_id;
  end if;
  return v_run_id;
end;
$$;

create or replace function private.enqueue_open_embedding_reindex_item() returns trigger
language plpgsql security definer set search_path = '' as $$
declare v_run_id uuid; v_entity_type text;
begin
  perform pg_advisory_xact_lock(hashtextextended('bighead.embedding.reindex',0));
  select id into v_run_id from private.embedding_reindex_runs
   where status in ('running','ready') for update;
  if v_run_id is null then return new; end if;
  v_entity_type := case tg_table_name
    when 'knowledge_chunks' then 'knowledge_chunk'
    when 'memory_items' then 'memory_item'
    else null end;
  if v_entity_type is null then
    raise exception 'unsupported_embedding_entity';
  end if;
  insert into private.embedding_reindex_items(run_id,entity_type,entity_id)
  values(v_run_id,v_entity_type,new.id)
  on conflict(run_id,entity_type,entity_id) do update
    set status='pending',target_embedding=null,error=null,updated_at=now();
  update private.embedding_reindex_runs set status='running' where id=v_run_id;
  return new;
end;
$$;
revoke execute on function private.enqueue_open_embedding_reindex_item()
  from public,anon,authenticated;

create trigger knowledge_chunks_enqueue_open_reindex
  after insert or update of content on public.knowledge_chunks
  for each row execute function private.enqueue_open_embedding_reindex_item();
create trigger memory_items_enqueue_open_reindex
  after insert or update of content on public.memory_items
  for each row execute function private.enqueue_open_embedding_reindex_item();

create or replace function private.activate_embedding_reindex(p_run_id uuid) returns void
language plpgsql security invoker set search_path = '' as $$
declare v_profile_id uuid; v_dimensions integer; v_suffix text;
begin
  perform pg_advisory_xact_lock(hashtextextended('bighead.embedding.reindex',0));
  select r.target_profile_id,p.dimensions into v_profile_id,v_dimensions
    from private.embedding_reindex_runs r join private.embedding_profiles p on p.id=r.target_profile_id
   where r.id=p_run_id and r.status='ready' for update of r;
  if not found or exists(
    select 1 from private.embedding_reindex_items where run_id=p_run_id and status<>'ready'
  ) then
    raise exception 'embedding_reindex_not_ready' using errcode='55000';
  end if;
  if v_profile_id=(select id from private.embedding_profiles where status='active') then
    raise exception 'embedding_profile_already_active' using errcode='55000';
  end if;

  update public.knowledge_chunks c set embedding=i.target_embedding,embedding_profile_id=v_profile_id
    from private.embedding_reindex_items i
   where i.run_id=p_run_id and i.entity_type='knowledge_chunk' and i.entity_id=c.id;
  update public.memory_items m set embedding=i.target_embedding,embedding_profile_id=v_profile_id
    from private.embedding_reindex_items i
   where i.run_id=p_run_id and i.entity_type='memory_item' and i.entity_id=m.id;

  update private.embedding_profiles set status='retired' where status='active';
  update private.embedding_profiles set status='active',activated_at=now() where id=v_profile_id;
  update private.embedding_reindex_runs set status='activated',activated_at=now() where id=p_run_id;

  v_suffix := replace(left(v_profile_id::text,8),'-','');
  execute format(
    'create index %I on public.knowledge_chunks using hnsw ((embedding::extensions.vector(%s)) extensions.vector_cosine_ops) where embedding_profile_id=%L and embedding is not null',
    'knowledge_chunks_embedding_'||v_suffix||'_hnsw_idx',v_dimensions,v_profile_id
  );
  execute format(
    'create index %I on public.memory_items using hnsw ((embedding::extensions.vector(%s)) extensions.vector_cosine_ops) where embedding_profile_id=%L and embedding is not null and review_status=''approved''',
    'memory_items_embedding_'||v_suffix||'_hnsw_idx',v_dimensions,v_profile_id
  );
end;
$$;

alter table public.crm_import_rows
  add column last_resume_fingerprint text,
  add column last_resume_at timestamptz;
