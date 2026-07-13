begin;
select plan(29);

select has_table('private','webhook_deliveries','webhook delivery ledger exists');
select has_table('private','privacy_requests','privacy request lifecycle exists');
select has_table('private','legal_holds','legal hold registry exists');
select has_table('private','retention_policies','retention policy registry exists');
select has_function(
  'public','claim_webhook_deliveries',array['text','integer','integer'],
  'service worker can atomically lease deliveries');
select ok(not has_function_privilege(
  'authenticated','public.claim_webhook_deliveries(text,integer,integer)','execute'),
  'application users cannot claim webhook deliveries');
select ok(not has_function_privilege(
  'authenticated','public.resolve_webhook_secret(text)','execute'),
  'application users cannot resolve webhook secrets');
select has_function('public','claim_privacy_requests',array['text','integer','integer'],
  'privacy worker can atomically lease jobs');
select ok(not has_function_privilege(
  'authenticated','public.claim_privacy_requests(text,integer,integer)','execute'),
  'application users cannot claim privacy jobs');

insert into public.webhook_endpoints(
  id,organization_id,url,event_types,secret_reference,is_enabled
) values (
  'ed900000-0000-0000-0000-000000000001',
  'a7100000-0000-0000-0000-000000000001',
  'https://hooks.example.test/events',array['worker.test'],'vault/worker-test',true
);
insert into public.event_outbox(
  id,organization_id,event_type,aggregate_type,aggregate_id,payload
) values (
  'ed900000-0000-0000-0000-000000000002',
  'a7100000-0000-0000-0000-000000000001','worker.test','task',
  'ed900000-0000-0000-0000-000000000003','{"ok":true}'
);
insert into public.event_outbox(
  id,organization_id,event_type,aggregate_type,aggregate_id,payload,created_at
) values (
  'ed900000-0000-0000-0000-000000000007',
  'a7100000-0000-0000-0000-000000000001','worker.test','task',
  'ed900000-0000-0000-0000-000000000008','{"old":true}',now()-interval '1 day'
);

select is(
  (select count(*) from public.claim_webhook_deliveries('worker-a',10,30)),1::bigint,
  'matching outbox event creates and leases one delivery');
select is(
  (select count(*) from public.claim_webhook_deliveries('worker-b',10,30)),0::bigint,
  'active delivery lease prevents concurrent duplicate');
select is(public.ack_webhook_delivery(
  'ed900000-0000-0000-0000-000000000004','worker-a',204,repeat('a',64)),false,
  'unknown delivery cannot be acknowledged');
select is((select count(*) from private.webhook_deliveries),1::bigint,
  'endpoint and event uniqueness prevents duplicate delivery effects');
update private.webhook_deliveries set locked_until=now()-interval '1 second'
where status='delivering';
select is((select count(*) from public.claim_webhook_deliveries('worker-crash',10,30)),1::bigint,
  'expired delivering webhook lease is recovered');
select is((select attempts from private.webhook_deliveries limit 1),2,
  'recovered webhook delivery increments attempts exactly once');
select is((select count(*) from private.webhook_deliveries where event_id=
  'ed900000-0000-0000-0000-000000000007'),0::bigint,
  'webhook registration does not backfill historical events');

insert into public.experiments(
  id,organization_id,name,hypothesis,status,primary_metric
) values (
  'ed900000-0000-0000-0000-000000000009',
  'a7100000-0000-0000-0000-000000000001','No downgrade','immutable','running','rate'
);
select throws_ok(
  $$update public.experiments set status='draft'
    where id='ed900000-0000-0000-0000-000000000009'$$,
  '23514','experiment_cannot_return_to_draft',
  'started experiment cannot downgrade to draft');

