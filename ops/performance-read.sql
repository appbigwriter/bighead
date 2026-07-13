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
     or (select count(*) from public.notifications where organization_id = 'a7100000-0000-0000-0000-000000000001' and user_id = 'd1000000-0000-0000-0000-000000000004') < 5000 then
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
  end loop;
end
$performance$;

reset role;
select operation || '=' || round(percentile_cont(0.95) within group (order by elapsed_ms)::numeric, 3)
from bighead_perf_samples
group by operation
order by operation;
rollback;
