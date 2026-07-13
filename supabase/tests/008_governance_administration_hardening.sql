begin;
create extension if not exists pgtap with schema extensions;
select plan(12);

select has_column('public','approval_decisions','idempotency_key',
  'external approval decisions carry an idempotency key');
select has_index('public','approval_decisions','approval_decisions_tenant_idempotency_key_idx',
  'external approval idempotency is enforced in Postgres');
select has_table('private','portal_access_events','portal rate limits are private');
select matches(
  (select pg_get_functiondef('private.protect_last_owner()'::regprocedure)),
  'pg_advisory_xact_lock', 'last owner changes serialize per tenant');
select matches(
  (select pg_get_expr(polwithcheck,polrelid) from pg_policy
    where polrelid='public.approval_decisions'::regclass
      and polname='approval_decisions_insert_reviewer'),
  'requested_by', 'Data API approval decisions enforce segregation of duties');

insert into public.agents(id,organization_id,name,slug,owner_user_id)
values('cc100000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001',
  'Governance hardening','governance-hardening','d1000000-0000-0000-0000-000000000001');
insert into public.workflows(id,organization_id,name,slug,owner_user_id)
values('cc200000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001',
  'Governance workflow','governance-workflow','d1000000-0000-0000-0000-000000000001');
insert into public.workflow_versions(id,organization_id,workflow_id,version,definition,created_by)
values('cc210000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001',
  'cc200000-0000-0000-0000-000000000001',1,'{}','d1000000-0000-0000-0000-000000000001');
insert into public.experiments(id,organization_id,name,hypothesis,status,primary_metric)
values('cc300000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001',
  'Locked experiment','Original hypothesis','draft','conversion');
insert into public.experiment_variants(id,organization_id,experiment_id,name,weight)
values('cc310000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001',
  'cc300000-0000-0000-0000-000000000001','A',1);
update public.experiments set status='running'
where id='cc300000-0000-0000-0000-000000000001';

set local role authenticated;
set local request.jwt.claim.sub='d1000000-0000-0000-0000-000000000003';
select is((select count(*) from public.agents where id='cc100000-0000-0000-0000-000000000001'),0::bigint,
  'manager cannot read admin agent catalog through Data API');
select is((select count(*) from public.workflows where id='cc200000-0000-0000-0000-000000000001'),1::bigint,
  'manager retains T31 workflow list access');
select is((select count(*) from public.workflow_versions where id='cc210000-0000-0000-0000-000000000001'),0::bigint,
  'manager cannot read T33 workflow versions through Data API');
set local request.jwt.claim.sub='d1000000-0000-0000-0000-000000000002';
select is((select count(*) from public.agents where id='cc100000-0000-0000-0000-000000000001'),1::bigint,
  'admin reads the agent catalog');
set local request.jwt.claim.sub='d1000000-0000-0000-0000-000000000006';
select throws_ok(
  $$ update public.experiments set hypothesis='tampered' where id='cc300000-0000-0000-0000-000000000001' $$,
  '23514','running_experiment_configuration_immutable',
  'running experiment hypothesis is immutable');
select throws_ok(
  $$ update public.experiment_variants set weight=0.5 where id='cc310000-0000-0000-0000-000000000001' $$,
  '23514','running_experiment_variants_immutable',
  'running experiment variants are immutable');
select throws_ok(
  $$ insert into public.experiment_variants(organization_id,experiment_id,name,weight)
     values('a7100000-0000-0000-0000-000000000001','cc300000-0000-0000-0000-000000000001','B',0.5) $$,
  '23514','running_experiment_variants_immutable',
  'running experiment rejects new variants');

select * from finish();
rollback;
