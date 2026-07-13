begin;
create extension if not exists pgtap with schema extensions;
select plan(25);

select has_table('private','embedding_profiles','embedding profiles are controlled privately');
select has_table('private','embedding_reindex_runs','embedding reindex runs are durable');
select has_table('private','embedding_reindex_items','embedding migration stages every row');
select has_table('public','crm_imports','CRM imports have a durable aggregate report');
select has_table('public','crm_import_rows','CRM imports report every row');
select has_column('public','leads','score_algorithm_version','lead score records algorithm version');
select has_column('public','crm_accounts','merged_into_id','merged source account is retained as a tombstone');
select has_index('public','crm_import_rows','crm_import_rows_resume_idx','failed CRM rows have a resumable access path');

insert into public.knowledge_documents(
  id,organization_id,title,source_type,review_status
) values (
  'b7110000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001',
  'Controlled embedding test','text','approved'
);
insert into public.knowledge_chunks(
  id,organization_id,document_id,ordinal,content,embedding
) values (
  'b7120000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001',
  'b7110000-0000-0000-0000-000000000001',0,'legacy embedding',
  ('[' || array_to_string(array_fill(0::real,array[1536]),',') || ']')::extensions.vector
);

select is(
  (select p.dimensions from public.knowledge_chunks c
    join private.embedding_profiles p on p.id=c.embedding_profile_id
   where c.id='b7120000-0000-0000-0000-000000000001'),
  1536,
  'new embeddings are bound to the active profile'
);

create temporary table test_reindex(run_id uuid);
insert into test_reindex
select private.start_embedding_reindex('test-provider','test-3d',3,null);

select is(
  (select dimensions from private.embedding_profiles where status='active'),
  1536,
  'starting a reindex leaves the operational profile active'
);
select throws_ok(
  $$select private.complete_embedding_reindex_item(
      (select run_id from test_reindex),'knowledge_chunk',
      'b7120000-0000-0000-0000-000000000001','[1,0]'::extensions.vector)$$,
  '22023','embedding_dimension_mismatch','dimension mismatch is rejected'
);

do $complete$
declare item record;
begin
  for item in
    select entity_type,entity_id from private.embedding_reindex_items
    where run_id=(select run_id from test_reindex)
  loop
    perform private.complete_embedding_reindex_item(
      (select run_id from test_reindex),item.entity_type,item.entity_id,
      '[1,0,0]'::extensions.vector
    );
  end loop;
end
$complete$;

select is(
  (select status from private.embedding_reindex_runs where id=(select run_id from test_reindex)),
  'ready',
  'run becomes ready only after every row has a target embedding'
);
do $build_test_indexes$
declare command record;
begin
  for command in
    select ddl from private.embedding_reindex_index_commands((select run_id from test_reindex))
  loop
    execute replace(command.ddl,'create index concurrently','create index');
  end loop;
end
$build_test_indexes$;
select lives_ok(
  $$select private.activate_embedding_reindex((select run_id from test_reindex))$$,
  'ready embedding migration activates atomically'
);
select is(
  (select dimensions from private.embedding_profiles where status='active'),
  3,
  'activation changes the active dimension'
);
select is(
  (select extensions.vector_dims(embedding) from public.knowledge_chunks
    where id='b7120000-0000-0000-0000-000000000001'),
  3,
  'activation swaps staged embeddings into operational rows'
);
select ok(
  exists(select 1 from pg_indexes where schemaname='public'
    and tablename='knowledge_chunks' and indexname like 'knowledge_chunks_embedding_%_hnsw_idx'
    and indexdef like '%embedding_profile_id%'),
  'activation creates a profile-specific HNSW index'
);

insert into public.crm_imports(
  id,organization_id,source,consent_basis,idempotency_key,fingerprint,status,total_rows,
  accepted_rows,failed_rows
) values (
  'b7200000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001',
  'pgtap','contract','pgtap-resume','fingerprint','partial',2,1,1
);
insert into public.crm_import_rows(
  import_id,organization_id,row_number,payload,status,attempts,error_code,error_detail
) values
  ('b7200000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001',0,
   '{"accountName":"Accepted"}','accepted',1,null,null),
  ('b7200000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001',1,
   '{"accountName":"Retry"}','failed',1,'transient','provider unavailable');
select is(
  (select count(*)::integer from public.crm_import_rows
    where import_id='b7200000-0000-0000-0000-000000000001'),
  2,
  'partial import retains one report per input row'
);

select throws_ok(
  $$insert into public.leads(organization_id,status,icp_score,score_factors)
    values('a7100000-0000-0000-0000-000000000001','new',80,'{"fit":0.8}')$$,
  '23514',null,'scored lead without algorithm version is rejected'
);
select lives_ok(
  $$insert into public.leads(id,organization_id,status,icp_score,score_factors,score_algorithm_version)
    values('b7300000-0000-0000-0000-000000000001',
      'a7100000-0000-0000-0000-000000000001','new',80,
      '{"fit":{"weight":0.6,"contribution":48},"intent":{"weight":0.4,"contribution":32}}',
      'icp-v2.1')$$,
  'explainable scored lead records factors and version'
);

insert into public.crm_accounts(id,organization_id,name,domain) values
 ('b7400000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001','Duplicate','duplicate.invalid'),
 ('b7400000-0000-0000-0000-000000000002','a7100000-0000-0000-0000-000000000001','Canonical','canonical.invalid');
insert into public.crm_contacts(id,organization_id,account_id,name,consent_status)
values('b7410000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001',
  'b7400000-0000-0000-0000-000000000001','Contact','unknown');
update public.leads set account_id='b7400000-0000-0000-0000-000000000001'
 where id='b7300000-0000-0000-0000-000000000001';
insert into public.opportunities(id,organization_id,account_id,name,stage)
values('b7420000-0000-0000-0000-000000000001','a7100000-0000-0000-0000-000000000001',
  'b7400000-0000-0000-0000-000000000001','Merge opportunity','discovery');

select lives_ok(
  $$select private.merge_crm_accounts(
    'a7100000-0000-0000-0000-000000000001','b7400000-0000-0000-0000-000000000001',
    'b7400000-0000-0000-0000-000000000002','d1000000-0000-0000-0000-000000000001','same legal entity')$$,
  'account merge succeeds in one transaction'
);
select is(
  (select merged_into_id from public.crm_accounts where id='b7400000-0000-0000-0000-000000000001'),
  'b7400000-0000-0000-0000-000000000002'::uuid,
  'source account is preserved as a tombstone'
);
select is(
  (select account_id from public.crm_contacts where id='b7410000-0000-0000-0000-000000000001'),
  'b7400000-0000-0000-0000-000000000002'::uuid,
  'contact reference moves to canonical account'
);
select is(
  (select account_id from public.leads where id='b7300000-0000-0000-0000-000000000001'),
  'b7400000-0000-0000-0000-000000000002'::uuid,
  'lead reference moves to canonical account'
);
select is(
  (select account_id from public.opportunities where id='b7420000-0000-0000-0000-000000000001'),
  'b7400000-0000-0000-0000-000000000002'::uuid,
  'opportunity reference moves to canonical account'
);
select is(
  (select count(*)::integer from public.audit_log
    where resource_id='b7400000-0000-0000-0000-000000000001' and action='crm.account.merged'),
  1,
  'merge appends exactly one audit event'
);

select * from finish();
rollback;
