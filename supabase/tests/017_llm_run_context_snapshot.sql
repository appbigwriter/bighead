begin;
create extension if not exists pgtap with schema extensions;
select plan(9);

insert into auth.users(id,instance_id,aud,role,email,encrypted_password,created_at,updated_at)
values('61700000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000000','authenticated','authenticated','llm-snapshot@example.test','',now(),now());
insert into public.profiles(id,display_name)
values('61700000-0000-0000-0000-000000000001','LLM Snapshot');
insert into public.organizations(id,name,slug,created_by)
values('61710000-0000-0000-0000-000000000001','LLM Snapshot Tenant','llm-snapshot-tenant','61700000-0000-0000-0000-000000000001');
insert into public.organization_members(organization_id,user_id,role,status)
values('61710000-0000-0000-0000-000000000001','61700000-0000-0000-0000-000000000001','owner','active');
insert into public.model_providers(id,organization_id,name,provider_key)
values('61720000-0000-0000-0000-000000000001','61710000-0000-0000-0000-000000000001','OpenAI','openai');
insert into public.models(
  id,organization_id,provider_id,model_key,input_cost_per_million,output_cost_per_million
) values (
  '61730000-0000-0000-0000-000000000001','61710000-0000-0000-0000-000000000001',
  '61720000-0000-0000-0000-000000000001','gpt-pinned',5,15
);
insert into public.agents(id,organization_id,name,slug)
values('61740000-0000-0000-0000-000000000001','61710000-0000-0000-0000-000000000001','Pinned agent','pinned-agent');
insert into public.agent_versions(
  id,organization_id,agent_id,version,model_id,system_prompt,configuration,published_at
) values (
  '61750000-0000-0000-0000-000000000001','61710000-0000-0000-0000-000000000001',
  '61740000-0000-0000-0000-000000000001',1,'61730000-0000-0000-0000-000000000001',
  'Pinned prompt v1','{"outputSchema":{"type":"object","properties":{"v1":{"type":"string"}},"required":["v1"]}}',now()
);
insert into public.tasks(id,organization_id,title,objective,agent_id,requester_id)
values(
  '61760000-0000-0000-0000-000000000001','61710000-0000-0000-0000-000000000001',
  'Pinned run','Retry exactly','61740000-0000-0000-0000-000000000001',
  '61700000-0000-0000-0000-000000000001'
);
insert into public.runs(
  id,organization_id,task_id,idempotency_key,max_attempts,retry_backoff_seconds,
  available_at,created_at
) values (
  '61770000-0000-0000-0000-000000000001','61710000-0000-0000-0000-000000000001',
  '61760000-0000-0000-0000-000000000001','llm-snapshot-run',3,10,
  '1900-01-01T00:00:00Z','1900-01-01T00:00:00Z'
);

update public.runs set available_at=now()+interval '1 day'
 where id<>'61770000-0000-0000-0000-000000000001' and status in ('queued','waiting');
update public.runs set locked_until=now()+interval '1 day'
 where id<>'61770000-0000-0000-0000-000000000001' and status='running';

set local role authenticated;
set local request.jwt.claim.sub='61700000-0000-0000-0000-000000000001';
select throws_ok(
  $$select * from private.snapshot_run_llm_context('61770000-0000-0000-0000-000000000001')$$,
  '42501','permission denied for function snapshot_run_llm_context',
  'application users cannot create or read execution snapshots'
);
reset role;

create temp table first_claim as
select * from public.claim_llm_runs('unused',1,60) with no data;
create temp table retry_claim as select * from first_claim with no data;
grant select,insert on first_claim,retry_claim to service_role;
set local role service_role;
insert into first_claim select * from public.claim_llm_runs('snapshot-worker',1,60);
select is((select count(*) from first_claim),1::bigint,'first claim creates one snapshot');
select is(
  (select agent_version_id from first_claim),'61750000-0000-0000-0000-000000000001'::uuid,
  'first claim pins published agent version v1'
);
reset role;

insert into public.agent_versions(
  id,organization_id,agent_id,version,model_id,system_prompt,configuration,published_at
) values (
  '61750000-0000-0000-0000-000000000002','61710000-0000-0000-0000-000000000001',
  '61740000-0000-0000-0000-000000000001',2,'61730000-0000-0000-0000-000000000001',
  'Mutable prompt v2','{"outputSchema":{"type":"object","properties":{"v2":{"type":"string"}},"required":["v2"]}}',now()+interval '1 second'
);
update public.models
   set input_cost_per_million=50,output_cost_per_million=150
 where id='61730000-0000-0000-0000-000000000001';
update public.runs set locked_until=now()-interval '1 second'
 where id='61770000-0000-0000-0000-000000000001';

set local role service_role;
insert into retry_claim select * from public.claim_llm_runs('snapshot-worker-retry',1,60);
select is((select attempt from retry_claim),2,'expired lease is reclaimed as retry');
select is(
  (select agent_version_id from retry_claim),'61750000-0000-0000-0000-000000000001'::uuid,
  'retry keeps pinned agent version despite later publication'
);
select is(
  (select system_prompt from retry_claim),'Pinned prompt v1',
  'retry keeps pinned system prompt'
);
select ok(
  (select (output_schema -> 'properties') ? 'v1' and not ((output_schema -> 'properties') ? 'v2') from retry_claim),
  'retry keeps pinned output schema'
);
select is(
  (select model_prices #>> '{gpt-pinned,inputCostPerMillion}' from retry_claim),'5.000000',
  'retry keeps pinned price table'
);
select is(
  (select count(*) from private.run_llm_context
    where run_id='61770000-0000-0000-0000-000000000001'),1::bigint,
  'one immutable snapshot exists per run'
);

reset role;
select * from finish();
rollback;
