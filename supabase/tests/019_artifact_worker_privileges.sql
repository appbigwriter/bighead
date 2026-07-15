begin;

select plan(8);

select ok(has_column_privilege('service_role', 'public.artifacts', 'id', 'SELECT'), 'scanner can read artifact id');
select ok(has_column_privilege('service_role', 'public.artifacts', 'storage_path', 'SELECT'), 'scanner can read storage path');
select ok(has_column_privilege('service_role', 'public.artifacts', 'metadata', 'SELECT'), 'scanner can read verification metadata');
select ok(has_column_privilege('service_role', 'public.artifacts', 'quarantine_status', 'SELECT'), 'scanner can filter pending artifacts');
select ok(not has_table_privilege('service_role', 'public.artifacts', 'SELECT'), 'scanner has no table-wide select');
select ok(not has_table_privilege('service_role', 'public.artifacts', 'INSERT'), 'scanner cannot insert artifacts directly');
select ok(not has_table_privilege('service_role', 'public.artifacts', 'UPDATE'), 'scanner cannot update artifacts directly');
select ok(not has_table_privilege('service_role', 'public.artifacts', 'DELETE'), 'scanner cannot delete artifacts directly');

select * from finish();
rollback;
