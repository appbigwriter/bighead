begin;
create extension if not exists pgtap with schema extensions;
select plan(22);

insert into auth.users(id,instance_id,aud,role,email,encrypted_password,created_at,updated_at)
values('61200000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000000','authenticated','authenticated','run-worker@example.test','',now(),now());
insert into public.profiles(id,display_name) values('61200000-0000-0000-0000-000000000001','Run Worker');
insert into public.organizations(id,name,slug,created_by)
values('61210000-0000-0000-0000-000000000001','Run Worker Tenant','run-worker-tenant','61200000-0000-0000-0000-000000000001');
insert into public.organization_members(organization_id,user_id,role,status)
values('61210000-0000-0000-0000-000000000001','61200000-0000-0000-0000-000000000001','owner','active');
insert into public.tasks(id,organization_id,title,objective,requester_id)
values
 ('61220000-0000-0000-0000-000000000001','61210000-0000-0000-0000-000000000001','Recover lease','test','61200000-0000-0000-0000-000000000001'),
 ('61220000-0000-0000-0000-000000000002','61210000-0000-0000-0000-000000000001','Complete once','test','61200000-0000-0000-0000-000000000001'),
 ('61220000-0000-0000-0000-000000000003','61210000-0000-0000-0000-000000000001','Retry policy','test','61200000-0000-0000-0000-000000000001');
insert into public.runs(id,organization_id,task_id,idempotency_key,max_attempts,retry_backoff_seconds)
values
 ('61230000-0000-0000-0000-000000000001','61210000-0000-0000-0000-000000000001','61220000-0000-0000-0000-000000000001','recover-run',2,1),
 ('61230000-0000-0000-0000-000000000002','61210000-0000-0000-0000-000000000001','61220000-0000-0000-0000-000000000002','complete-run',3,1),
 ('61230000-0000-0000-0000-000000000003','61210000-0000-0000-0000-000000000001','61220000-0000-0000-0000-000000000003','retry-run',2,1);

set local role authenticated;
set local request.jwt.claim.sub='61200000-0000-0000-0000-000000000001';
select throws_ok(
  $$select * from public.claim_runs('attacker',10,60)$$,
  '42501',
  'permission denied for function claim_runs',
  'application user cannot claim runs'
);
reset role;
set local role service_role;

select is((select count(*) from public.claim_runs('worker-a',1,60)),1::bigint,'worker atomically claims one run');
select is((select count(*) from public.claim_runs('worker-b',1,60)),1::bigint,'second worker skips active lease and claims another run');
select is((select count(*) from public.runs where status='running'),2::bigint,'two workers own distinct runs');

update public.runs set locked_until=now()-interval '1 second'
 where id='61230000-0000-0000-0000-000000000002';
select throws_ok(
  $$select public.fail_run('61230000-0000-0000-0000-000000000002','worker-b','stale worker')$$,
  '55000','run_lease_lost','expired lease owner cannot fail a run'
);
update public.runs set locked_until=now()+interval '60 seconds'
 where id='61230000-0000-0000-0000-000000000002';

update public.runs set locked_until=now()-interval '1 second' where id='61230000-0000-0000-0000-000000000001';
select is((select count(*) from public.claim_runs('worker-c',1,60)),1::bigint,'expired lease is reclaimed');
select is((select attempt from public.runs where id='61230000-0000-0000-0000-000000000001'),2,'lease recovery records another attempt');
select is((select last_error from public.runs where id='61230000-0000-0000-0000-000000000001'),'worker_lease_expired','lease recovery records its cause');

select ok(public.register_run_effect('61230000-0000-0000-0000-000000000001','worker-c','effect-recover-0001','provider.call','0123456789abcdef'),'first effect reservation succeeds');
select isnt(public.register_run_effect('61230000-0000-0000-0000-000000000001','worker-c','effect-recover-0001','provider.call','0123456789abcdef'),true,'duplicate effect reservation is rejected');
select throws_ok(
  $$select public.register_run_effect('61230000-0000-0000-0000-000000000001','worker-c','effect-recover-0001','provider.call','different-fingerprint')$$,
  '23505','idempotency_conflict','same effect key rejects a different request fingerprint'
);
select is((select count(*) from private.run_effect_ledger where effect_key='effect-recover-0001'),1::bigint,'effect ledger remains exactly one row');
select is(public.fail_run('61230000-0000-0000-0000-000000000001','worker-c','timeout'),'dead_letter'::public.run_status,'retry exhaustion moves run to dead letter');

update public.runs set locked_by='worker-complete' where id='61230000-0000-0000-0000-000000000002' and status='running';
select ok(public.register_run_effect('61230000-0000-0000-0000-000000000002','worker-complete','effect-complete-0001','provider.call','fedcba9876543210'),'completion effect is reserved');
select ok(public.complete_run('61230000-0000-0000-0000-000000000002','worker-complete','effect-complete-0001','provider-event-0001',1.25,'USD'),'lease owner completes run');
select isnt(public.complete_run('61230000-0000-0000-0000-000000000002','worker-complete','effect-complete-0001','provider-event-0001',1.25,'USD'),true,'duplicate completion cannot apply twice');
select is((select count(*) from public.cost_events where provider_event_id='provider-event-0001'),1::bigint,'provider cost event is deduplicated');
select ok((select reconciled from public.reconcile_run_cost('61230000-0000-0000-0000-000000000002')),'provider and task cost ledgers reconcile');
select is((select provider_total from public.reconcile_run_cost('61230000-0000-0000-0000-000000000002')),1.25::numeric,'reconciled total preserves provider amount');

select is((select count(*) from public.claim_runs('worker-policy',10,60)),1::bigint,'remaining queued policy run is claimed');
select is(public.fail_run('61230000-0000-0000-0000-000000000003','worker-policy','timeout'),'queued'::public.run_status,'first policy failure schedules retry');
select ok((select available_at>now() from public.runs where id='61230000-0000-0000-0000-000000000003'),'retry applies positive backoff');

reset role;
select * from finish();
rollback;
