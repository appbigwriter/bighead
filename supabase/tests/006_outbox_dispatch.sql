begin;
create extension if not exists pgtap with schema extensions;
select plan(12);

-- Keep claims deterministic even when the suite runs after seeds or API/E2E activity.
-- Every mutation is contained by this test transaction and rolled back at the end.
delete from public.organizations where id='ed000000-0000-0000-0000-000000000001';
update public.event_outbox
set available_at=now()+interval '1 day'
where published_at is null and dead_lettered_at is null;

insert into public.organizations(id,name,slug)
values('ed000000-0000-0000-0000-000000000001','Outbox Test','outbox-test');
insert into public.event_outbox(
  id,organization_id,event_type,aggregate_type,aggregate_id,payload
) values(
  'ed100000-0000-0000-0000-000000000001',
  'ed000000-0000-0000-0000-000000000001',
  'tasks.created','task','ed200000-0000-0000-0000-000000000001','{}'
),(
  'ed100000-0000-0000-0000-000000000002',
  'ed000000-0000-0000-0000-000000000001',
  'tasks.failed','task','ed200000-0000-0000-0000-000000000002','{}'
);
update public.event_outbox set available_at=now()+interval '1 hour',attempts=7
where id='ed100000-0000-0000-0000-000000000002';

set local role authenticated;
set local request.jwt.claims='{"role":"authenticated","sub":"00000000-0000-0000-0000-000000000001"}';
select throws_ok(
  $$ select * from public.claim_event_outbox('attacker',10,30) $$,
  '42501',null,'authenticated callers cannot claim the service outbox'
);
reset role;

set local role service_role;
set local request.jwt.claims='{"role":"service_role"}';
do $$
declare claimed_token uuid;
begin
  select lease_token into claimed_token
  from public.claim_event_outbox('worker-a',10,30);
  perform set_config(
    'test.outbox_lease_a',
    claimed_token::text,
    false
  );
end $$;
select ok(current_setting('test.outbox_lease_a',true) is not null,
  'first worker claims the available event');
select is((select count(*) from public.claim_event_outbox('worker-b',10,30)),0::bigint,
  'skip-locked lease prevents a second claim');
select is(public.ack_event_outbox(
  'ed100000-0000-0000-0000-000000000001','worker-b',
  current_setting('test.outbox_lease_a')::uuid),false,
  'a different worker cannot acknowledge the lease');
reset role;
update public.event_outbox set locked_until=now()-interval '1 second'
where id='ed100000-0000-0000-0000-000000000001';
set local role service_role;
set local request.jwt.claims='{"role":"service_role"}';
do $$
declare claimed_token uuid;
begin
  select lease_token into claimed_token
  from public.claim_event_outbox('worker-a',10,30);
  perform set_config('test.outbox_lease_a2', claimed_token::text, false);
end $$;
select isnt(current_setting('test.outbox_lease_a2'),current_setting('test.outbox_lease_a'),
  'expired lease is reclaimed with a new token when the worker name is reused');
select is(public.ack_event_outbox(
  'ed100000-0000-0000-0000-000000000001','worker-a',
  current_setting('test.outbox_lease_a')::uuid),false,
  'stale fencing token cannot acknowledge a replacement lease');
select is(public.nack_event_outbox(
  'ed100000-0000-0000-0000-000000000001','worker-a',
  current_setting('test.outbox_lease_a2')::uuid,'temporary',8),true,
  'lease owner can release a failed delivery');
reset role;

update public.event_outbox set available_at=now()-interval '1 second'
where id='ed100000-0000-0000-0000-000000000001';
set local role service_role;
set local request.jwt.claims='{"role":"service_role"}';
do $$
declare claimed_token uuid;
begin
  select lease_token into claimed_token
  from public.claim_event_outbox('worker-b',10,30);
  perform set_config('test.outbox_lease_b', claimed_token::text, false);
end $$;
select ok(current_setting('test.outbox_lease_b',true) is not null,
  'released delivery is reclaimable after backoff');
select is(public.ack_event_outbox(
  'ed100000-0000-0000-0000-000000000001','worker-b',
  current_setting('test.outbox_lease_b')::uuid),true,
  'lease owner acknowledges delivery');
reset role;
select is((select count(*) from public.event_outbox
  where id='ed100000-0000-0000-0000-000000000001' and published_at is not null),1::bigint,
  'ack records publication exactly once');
update public.event_outbox set available_at=now()-interval '1 second'
where id='ed100000-0000-0000-0000-000000000002';
set local role service_role;
set local request.jwt.claims='{"role":"service_role"}';
do $$
declare claimed_token uuid;
begin
  select lease_token into claimed_token
  from public.claim_event_outbox('worker-c',10,30);
  perform set_config('test.outbox_lease_c', claimed_token::text, false);
end $$;
select ok(current_setting('test.outbox_lease_c',true) is not null,
  'final attempt is claimed');
select public.nack_event_outbox(
  'ed100000-0000-0000-0000-000000000002','worker-c',
  current_setting('test.outbox_lease_c')::uuid,'permanent',8);
reset role;
select ok((select dead_lettered_at is not null from public.event_outbox
  where id='ed100000-0000-0000-0000-000000000002'),
  'attempt limit moves delivery to dead letter');

select * from finish();
rollback;
