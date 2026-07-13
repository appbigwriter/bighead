-- Serialize every embedding write before it changes a row. Relation-level
-- ROW EXCLUSIVE locks do not conflict with each other, so activation no longer
-- needs SHARE locks whose ordering could deadlock with multi-table writers.

create table private.embedding_activation_context (
  backend_pid integer not null,
  transaction_id bigint not null,
  run_id uuid not null references private.embedding_reindex_runs(id) on delete cascade,
  primary key (backend_pid, transaction_id)
);
revoke all on private.embedding_activation_context from public, anon, authenticated;
grant select, insert, delete on private.embedding_activation_context to service_role;

drop trigger knowledge_chunks_enqueue_open_reindex on public.knowledge_chunks;
drop trigger memory_items_enqueue_open_reindex on public.memory_items;

create or replace function private.guard_and_enqueue_embedding_write() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_run_id uuid;
  v_target_profile_id uuid;
  v_active_profile_id uuid;
  v_entity_type text;
begin
  perform pg_advisory_xact_lock(hashtextextended('bighead.embedding.reindex',0));

  select id into v_active_profile_id
    from private.embedding_profiles
   where status = 'active';
  select id, target_profile_id into v_run_id, v_target_profile_id
    from private.embedding_reindex_runs
   where status in ('running','ready')
   for update;

  -- Activation is the only operation allowed to write the target profile before
  -- it becomes active. The context is transaction-scoped and inaccessible to
  -- application roles.
  if v_run_id is not null
     and new.embedding_profile_id = v_target_profile_id
     and exists (
       select 1
         from private.embedding_activation_context c
        where c.backend_pid = pg_backend_pid()
          and c.transaction_id = txid_current()
          and c.run_id = v_run_id
     ) then
    return new;
  end if;

  if new.embedding_profile_id is null then
    new.embedding_profile_id := v_active_profile_id;
  end if;
  if new.embedding_profile_id is distinct from v_active_profile_id then
    raise exception 'embedding_profile_changed_retry' using errcode='40001';
  end if;
  if v_run_id is null then
    return new;
  end if;

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
revoke execute on function private.guard_and_enqueue_embedding_write()
  from public,anon,authenticated;

-- PostgreSQL executes same-kind triggers alphabetically. The 00_ prefix makes
-- the advisory barrier run before the existing dimension-validation triggers.
create trigger "00_knowledge_chunks_embedding_write_barrier"
  before insert or update of content,embedding,embedding_profile_id
  on public.knowledge_chunks
  for each row execute function private.guard_and_enqueue_embedding_write();
create trigger "00_memory_items_embedding_write_barrier"
  before insert or update of content,embedding,embedding_profile_id
  on public.memory_items
  for each row execute function private.guard_and_enqueue_embedding_write();

create or replace function private.complete_embedding_reindex_item(
  p_run_id uuid, p_entity_type text, p_entity_id uuid, p_embedding extensions.vector
) returns void
language plpgsql security invoker set search_path = '' as $$
declare v_dimensions integer;
begin
  perform pg_advisory_xact_lock(hashtextextended('bighead.embedding.reindex',0));
  select p.dimensions into v_dimensions
    from private.embedding_reindex_runs r
    join private.embedding_profiles p on p.id=r.target_profile_id
   where r.id=p_run_id and r.status='running';
  if not found then raise exception 'embedding_reindex_not_running' using errcode='55000'; end if;
  if extensions.vector_dims(p_embedding) <> v_dimensions then
    raise exception 'embedding_dimension_mismatch' using errcode='22023';
  end if;
  update private.embedding_reindex_items
     set target_embedding=p_embedding,status='ready',attempts=attempts+1,
         error=null,updated_at=now()
   where run_id=p_run_id and entity_type=p_entity_type and entity_id=p_entity_id;
  if not found then raise exception 'embedding_reindex_item_not_found' using errcode='P0002'; end if;
  if not exists(
    select 1 from private.embedding_reindex_items where run_id=p_run_id and status<>'ready'
  ) then
    update private.embedding_reindex_runs set status='ready' where id=p_run_id;
  end if;
