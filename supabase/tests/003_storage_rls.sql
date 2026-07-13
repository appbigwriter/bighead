begin;
create extension if not exists pgtap with schema extensions;
select plan(17);

insert into auth.users (id, instance_id, aud, role, email, encrypted_password, created_at, updated_at)
values
  ('31000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'storage-a@example.test', '', now(), now()),
  ('32000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'storage-b@example.test', '', now(), now());
insert into public.organizations(id, name, slug, created_by) values
  ('ca000000-0000-0000-0000-000000000001', 'Storage A', 'storage-a', '31000000-0000-0000-0000-000000000001'),
  ('cb000000-0000-0000-0000-000000000002', 'Storage B', 'storage-b', '32000000-0000-0000-0000-000000000002');
insert into public.organization_members(organization_id, user_id, role, status) values
  ('ca000000-0000-0000-0000-000000000001', '31000000-0000-0000-0000-000000000001', 'owner', 'active'),
  ('cb000000-0000-0000-0000-000000000002', '32000000-0000-0000-0000-000000000002', 'owner', 'active');

select ok(not public, 'artifacts bucket is private')
from storage.buckets where id = 'artifacts';
select is(file_size_limit, 52428800::bigint, 'bucket limit is 50 MiB')
from storage.buckets where id = 'artifacts';
select ok(private.artifact_storage_path_is_valid(
  'ca000000-0000-0000-0000-000000000001/31000000-0000-0000-0000-000000000001/aa000000-0000-0000-0000-000000000001/report.pdf'
), 'canonical org/user/object path is accepted');
select ok(not private.artifact_storage_path_is_valid(
  'ca000000-0000-0000-0000-000000000001/31000000-0000-0000-0000-000000000001/../secret.pdf'
), 'path traversal is rejected');
select ok(not private.artifact_storage_metadata_is_valid(
  'x/y/z/report.pdf', '{"size": 100, "mimetype": "image/png"}',
  '{"checksum_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "quarantine_status": "pending"}'
), 'false MIME and extension pair is rejected');

insert into public.artifacts(
  id, organization_id, name, kind, storage_bucket, storage_path, created_by, quarantine_status
) values
  ('aa000000-0000-0000-0000-000000000001', 'ca000000-0000-0000-0000-000000000001', 'clean.pdf', 'upload', 'artifacts', 'ca000000-0000-0000-0000-000000000001/31000000-0000-0000-0000-000000000001/aa000000-0000-0000-0000-000000000001/clean.pdf', '31000000-0000-0000-0000-000000000001', 'clean'),
  ('aa000000-0000-0000-0000-000000000002', 'ca000000-0000-0000-0000-000000000001', 'pending.pdf', 'upload', 'artifacts', 'ca000000-0000-0000-0000-000000000001/31000000-0000-0000-0000-000000000001/aa000000-0000-0000-0000-000000000002/pending.pdf', '31000000-0000-0000-0000-000000000001', 'pending'),
  ('aa000000-0000-0000-0000-000000000003', 'ca000000-0000-0000-0000-000000000001', 'spoof.pdf', 'upload', 'artifacts', 'ca000000-0000-0000-0000-000000000001/31000000-0000-0000-0000-000000000001/aa000000-0000-0000-0000-000000000003/spoof.pdf', '31000000-0000-0000-0000-000000000001', 'pending'),
  ('ab000000-0000-0000-0000-000000000001', 'cb000000-0000-0000-0000-000000000002', 'clean.pdf', 'upload', 'artifacts', 'cb000000-0000-0000-0000-000000000002/32000000-0000-0000-0000-000000000002/ab000000-0000-0000-0000-000000000001/clean.pdf', '32000000-0000-0000-0000-000000000002', 'clean');

insert into storage.objects(id, bucket_id, name, owner_id, metadata, user_metadata) values
  ('da000000-0000-0000-0000-000000000001', 'artifacts', 'ca000000-0000-0000-0000-000000000001/31000000-0000-0000-0000-000000000001/aa000000-0000-0000-0000-000000000001/clean.pdf', '31000000-0000-0000-0000-000000000001', '{"size":100,"mimetype":"application/pdf"}', '{"checksum_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","quarantine_status":"clean"}'),
  ('da000000-0000-0000-0000-000000000002', 'artifacts', 'ca000000-0000-0000-0000-000000000001/31000000-0000-0000-0000-000000000001/aa000000-0000-0000-0000-000000000002/pending.pdf', '31000000-0000-0000-0000-000000000001', '{"size":100,"mimetype":"application/pdf"}', '{"checksum_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","quarantine_status":"pending"}'),
  ('da000000-0000-0000-0000-000000000003', 'artifacts', 'ca000000-0000-0000-0000-000000000001/31000000-0000-0000-0000-000000000001/aa000000-0000-0000-0000-000000000003/spoof.pdf', '31000000-0000-0000-0000-000000000001', '{"size":100,"mimetype":"application/pdf"}', '{"checksum_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","quarantine_status":"clean"}'),
  ('db000000-0000-0000-0000-000000000001', 'artifacts', 'cb000000-0000-0000-0000-000000000002/32000000-0000-0000-0000-000000000002/ab000000-0000-0000-0000-000000000001/clean.pdf', '32000000-0000-0000-0000-000000000002', '{"size":100,"mimetype":"application/pdf"}', '{"checksum_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","quarantine_status":"clean"}');

set local role authenticated;
set local request.jwt.claim.sub = '31000000-0000-0000-0000-000000000001';

select is((select count(*) from storage.objects), 1::bigint,
  'member sees only clean objects in own tenant');
select is((select count(*) from storage.objects where id = 'da000000-0000-0000-0000-000000000003'), 0::bigint,
  'client user_metadata clean cannot bypass authoritative quarantine');
select results_eq(
  $$ select id from storage.objects where id = 'db000000-0000-0000-0000-000000000001' $$,
  $$ select null::uuid where false $$,
  'cross-tenant object is invisible'
);
select lives_ok(
  $$ insert into storage.objects(id, bucket_id, name, owner_id, metadata, user_metadata)
     values ('da000000-0000-0000-0000-000000000010', 'artifacts',
       'ca000000-0000-0000-0000-000000000001/31000000-0000-0000-0000-000000000001/aa000000-0000-0000-0000-000000000010/new.pdf',
       '31000000-0000-0000-0000-000000000001', '{"size":100,"mimetype":"application/pdf"}',
       '{"checksum_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","quarantine_status":"pending"}') $$,
  'member can insert a valid quarantined upload'
);
select throws_ok(
  $$ insert into public.artifacts(
       id, organization_id, name, kind, storage_bucket, storage_path, created_by, quarantine_status
     ) values (
       'aa000000-0000-0000-0000-000000000099',
       'ca000000-0000-0000-0000-000000000001', 'bypass.pdf', 'upload', 'artifacts',
       'ca000000-0000-0000-0000-000000000001/31000000-0000-0000-0000-000000000001/aa000000-0000-0000-0000-000000000099/bypass.pdf',
       '31000000-0000-0000-0000-000000000001', 'clean'
     ) $$,
  '42501', null, 'authenticated client cannot create an authoritative clean artifact'
);
select throws_ok(
  $$ insert into storage.objects(id, bucket_id, name, owner_id, metadata, user_metadata)
     values ('da000000-0000-0000-0000-000000000011', 'artifacts',
       'cb000000-0000-0000-0000-000000000002/31000000-0000-0000-0000-000000000001/aa000000-0000-0000-0000-000000000011/cross.pdf',
       '31000000-0000-0000-0000-000000000001', '{"size":100,"mimetype":"application/pdf"}',
       '{"checksum_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","quarantine_status":"pending"}') $$,
  '42501', null, 'cross-tenant insert is denied'
);
select throws_ok(
  $$ insert into storage.objects(id, bucket_id, name, owner_id, metadata, user_metadata)
     values ('da000000-0000-0000-0000-000000000012', 'artifacts',
       'ca000000-0000-0000-0000-000000000001/31000000-0000-0000-0000-000000000001/../escape.pdf',
       '31000000-0000-0000-0000-000000000001', '{"size":100,"mimetype":"application/pdf"}',
       '{"checksum_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","quarantine_status":"pending"}') $$,
  '42501', null, 'path traversal insert is denied'
);
select throws_ok(
  $$ insert into storage.objects(id, bucket_id, name, owner_id, metadata, user_metadata)
     values ('da000000-0000-0000-0000-000000000013', 'artifacts',
       'ca000000-0000-0000-0000-000000000001/31000000-0000-0000-0000-000000000001/aa000000-0000-0000-0000-000000000013/fake.pdf',
       '31000000-0000-0000-0000-000000000001', '{"size":100,"mimetype":"image/png"}',
       '{"checksum_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","quarantine_status":"pending"}') $$,
  '42501', null, 'false declared MIME is denied'
);
select throws_ok(
  $$ insert into storage.objects(id, bucket_id, name, owner_id, metadata, user_metadata)
     values ('da000000-0000-0000-0000-000000000014', 'artifacts',
       'ca000000-0000-0000-0000-000000000001/31000000-0000-0000-0000-000000000001/aa000000-0000-0000-0000-000000000014/no-checksum.pdf',
       '31000000-0000-0000-0000-000000000001', '{"size":100,"mimetype":"application/pdf"}',
       '{"quarantine_status":"pending"}') $$,
  '42501', null, 'missing checksum is denied'
);
select throws_ok(
  $$ insert into storage.objects(id, bucket_id, name, owner_id, metadata, user_metadata)
     values ('da000000-0000-0000-0000-000000000015', 'artifacts',
       'ca000000-0000-0000-0000-000000000001/31000000-0000-0000-0000-000000000001/aa000000-0000-0000-0000-000000000015/not-quarantined.pdf',
       '31000000-0000-0000-0000-000000000001', '{"size":100,"mimetype":"application/pdf"}',
       '{"checksum_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","quarantine_status":"clean"}') $$,
  '42501', null, 'client cannot bypass quarantine on insert'
);
set local storage.operation = 'storage.object.upload_update';
select lives_ok(
  $$ update storage.objects
     set metadata = '{"size":101,"mimetype":"application/pdf"}',
         user_metadata = '{"checksum_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","quarantine_status":"pending"}'
     where id = 'da000000-0000-0000-0000-000000000001' $$,
  'SELECT and UPDATE policies permit safe upsert replacement'
);
set local storage.operation = '';
select is((select count(*) from storage.objects where id = 'db000000-0000-0000-0000-000000000001'), 0::bigint,
  'cross-tenant object remains inaccessible after update attempts');

reset role;
select * from finish();
rollback;
