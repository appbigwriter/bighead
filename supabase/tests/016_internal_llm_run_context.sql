begin;
create extension if not exists pgtap with schema extensions;
select plan(14);

insert into auth.users(id,instance_id,aud,role,email,encrypted_password,created_at,updated_at)
values('61600000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000000','authenticated','authenticated','llm-run@example.test','',now(),now());
insert into public.profiles(id,display_name)
values('61600000-0000-0000-0000-000000000001','LLM Run');
insert into public.organizations(id,name,slug,created_by)
values('61610000-0000-0000-0000-000000000001','LLM Run Tenant','llm-run-tenant','61600000-0000-0000-0000-000000000001');
insert into public.organization_members(organization_id,user_id,role,status)
values('61610000-0000-0000-0000-000000000001','61600000-0000-0000-0000-000000000001','owner','active');
insert into public.model_providers(id,organization_id,name,provider_key)
values('61620000-0000-0000-0000-000000000001','61610000-0000-0000-0000-000000000001','OpenAI','openai');
insert into public.models(
  id,organization_id,provider_id,model_key,input_cost_per_million,output_cost_per_million
) values (
  '61630000-0000-0000-0000-000000000001','61610000-0000-0000-0000-000000000001',
  '61620000-0000-0000-0000-000000000001','gpt-priced',5,15
);
insert into public.agents(id,organization_id,name,slug)
values('61640000-0000-0000-0000-000000000001','61610000-0000-0000-0000-000000000001','SDR','sdr');
insert into public.agent_versions(
  id,organization_id,agent_id,version,model_id,system_prompt,configuration,published_at
) values (
  '61650000-0000-0000-0000-000000000001','61610000-0000-0000-0000-000000000001',
  '61640000-0000-0000-0000-000000000001',1,'61630000-0000-0000-0000-000000000001',
  'Return structured JSON.','{"outputSchema":{"type":"object","properties":{"answer":{"type":"string"}},"required":["answer"]}}',now()
);
insert into public.tasks(
  id,organization_id,title,objective,agent_id,metadata,requester_id
) values (
  '61660000-0000-0000-0000-000000000001','61610000-0000-0000-0000-000000000001',
  'Qualify lead','Recommend next action','61640000-0000-0000-0000-000000000001',
  '{"source":"crm","apiKey":"must-not-leak","nested":{"accessToken":"also-secret"}}',
  '61600000-0000-0000-0000-000000000001'
);
insert into public.runs(
  id,organization_id,task_id,idempotency_key,max_attempts,retry_backoff_seconds
) values (
  '61670000-0000-0000-0000-000000000001','61610000-0000-0000-0000-000000000001',
  '61660000-0000-0000-0000-000000000001','llm-context-run',3,10
);
insert into public.tasks(id,organization_id,title,objective,requester_id)
values(
  '61660000-0000-0000-0000-000000000002','61610000-0000-0000-0000-000000000001',
  'Missing agent context','Must fail closed','61600000-0000-0000-0000-000000000001'
);
insert into public.runs(
  id,organization_id,task_id,idempotency_key,max_attempts,retry_backoff_seconds
) values (
  '61670000-0000-0000-0000-000000000002','61610000-0000-0000-0000-000000000001',
  '61660000-0000-0000-0000-000000000002','llm-invalid-context-run',3,10
);

set local role authenticated;
set local request.jwt.claim.sub='61600000-0000-0000-0000-000000000001';
select throws_ok(
  $$select * from public.claim_llm_runs('attacker',10,60)$$,
  '42501',
  'permission denied for function claim_llm_runs',
  'application users cannot claim enriched LLM runs'
);
reset role;

create temp table claimed_llm as
select * from public.claim_llm_runs('unused',1,60) with no data;
grant select, insert on claimed_llm to service_role;
set local role service_role;
insert into claimed_llm select * from public.claim_llm_runs('llm-worker',1,60);

select is((select count(*) from claimed_llm),1::bigint,'service worker claims one enriched run');
select is((select task_title from claimed_llm),'Qualify lead','claim includes tenant task title');
select is(
  (select task_metadata #>> '{apiKey}' from claimed_llm),'[REDACTED]',
  'claim redacts top-level secrets'
);
select is(
  (select task_metadata #>> '{nested,accessToken}' from claimed_llm),'[REDACTED]',
  'claim recursively redacts nested secrets'
);
select is(
  (select output_schema ->> 'type' from claimed_llm),'object',
  'claim resolves the published agent output schema'
);
select is(
  (select agent_version_id from claimed_llm),'61650000-0000-0000-0000-000000000001'::uuid,
  'claim selects the latest published tenant agent version'
);
select is(
  (select model_prices #>> '{gpt-priced,inputCostPerMillion}' from claimed_llm),'5.000000',
  'claim returns the tenant model price without provider credentials'
);

select ok(public.register_run_effect(
  '61670000-0000-0000-0000-000000000001','llm-worker','run:6167:primary',
  'provider.call','0123456789abcdef'
),'LLM effect is reserved');
select ok(public.complete_llm_run(
  '61670000-0000-0000-0000-000000000001','llm-worker','run:6167:primary',
  'llm:openai:response-1',0.0175,'USD',2000,500,
  '61630000-0000-0000-0000-000000000001'
),'LLM completion is atomic');
select ok((
  select input_tokens=2000 and output_tokens=500
    and amount=0.0175 and model_id='61630000-0000-0000-0000-000000000001'::uuid
  from public.cost_events
  where provider_event_id='llm:openai:response-1'
),'LLM completion persists tokens, price-derived cost and tenant model');

create temp table invalid_llm as
select * from claimed_llm with no data;
grant select, insert on invalid_llm to service_role;
insert into invalid_llm select * from public.claim_llm_runs('llm-worker',1,60);
select is(
  (select count(*) from invalid_llm),1::bigint,
  'a claimed run with missing execution context is never dropped by the RPC'
);
select is(
  (select task_title from invalid_llm),'Missing agent context',
  'invalid claim still carries task context for explicit worker failure'
);
select is(
  (select agent_id from invalid_llm),null::uuid,
  'invalid claim exposes missing agent so the executor fails closed'
);

reset role;
select * from finish();
rollback;