insert into private.legal_holds(
  id,organization_id,subject_user_id,reason,created_by
) values (
  'ed900000-0000-0000-0000-000000000005',
  'a7100000-0000-0000-0000-000000000001',
  'd1000000-0000-0000-0000-000000000004','litigation',
  'd1000000-0000-0000-0000-000000000001'
);
insert into private.privacy_requests(
  id,organization_id,subject_user_id,request_type,idempotency_key,requested_by
) values (
  'ed900000-0000-0000-0000-000000000006',
  'a7100000-0000-0000-0000-000000000001',
  'd1000000-0000-0000-0000-000000000004','delete','privacy-worker-test',
  'd1000000-0000-0000-0000-000000000001'
);
select is((select status from private.privacy_requests where id=
  'ed900000-0000-0000-0000-000000000006'),'requested',
  'privacy request starts with explicit lifecycle state');
select is((select count(*) from public.claim_privacy_requests('privacy-a',10,60)),0::bigint,
  'legal hold prevents destructive privacy job from being leased');
select is((select status from private.privacy_requests where id=
  'ed900000-0000-0000-0000-000000000006'),'blocked',
  'legal hold is recorded as an explicit blocked lifecycle state');
insert into private.privacy_requests(
  id,organization_id,subject_user_id,request_type,idempotency_key,requested_by
) values (
  'ed900000-0000-0000-0000-000000000010',
  'a7100000-0000-0000-0000-000000000001',
  'd1000000-0000-0000-0000-000000000004','export','privacy-export-worker-test',
  'd1000000-0000-0000-0000-000000000001'
);
select is((select count(*) from public.claim_privacy_requests('privacy-a',10,60)),1::bigint,
  'export job is leased even while destructive processing is held');
select is(public.complete_privacy_request(
  'ed900000-0000-0000-0000-000000000010','privacy-a','{"exportPath":"proof.json"}'),true,
  'leased privacy job completes with evidence');
select is((select status from private.privacy_requests where id=
  'ed900000-0000-0000-0000-000000000010'),'completed',
  'privacy lifecycle persists terminal completion');
insert into private.privacy_requests(
  id,organization_id,subject_user_id,request_type,idempotency_key,requested_by
) values (
  'ed900000-0000-0000-0000-000000000011',
  'b7200000-0000-0000-0000-000000000001',
  'd1000000-0000-0000-0000-000000000004','anonymize','privacy-cross-tenant-hold',
  'd2000000-0000-0000-0000-000000000001'
);
select is((select count(*) from public.claim_privacy_requests('privacy-b',10,60)),1::bigint,
  'legal hold in another tenant does not block a privacy request');
update private.privacy_requests set locked_until=now()-interval '1 second'
where id='ed900000-0000-0000-0000-000000000011';
select is((select count(*) from public.claim_privacy_requests('privacy-c',10,60)),1::bigint,
  'expired processing privacy lease is recovered');
select is((select attempts from private.privacy_requests where id=
  'ed900000-0000-0000-0000-000000000011'),2,
  'recovered privacy job increments attempts exactly once');
select throws_ok(
  $$insert into private.privacy_requests(
      organization_id,subject_user_id,request_type,idempotency_key,requested_by)
    values ('a7100000-0000-0000-0000-000000000001',
      'd1000000-0000-0000-0000-000000000004','delete','privacy-worker-test',
      'd1000000-0000-0000-0000-000000000001')$$,
  '23505',null,'privacy request idempotency is tenant scoped');

update public.organizations set settings=jsonb_set(
  settings,'{budgets}','{"limit":"1","exceededAction":"block"}',true)
where id='a7100000-0000-0000-0000-000000000001';
insert into public.cost_events(organization_id,provider_event_id,amount)
values('a7100000-0000-0000-0000-000000000001','budget-worker-test',2);
select throws_ok(
  $$insert into public.tasks(organization_id,title,objective,requester_id)
    values ('a7100000-0000-0000-0000-000000000001','blocked','budget guard',
      'd1000000-0000-0000-0000-000000000001')$$,
  'P0001','tenant_budget_exceeded','budget block is enforced before accepting work');

select is(
  (select count(*) from information_schema.tables where table_schema='public'),48::bigint,
  'only the two reviewed CRM report tables expand the public Data API surface');

select * from finish();
rollback;
