begin;
create extension if not exists pgtap with schema extensions;
select plan(7);

select has_trigger('public','agent_versions','agent_versions_protect_published',
  'published agent versions have an immutability trigger');
select is((select count(*) from pg_policy where polrelid='public.agents'::regclass
  and polname='agents_manage_delete'),0::bigint,
  'authenticated users cannot hard-delete agents through the Data API');
select is((select count(*) from pg_policy where polrelid='public.agent_versions'::regclass
  and polname in ('agent_versions_manage_insert','agent_versions_manage_update','agent_versions_manage_delete')),
  0::bigint,'authenticated users cannot mutate agent versions directly');

insert into public.agents(id,organization_id,name,slug,owner_user_id)
values('ce100000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001',
  'Lifecycle proof','lifecycle-proof','d1000000-0000-0000-0000-000000000001');
insert into public.agent_versions(id,organization_id,agent_id,version,system_prompt,published_at,created_by)
values('ce110000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001',
  'ce100000-0000-0000-0000-000000000001',1,'immutable prompt',now(),
  'd1000000-0000-0000-0000-000000000001');
select throws_ok(
  $$ update public.agent_versions set system_prompt='tampered'
     where id='ce110000-0000-0000-0000-000000000001' $$,
  '23514','published_agent_version_immutable',
  'published agent version cannot be changed in place');
select is((select count(*) from public.agent_versions
  where id='ce110000-0000-0000-0000-000000000001' and system_prompt='immutable prompt'),
  1::bigint,'published prompt remains unchanged after rejected update');
select throws_ok(
  $$ delete from public.agent_versions
     where id='ce110000-0000-0000-0000-000000000001' $$,
  '23514','published_agent_version_immutable',
  'published agent version cannot be deleted');
select is((select count(*) from public.agent_versions
  where id='ce110000-0000-0000-0000-000000000001' and published_at is not null),
  1::bigint,'published agent version remains after rejected delete');

select * from finish();
rollback;
