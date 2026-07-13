create extension if not exists pgtap with schema extensions;
begin;
select plan(22);

select has_table('public','crm_connections','CRM connections exist');
select has_table('public','crm_sync_cursors','CRM cursors exist');
select has_table('public','crm_external_links','CRM external links exist');
select has_table('public','crm_webhook_inbox','CRM webhook inbox exists');
select has_table('public','crm_effect_ledger','CRM effect ledger exists');
select has_table('public','crm_sync_jobs','CRM durable sync jobs exist');
select ok((select relrowsecurity from pg_class where oid='public.crm_effect_ledger'::regclass), 'effect ledger has RLS');
select ok(not has_table_privilege('authenticated','public.crm_effect_ledger','INSERT'), 'browser cannot forge effect ledger rows');
select ok(not has_table_privilege('anon','public.crm_connections','SELECT'), 'anonymous cannot enumerate CRM connections');
select has_function('public','claim_crm_sync_jobs',array['text','integer','integer'],'CRM job claim RPC exists');

insert into auth.users(id,instance_id,aud,role,email,encrypted_password,created_at,updated_at) values
 ('51000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000000','authenticated','authenticated','crm-a@example.test','',now(),now()),
 ('52000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000000','authenticated','authenticated','crm-b@example.test','',now(),now());
insert into public.profiles(id,display_name) values
 ('51000000-0000-0000-0000-000000000001','CRM A'),('52000000-0000-0000-0000-000000000002','CRM B');
insert into public.organizations(id,name,slug,created_by) values
 ('5a000000-0000-0000-0000-000000000001','CRM Tenant A','crm-tenant-a','51000000-0000-0000-0000-000000000001'),
 ('5b000000-0000-0000-0000-000000000002','CRM Tenant B','crm-tenant-b','52000000-0000-0000-0000-000000000002');
insert into public.organization_members(organization_id,user_id,role,status) values
 ('5a000000-0000-0000-0000-000000000001','51000000-0000-0000-0000-000000000001','owner','active'),
 ('5b000000-0000-0000-0000-000000000002','52000000-0000-0000-0000-000000000002','owner','active');
insert into public.crm_connections(id,organization_id,provider_key,display_name,secret_ref,created_by) values
 ('5c000000-0000-0000-0000-000000000001','5a000000-0000-0000-0000-000000000001','hubspot','A','env://CRM_SECRET_TENANT_A','51000000-0000-0000-0000-000000000001'),
 ('5c000000-0000-0000-0000-000000000002','5b000000-0000-0000-0000-000000000002','hubspot','B','env://CRM_SECRET_TENANT_B','52000000-0000-0000-0000-000000000002');

set local role authenticated;
set local request.jwt.claim.sub='51000000-0000-0000-0000-000000000001';
select is((select count(*) from public.crm_connections),1::bigint,'CRM RLS hides cross-tenant connections');
reset role;

insert into public.crm_sync_jobs(id,organization_id,connection_id,status,attempts,locked_by,locked_until) values
 ('5d000000-0000-0000-0000-000000000001','5a000000-0000-0000-0000-000000000001','5c000000-0000-0000-0000-000000000001','running',7,'dead-worker',now()-interval '1 minute');
set local role service_role;
set local request.jwt.claims='{"role":"service_role"}';
create temp table claimed_crm_job on commit drop as
 select * from public.claim_crm_sync_jobs('reclaimer',1,60);
select is(
 (select id from claimed_crm_job),
 '5d000000-0000-0000-0000-000000000001'::uuid,
 'expired running CRM job is reclaimed');
select is(public.ack_crm_sync_job('5d000000-0000-0000-0000-000000000001','reclaimer','00000000-0000-0000-0000-000000000000'),false,'stale lease token cannot ack reclaimed job');
select ok(public.nack_crm_sync_job(
 '5d000000-0000-0000-0000-000000000001','reclaimer',
 (select lease_token from claimed_crm_job),
 'HTTPStatusError',8),'reclaimed job can be nacked');
reset role;
select is((select status from public.crm_sync_jobs where id='5d000000-0000-0000-0000-000000000001'),'dead_letter'::text,'attempt limit moves CRM job to DLQ');
select is((select last_error from public.crm_sync_jobs where id='5d000000-0000-0000-0000-000000000001'),'HTTPStatusError'::text,'DLQ error is sanitized');

set local role service_role;
set local request.jwt.claims='{"role":"service_role"}';
select is(public.apply_crm_sync_page(
 '5c000000-0000-0000-0000-000000000001',
 '[{"entityType":"account","externalId":"acct-1","updatedAt":"2026-07-13T18:00:00Z","fields":{"name":"Acme"}}]'::jsonb,
 null,'2026-07-13T18:00:00Z',0),1::bigint,'first CRM page advances cursor');
select throws_ok(
 $$select public.apply_crm_sync_page('5c000000-0000-0000-0000-000000000001','[]'::jsonb,null,null,0)$$,
 '40001','crm_cursor_version_conflict','stale CRM cursor is rejected');
select is(public.apply_crm_sync_page(
 '5c000000-0000-0000-0000-000000000001',
 '[{"entityType":"account","externalId":"acct-1","updatedAt":"2026-07-13T18:00:00Z","fields":{"name":"Acme"}}]'::jsonb,
 null,'2026-07-13T18:00:00Z',1),2::bigint,'replayed CRM page is idempotent');
select throws_ok(
 $$select public.apply_crm_sync_page(
   '5c000000-0000-0000-0000-000000000001',
   '[{"entityType":"account","externalId":"acct-1","updatedAt":"2026-07-12T18:00:00Z","fields":{"name":"Stale"}}]'::jsonb,
   null,'2026-07-12T18:00:00Z',2)$$,
 '40001','crm_page_older_than_watermark','older provider page cannot regress CRM state');
reset role;
select is((select count(*) from public.crm_external_links where connection_id='5c000000-0000-0000-0000-000000000001'),1::bigint,'mapping replay creates one external link');
select is((select name from public.crm_accounts where id=(select local_id from public.crm_external_links where external_id='acct-1')),'Acme'::text,'older updatedAt does not overwrite mapped entity');

select * from finish();
rollback;
