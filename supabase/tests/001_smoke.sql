begin;
select plan(1);

select ok(true, 'Sprint 1 Supabase smoke test');

select * from finish();
rollback;
