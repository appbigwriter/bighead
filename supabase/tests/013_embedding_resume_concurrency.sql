begin;
create extension if not exists pgtap with schema extensions;
select plan(19);

select has_trigger(
  'public','knowledge_chunks','knowledge_chunks_embedding_insert_guard',
  'knowledge inserts acquire the reindex guard before row processing'
);
select has_trigger(
  'public','knowledge_chunks','knowledge_chunks_embedding_update_guard',
  'knowledge updates acquire the reindex guard before tuple selection'
);
select has_trigger(
  'public','memory_items','memory_items_embedding_insert_guard',
  'memory inserts acquire the reindex guard before row processing'
);
select has_trigger(
  'public','memory_items','memory_items_embedding_update_guard',
  'memory updates acquire the reindex guard before tuple selection'
);

create temporary table concurrency_active(profile_id uuid);
insert into concurrency_active
select id from private.embedding_profiles where status='active';

select has_index(
  'private','embedding_reindex_runs','embedding_reindex_runs_one_open_idx',
  'only one embedding reindex can remain open'
);
select throws_ok(
  $$select private.start_embedding_reindex('bootstrap','legacy-1536',1536,null)$$,
  '55000','embedding_profile_already_active',
  'active profile cannot be changed to reindexing'
);
select is(
  (select count(*)::integer from private.embedding_profiles where status='active'),1,
  'reindexing the active profile never leaves zero active profiles'
);

create temporary table concurrency_reindex(run_id uuid);
insert into concurrency_reindex
select private.start_embedding_reindex('test-provider','concurrency-7d',7,null);

do $complete_initial$
declare item record;
begin
  for item in select entity_type,entity_id from private.embedding_reindex_items
    where run_id=(select run_id from concurrency_reindex)
  loop
    perform private.complete_embedding_reindex_item(
      (select run_id from concurrency_reindex),item.entity_type,item.entity_id,
      '[1,0,0,0,0,0,0]'::extensions.vector
    );
  end loop;
end
$complete_initial$;

select is(
  (select status from private.embedding_reindex_runs
    where id=(select run_id from concurrency_reindex)),
  'ready','initial snapshot can become ready'
);

insert into public.knowledge_documents(id,organization_id,title,source_type,review_status)
values('b7510000-0000-0000-0000-000000000001',
  'a7100000-0000-0000-0000-000000000001','Concurrent insert','text','approved');
insert into public.knowledge_chunks(id,organization_id,document_id,ordinal,content,embedding)
values('b7520000-0000-0000-0000-000000000001',
  'a7100000-0000-0000-0000-000000000001','b7510000-0000-0000-0000-000000000001',0,
  'inserted while ready',
  ('[1,'||array_to_string(array_fill(0::real,array[1535]),',')||']')::extensions.vector);

select is(
  (select status from private.embedding_reindex_items
    where run_id=(select run_id from concurrency_reindex)
      and entity_id='b7520000-0000-0000-0000-000000000001'),
  'pending','insert during reindex is captured'
);
select is(
  (select status from private.embedding_reindex_runs
    where id=(select run_id from concurrency_reindex)),
  'running','new content returns a ready run to running'
);
select throws_ok(
  $$select private.activate_embedding_reindex((select run_id from concurrency_reindex))$$,
  '55000','embedding_reindex_not_ready',
  'activation cannot miss content committed during the run'
);
select is(
  (select count(*)::integer from private.embedding_profiles where status='active'),1,
  'failed activation keeps exactly one active profile'
);

select lives_ok(
  $$select private.complete_embedding_reindex_item(
    (select run_id from concurrency_reindex),'knowledge_chunk',
    'b7520000-0000-0000-0000-000000000001','[1,0,0,0,0,0,0]'::extensions.vector)$$,
  'newly captured row can be completed'
);
do $build_test_indexes$
declare command record;
begin
  for command in
    select ddl from private.embedding_reindex_index_commands(
      (select run_id from concurrency_reindex)
    )
  loop
    execute replace(command.ddl,'create index concurrently','create index');
  end loop;
end
$build_test_indexes$;
select lives_ok(
  $$select private.activate_embedding_reindex((select run_id from concurrency_reindex))$$,
  'fully reconciled run activates'
);
select is(
  (select dimensions from private.embedding_profiles where status='active'),7,
  'controlled activation publishes the target dimension'
);

insert into public.knowledge_documents(id,organization_id,title,source_type,review_status)
values('b7530000-0000-0000-0000-000000000001',
  'a7100000-0000-0000-0000-000000000001','Stale profile guard','text','approved');
select throws_ok(
  $$insert into public.knowledge_chunks(
      id,organization_id,document_id,ordinal,content,embedding_profile_id
    ) values(
      'b7540000-0000-0000-0000-000000000001',
      'a7100000-0000-0000-0000-000000000001',
      'b7530000-0000-0000-0000-000000000001',0,'stale writer',
      (select profile_id from concurrency_active)
    )$$,
  '40001','embedding_profile_changed_retry',
  'a stale knowledge write must retry after activation'
);
select throws_ok(
  $$insert into public.memory_items(
      id,organization_id,kind,content,embedding_profile_id
    ) values(
      'b7550000-0000-0000-0000-000000000001',
      'a7100000-0000-0000-0000-000000000001','fact','stale writer',
      (select profile_id from concurrency_active)
    )$$,
  '40001','embedding_profile_changed_retry',
  'a stale memory write must retry after activation'
);

insert into public.knowledge_chunks(id,organization_id,document_id,ordinal,content)
values('b7560000-0000-0000-0000-000000000001',
  'a7100000-0000-0000-0000-000000000001','b7530000-0000-0000-0000-000000000001',0,
  'current profile knowledge write');
insert into public.memory_items(id,organization_id,kind,content)
values('b7570000-0000-0000-0000-000000000001',
  'a7100000-0000-0000-0000-000000000001','fact','current profile memory write');

select throws_ok(
  $$update public.knowledge_chunks
       set embedding=null,embedding_profile_id=(select profile_id from concurrency_active)
     where id='b7560000-0000-0000-0000-000000000001'$$,
  '40001','embedding_profile_changed_retry',
  'a knowledge update cannot restore a retired embedding profile'
);
select throws_ok(
  $$update public.memory_items
       set embedding=null,embedding_profile_id=(select profile_id from concurrency_active)
     where id='b7570000-0000-0000-0000-000000000001'$$,
  '40001','embedding_profile_changed_retry',
  'a memory update cannot restore a retired embedding profile'
);

select * from finish();
rollback;
