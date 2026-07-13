-- UPDATE can lock an existing tuple before a BEFORE ROW trigger runs. Acquire
-- the global reindex guard at statement start so activation can never own the
-- advisory lock while waiting for a tuple held by a writer waiting on that lock.

create or replace function private.lock_embedding_write_statement() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform pg_advisory_xact_lock(hashtextextended('bighead.embedding.reindex',0));
  return null;
end;
$$;
revoke execute on function private.lock_embedding_write_statement()
  from public,anon,authenticated;

create trigger knowledge_chunks_embedding_insert_guard
  before insert on public.knowledge_chunks
  for each statement execute function private.lock_embedding_write_statement();
create trigger knowledge_chunks_embedding_update_guard
  before update of content,embedding,embedding_profile_id on public.knowledge_chunks
  for each statement execute function private.lock_embedding_write_statement();
create trigger memory_items_embedding_insert_guard
  before insert on public.memory_items
  for each statement execute function private.lock_embedding_write_statement();
create trigger memory_items_embedding_update_guard
  before update of content,embedding,embedding_profile_id on public.memory_items
  for each statement execute function private.lock_embedding_write_statement();