end;
$$;

-- HNSW builds must run outside a transaction block because the concurrent form
-- is the only form compatible with live writers. The operator/worker obtains
-- these canonical statements, executes each on an autocommit connection, and
-- only then calls activate_embedding_reindex.
create or replace function private.embedding_reindex_index_commands(p_run_id uuid)
returns table(index_name text, ddl text)
language plpgsql security invoker set search_path = '' as $$
declare v_profile_id uuid; v_dimensions integer; v_suffix text;
begin
  select r.target_profile_id,p.dimensions into v_profile_id,v_dimensions
    from private.embedding_reindex_runs r
    join private.embedding_profiles p on p.id=r.target_profile_id
   where r.id=p_run_id and r.status='ready';
  if not found then
    raise exception 'embedding_reindex_not_ready' using errcode='55000';
  end if;
  v_suffix := replace(left(v_profile_id::text,8),'-','');
  index_name := 'knowledge_chunks_embedding_'||v_suffix||'_hnsw_idx';
  ddl := format(
    'create index concurrently if not exists %I on public.knowledge_chunks using hnsw ((embedding::extensions.vector(%s)) extensions.vector_cosine_ops) where embedding_profile_id=%L and embedding is not null',
    index_name,v_dimensions,v_profile_id
  );
  return next;
  index_name := 'memory_items_embedding_'||v_suffix||'_hnsw_idx';
  ddl := format(
    'create index concurrently if not exists %I on public.memory_items using hnsw ((embedding::extensions.vector(%s)) extensions.vector_cosine_ops) where embedding_profile_id=%L and embedding is not null and review_status=''approved''',
    index_name,v_dimensions,v_profile_id
  );
  return next;
end;
$$;
revoke execute on function private.embedding_reindex_index_commands(uuid)
  from public,anon,authenticated;
grant execute on function private.embedding_reindex_index_commands(uuid) to service_role;

create or replace function private.activate_embedding_reindex(p_run_id uuid) returns void
language plpgsql security invoker set search_path = '' as $$
declare
  v_profile_id uuid;
  v_dimensions integer;
  v_suffix text;
  v_knowledge_index text;
  v_memory_index text;
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
  v_suffix := replace(left(v_profile_id::text,8),'-','');
  v_knowledge_index := 'knowledge_chunks_embedding_'||v_suffix||'_hnsw_idx';
  v_memory_index := 'memory_items_embedding_'||v_suffix||'_hnsw_idx';
  if not exists(
    select 1 from pg_catalog.pg_index i
    join pg_catalog.pg_class c on c.oid=i.indexrelid
    join pg_catalog.pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname=v_knowledge_index and i.indisvalid
  ) or not exists(
    select 1 from pg_catalog.pg_index i
    join pg_catalog.pg_class c on c.oid=i.indexrelid
    join pg_catalog.pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname=v_memory_index and i.indisvalid
  ) then
    raise exception 'embedding_reindex_indexes_not_ready' using errcode='55000';
  end if;

  insert into private.embedding_activation_context(backend_pid,transaction_id,run_id)
  values(pg_backend_pid(),txid_current(),p_run_id);

  update public.knowledge_chunks c set embedding=i.target_embedding,embedding_profile_id=v_profile_id
    from private.embedding_reindex_items i
   where i.run_id=p_run_id and i.entity_type='knowledge_chunk' and i.entity_id=c.id;
  update public.memory_items m set embedding=i.target_embedding,embedding_profile_id=v_profile_id
    from private.embedding_reindex_items i
   where i.run_id=p_run_id and i.entity_type='memory_item' and i.entity_id=m.id;

  delete from private.embedding_activation_context
   where backend_pid=pg_backend_pid() and transaction_id=txid_current();

  update private.embedding_profiles set status='retired' where status='active';
  update private.embedding_profiles set status='active',activated_at=now() where id=v_profile_id;
  update private.embedding_reindex_runs set status='activated',activated_at=now() where id=p_run_id;
end;
$$;
