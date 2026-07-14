begin;
create extension if not exists pgtap with schema extensions;
select plan(16);

insert into public.tasks(
  id,organization_id,title,objective,requester_id
) values (
  'cc410000-0000-0000-0000-000000000001',
  'a7100000-0000-0000-0000-000000000001',
  'Scorecard history task','Preserve the original evaluation meaning',
  'd1000000-0000-0000-0000-000000000001'
);

insert into public.qa_scorecards(
  id,organization_id,name,version,criteria,pass_threshold,published_at
) values (
  'cc400000-0000-0000-0000-000000000001',
  'a7100000-0000-0000-0000-000000000001',
  'Production scorecard',1,'[{"key":"quality","weight":1}]',80,now()
);

select throws_ok(
  $$ update public.qa_scorecards set pass_threshold=90
      where id='cc400000-0000-0000-0000-000000000001' $$,
  '23514','published_scorecard_version_immutable',
  'published scorecard cannot be edited'
);

select throws_ok(
  $$ delete from public.qa_scorecards
      where id='cc400000-0000-0000-0000-000000000001' $$,
  '23514','published_scorecard_version_immutable',
  'published scorecard cannot be deleted'
);

insert into public.qa_scorecards(
  id,organization_id,name,version,criteria,pass_threshold
) values (
  'cc400000-0000-0000-0000-000000000002',
  'a7100000-0000-0000-0000-000000000001',
  'Draft scorecard',1,'[{"key":"draft","weight":1}]',70
);

select throws_ok(
  $$ insert into public.qa_evaluations(
       organization_id,task_id,scorecard_id,score,passed,results
     ) values (
       'a7100000-0000-0000-0000-000000000001',
       'cc410000-0000-0000-0000-000000000001',
       'cc400000-0000-0000-0000-000000000002',75,true,'{}'
     ) $$,
  '23514','qa_evaluation_requires_published_scorecard',
  'evaluation cannot reference a mutable draft scorecard'
);

select lives_ok(
  $$ insert into public.qa_evaluations(
       id,organization_id,task_id,scorecard_id,score,passed,results
     ) values (
       'cc420000-0000-0000-0000-000000000001',
       'a7100000-0000-0000-0000-000000000001',
       'cc410000-0000-0000-0000-000000000001',
       'cc400000-0000-0000-0000-000000000001',85,true,
       '{"quality":"passed"}'
     ) $$,
  'evaluation can reference an immutable published scorecard version'
);

select throws_ok(
  $$ update public.qa_evaluations set score=50
      where id='cc420000-0000-0000-0000-000000000001' $$,
  '23514','qa_evaluation_immutable',
  'historical evaluation cannot be edited'
);

select throws_ok(
  $$ delete from public.qa_evaluations
      where id='cc420000-0000-0000-0000-000000000001' $$,
  '23514','qa_evaluation_immutable',
  'historical evaluation cannot be deleted'
);

select lives_ok(
  $$ insert into public.qa_scorecards(
       organization_id,name,version,criteria,pass_threshold,published_at
     ) values (
       'a7100000-0000-0000-0000-000000000001','Production scorecard',2,
       '[{"key":"quality","weight":1}]',90,now()
     ) $$,
  'a new scorecard version can be published'
);

select is(
  (select count(*) from public.qa_scorecards
    where organization_id='a7100000-0000-0000-0000-000000000001'
      and name='Production scorecard'),
  2::bigint,
  'historical and current scorecard versions coexist'
);

select is(
  (select (scorecard.version::text || ':' || scorecard.pass_threshold::text)
     from public.qa_evaluations as evaluation
     join public.qa_scorecards as scorecard on scorecard.id=evaluation.scorecard_id
    where evaluation.id='cc420000-0000-0000-0000-000000000001'),
  '1:80.00',
  'evaluation remains bound to the original published scorecard version'
);

-- Other test/integration artifacts may legitimately be pending in a reused local
-- database. Keep this proof deterministic without deleting or committing them.
update public.artifacts
   set scan_available_at = now() + interval '1 day'
 where quarantine_status = 'pending'
   and id <> 'cc430000-0000-0000-0000-000000000001';

insert into public.artifacts(
  id,organization_id,name,kind,storage_bucket,storage_path,created_by,
  quarantine_status,metadata
) values (
  'cc430000-0000-0000-0000-000000000001',
  'a7100000-0000-0000-0000-000000000001','scan.pdf','upload','artifacts',
  'a7100000-0000-0000-0000-000000000001/d1000000-0000-0000-0000-000000000001/cc430000-0000-0000-0000-000000000001/scan.pdf',
  'd1000000-0000-0000-0000-000000000001','pending',
  '{"expected_mime_type":"application/pdf","expected_size_bytes":4,"expected_checksum_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'
);

select is(
  (select artifact_id from public.claim_artifact_scans('scanner-a',25,60)),
  'cc430000-0000-0000-0000-000000000001'::uuid,
  'pending artifact is atomically claimed'
);

select is(
  (select count(*) from public.claim_artifact_scans('scanner-b',25,60)),
  0::bigint,
  'active scan lease prevents duplicate claim'
);

select ok(
  public.retry_artifact_scan(
    'cc430000-0000-0000-0000-000000000001','scanner-a','scanner_unavailable'
  ),
  'transient scanner failure is scheduled for retry'
);

select ok(
  (select scan_available_at > now() and scan_locked_by is null
     from public.artifacts where id='cc430000-0000-0000-0000-000000000001'),
  'retry applies backoff and releases the lease'
);

update public.artifacts set scan_available_at=now()-interval '1 second'
 where id='cc430000-0000-0000-0000-000000000001';

select is(
  (select artifact_id from public.claim_artifact_scans('scanner-b',25,60)),
  'cc430000-0000-0000-0000-000000000001'::uuid,
  'artifact can be reclaimed after backoff'
);

select ok(
  public.complete_artifact_scan(
    'cc430000-0000-0000-0000-000000000001','scanner-b',true,
    'application/pdf',4,
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',null
  ),
  'lease owner can complete the scan exactly once'
);

select is(
  (select quarantine_status::text from public.artifacts
    where id='cc430000-0000-0000-0000-000000000001'),
  'clean',
  'completed clean scan promotes the artifact'
);

select * from finish();
rollback;
