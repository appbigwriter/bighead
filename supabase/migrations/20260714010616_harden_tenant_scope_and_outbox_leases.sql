begin;

-- Tenant ownership is part of a row's identity. RLS checks both OLD and NEW
-- rows, but a user who belongs to two organizations could otherwise move a
-- row between them. Enforce the invariant below every public tenant table.
create or replace function private.preserve_organization_scope()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if new.organization_id is distinct from old.organization_id then
    raise exception 'tenant_scope_immutable' using errcode = '23514';
  end if;
  return new;
end;
$$;

revoke execute on function private.preserve_organization_scope()
from public, anon, authenticated;

do $$
declare
  relation record;
begin
  for relation in
    select c.oid::regclass as relation_name, c.relname as table_name
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    join pg_attribute a on a.attrelid = c.oid
    where n.nspname = 'public'
      and c.relkind in ('r', 'p')
      and a.attname = 'organization_id'
      and not a.attisdropped
  loop
    execute format(
      'drop trigger if exists preserve_organization_scope on %s',
      relation.relation_name
    );
    execute format(
      'create trigger preserve_organization_scope before update of organization_id on %s for each row execute function private.preserve_organization_scope()',
      relation.relation_name
    );
  end loop;
end;
$$;

-- A worker name is diagnostic metadata, not a fencing token. Give every
-- claim an unguessable token and require the still-active lease for finalize.
alter table public.event_outbox
  add column lease_token uuid;

drop function public.claim_event_outbox(text, integer, integer);
drop function public.ack_event_outbox(uuid, text);
drop function public.nack_event_outbox(uuid, text, text, integer);

create function public.claim_event_outbox(
  p_worker text,
  p_limit integer default 50,
  p_lease_seconds integer default 30
)
returns setof public.event_outbox
language plpgsql security definer set search_path = '' as $$
begin
  if coalesce(auth.jwt() ->> 'role', '') <> 'service_role' then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  if p_worker is null or char_length(p_worker) not between 1 and 200 then
    raise exception 'invalid_worker';
  end if;
  return query
  with claimed as (
    select id from public.event_outbox
    where published_at is null and dead_lettered_at is null
      and available_at <= now()
      and (locked_until is null or locked_until < now())
    order by available_at, created_at, id
    for update skip locked
    limit least(greatest(p_limit, 1), 200)
  )
  update public.event_outbox e
     set locked_at = now(),
         locked_until = now() + make_interval(secs => least(greatest(p_lease_seconds, 1), 300)),
         locked_by = p_worker,
         lease_token = gen_random_uuid(),
         attempts = attempts + 1
    from claimed where e.id = claimed.id
  returning e.*;
end;
$$;

create function public.ack_event_outbox(p_id uuid, p_worker text, p_lease_token uuid)
returns boolean language plpgsql security definer set search_path = '' as $$
declare affected integer;
begin
  if coalesce(auth.jwt() ->> 'role', '') <> 'service_role' then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  update public.event_outbox
     set published_at = now(), locked_at = null, locked_until = null,
         locked_by = null, lease_token = null, last_error = null
   where id = p_id and locked_by = p_worker and lease_token = p_lease_token
     and locked_until >= now() and published_at is null;
  get diagnostics affected = row_count;
  return affected = 1;
end;
$$;

create function public.nack_event_outbox(
  p_id uuid,
  p_worker text,
  p_lease_token uuid,
  p_error text,
  p_max_attempts integer default 8
)
returns boolean language plpgsql security definer set search_path = '' as $$
declare affected integer;
begin
  if coalesce(auth.jwt() ->> 'role', '') <> 'service_role' then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  update public.event_outbox
     set locked_at = null, locked_until = null, locked_by = null,
         lease_token = null, last_error = left(p_error, 2000),
         dead_lettered_at = case when attempts >= p_max_attempts then now() else null end,
         available_at = case when attempts >= p_max_attempts then available_at
           else now() + make_interval(secs => least(300, (power(2, attempts))::integer)) end
   where id = p_id and locked_by = p_worker and lease_token = p_lease_token
     and locked_until >= now() and published_at is null;
  get diagnostics affected = row_count;
  return affected = 1;
end;
$$;

revoke execute on function public.claim_event_outbox(text, integer, integer)
from public, anon, authenticated;
revoke execute on function public.ack_event_outbox(uuid, text, uuid)
from public, anon, authenticated;
revoke execute on function public.nack_event_outbox(uuid, text, uuid, text, integer)
from public, anon, authenticated;
grant execute on function public.claim_event_outbox(text, integer, integer) to service_role;
grant execute on function public.ack_event_outbox(uuid, text, uuid) to service_role;
grant execute on function public.nack_event_outbox(uuid, text, uuid, text, integer) to service_role;

commit;
