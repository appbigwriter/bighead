begin;
create extension if not exists pgtap with schema extensions;
select plan(8);

insert into public.organizations(id,name,slug)
values('61410000-0000-0000-0000-000000000001','Run failure tenant','run-failure-tenant');
insert into public.tasks(id,organization_id,title,objective)
values
 ('61420000-0000-0000-0000-000000000001','61410000-0000-0000-0000-000000000001','Retry exhausted','test'),
 ('61420000-0000-0000-0000-000000000002','61410000-0000-0000-0000-000000000001','Lease exhausted','test');
insert into public.runs(
  id,organization_id,task_id,idempotency_key,status,attempt,max_attempts,
  locked_by,locked_until
) values
 ('61430000-0000-0000-0000-000000000001','61410000-0000-0000-0000-000000000001',
  '61420000-0000-0000-0000-000000000001','retry-exhausted','running',2,2,
  'worker-fail',now()+interval '1 minute'),
 ('61430000-0000-0000-0000-000000000002','61410000-0000-0000-0000-000000000001',
  '61420000-0000-0000-0000-000000000002','lease-exhausted','running',2,2,
  'dead-worker',now()-interval '1 minute');

set local role service_role;
select is(
  public.fail_run(
    '61430000-0000-0000-0000-000000000001','worker-fail','provider timeout'
  ),
  'dead_letter'::public.run_status,
  'retry exhaustion reaches dead letter'
);
reset role;
select is(
  (select count(*) from public.event_outbox
    where aggregate_id='61430000-0000-0000-0000-000000000001'
      and event_type='run.failed'),
  1::bigint,
  'retry exhaustion emits exactly one run.failed event'
);
select is(
  (select payload->>'errorCode' from public.event_outbox
    where aggregate_id='61430000-0000-0000-0000-000000000001'
      and event_type='run.failed'),
  'retry_exhausted',
  'retry exhaustion event preserves terminal error code'
);
set local role service_role;
select throws_ok(
  $$select public.fail_run(
    '61430000-0000-0000-0000-000000000001','worker-fail','duplicate'
  )$$,
  '55000','run_lease_lost','terminal run cannot be failed twice'
);
select is(
  (select count(*) from public.claim_runs('recovery-worker',10,60)),
  0::bigint,
  'exhausted expired lease is not reclaimed'
);
reset role;
select is(
  (select status::text from public.runs
    where id='61430000-0000-0000-0000-000000000002'),
  'dead_letter',
  'expired lease exhaustion reaches dead letter'
);
select is(
  (select count(*) from public.event_outbox
    where aggregate_id='61430000-0000-0000-0000-000000000002'
      and event_type='run.failed'),
  1::bigint,
  'expired lease exhaustion emits exactly one run.failed event'
);
select is(
  (select payload->>'reason' from public.event_outbox
    where aggregate_id='61430000-0000-0000-0000-000000000002'
      and event_type='run.failed'),
  'lease_expired',
  'expired lease event records recovery reason'
);

select * from finish();
rollback;
