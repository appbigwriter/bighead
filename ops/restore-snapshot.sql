\set ON_ERROR_STOP on
\pset tuples_only on
\pset format unaligned
begin isolation level repeatable read read only;
select pg_backend_pid()::text || ':' || pg_export_snapshot();
select pg_sleep(300);
rollback;
