\set ON_ERROR_STOP on
\pset tuples_only on
\pset format unaligned

create temporary table bighead_perf_samples (
  operation text not null,
  elapsed_ms double precision not null
) on commit preserve rows;
grant insert, select on bighead_perf_samples to authenticated;

begin;
select pg_advisory_xact_lock(hashtext('bighead.performance'));
insert into public.rooms (organization_id, name, created_by, updated_at)
select 'a7100000-0000-0000-0000-000000000001', '__perf_room_' || item,
       'd1000000-0000-0000-0000-000000000004', now() - make_interval(secs => item)
from generate_series(1, 5000) as item;
insert into public.tasks (organization_id, title, objective, requester_id, updated_at)
select 'a7100000-0000-0000-0000-000000000001', '__perf_task_' || item,
       'Performance workload', 'd1000000-0000-0000-0000-000000000004',
       now() - make_interval(secs => item)
from generate_series(1, 5000) as item;
insert into public.notifications (organization_id, user_id, kind, title, created_at)
select 'a7100000-0000-0000-0000-000000000001',
       'd1000000-0000-0000-0000-000000000004', 'performance', '__perf_notification_' || item,
       now() - make_interval(secs => item)
from generate_series(1, 5000) as item;
insert into public.knowledge_documents(
  id,organization_id,title,source_type,review_status,created_by
) values (
  'a71f0000-0000-0000-0000-000000000001',
  'a7100000-0000-0000-0000-000000000001','__perf_vector_document','text','approved',
  'd1000000-0000-0000-0000-000000000004'
);
insert into public.knowledge_chunks(organization_id,document_id,ordinal,content,embedding)
select 'a7100000-0000-0000-0000-000000000001',
       'a71f0000-0000-0000-0000-000000000001',item,'__perf_vector_chunk_' || item,
       ('[1,' || array_to_string(array_fill(0::real,array[1535]),',') || ']')::extensions.vector
from generate_series(1, 5000) as item;
analyze public.knowledge_chunks;

do $vector_plan$
declare plan json; active_profile uuid;
begin
  select public.active_embedding_profile_id() into active_profile;
  execute format(
    'explain (format json) select id from public.knowledge_chunks
      where organization_id=%L and embedding_profile_id=%L and embedding is not null
      order by (embedding::extensions.vector(1536)) OPERATOR(extensions.<=>)
        (''[1,'' || array_to_string(array_fill(0::real,array[1535]),'','') || '']'')::extensions.vector(1536)
      limit 10',
    'a7100000-0000-0000-0000-000000000001',active_profile
  ) into plan;
  if plan::text not like '%knowledge_chunks_embedding_legacy_1536_hnsw_idx%' then
    raise exception 'representative vector plan did not use HNSW index: %', plan;
  end if;
end
$vector_plan$;

select set_config(
  'request.jwt.claims',
  '{"sub":"d1000000-0000-0000-0000-000000000004","role":"authenticated","organization_id":"a7100000-0000-0000-0000-000000000001"}',
  false
);
set role authenticated;

do $cardinality$
begin
  if (select count(*) from public.rooms where organization_id = 'a7100000-0000-0000-0000-000000000001') < 5000
     or (select count(*) from public.tasks where organization_id = 'a7100000-0000-0000-0000-000000000001') < 5000
     or (select count(*) from public.notifications where organization_id = 'a7100000-0000-0000-0000-000000000001' and user_id = 'd1000000-0000-0000-0000-000000000004') < 5000
     or (select count(*) from public.knowledge_chunks where organization_id = 'a7100000-0000-0000-0000-000000000001') < 5000 then
    raise exception 'RLS performance workload is not visible at required cardinality';
  end if;
end
$cardinality$;

do $performance$
declare
  started_at timestamptz;
  iteration integer;
begin
  for iteration in 1..250 loop
    started_at := clock_timestamp();
    perform id from public.rooms
      where organization_id = 'a7100000-0000-0000-0000-000000000001'
      order by updated_at desc, id desc limit 50;
    insert into bighead_perf_samples values ('rooms.list', extract(epoch from clock_timestamp() - started_at) * 1000);

    started_at := clock_timestamp();
    perform id from public.tasks
      where organization_id = 'a7100000-0000-0000-0000-000000000001'
      order by updated_at desc, id desc limit 50;
    insert into bighead_perf_samples values ('tasks.list', extract(epoch from clock_timestamp() - started_at) * 1000);

    started_at := clock_timestamp();
    perform id from public.notifications
      where organization_id = 'a7100000-0000-0000-0000-000000000001'
        and user_id = 'd1000000-0000-0000-0000-000000000004'
      order by created_at desc, id desc limit 50;
    insert into bighead_perf_samples values ('notifications.list', extract(epoch from clock_timestamp() - started_at) * 1000);

    started_at := clock_timestamp();
    perform * from public.match_knowledge(
      'a7100000-0000-0000-0000-000000000001',
      ('[1,' || array_to_string(array_fill(0::real,array[1535]),',') || ']')::extensions.vector,
      0.9,10
    );
    insert into bighead_perf_samples values ('knowledge.vector', extract(epoch from clock_timestamp() - started_at) * 1000);
  end loop;
end
$performance$;

reset role;
select operation || '=' || round(percentile_cont(0.95) within group (order by elapsed_ms)::numeric, 3)
from bighead_perf_samples
group by operation
order by operation;
rollback;
