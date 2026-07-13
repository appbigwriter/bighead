begin;

alter table public.event_outbox
  add column available_at timestamptz not null default now(),
  add column locked_at timestamptz,
  add column locked_until timestamptz,
  add column locked_by text,
  add column last_error text,
  add column dead_lettered_at timestamptz;

drop index if exists public.event_outbox_pending_idx;
create index event_outbox_dispatch_idx
on public.event_outbox(available_at, created_at)
where published_at is null and dead_lettered_at is null;

create or replace function public.claim_event_outbox(
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
         locked_by = p_worker, attempts = attempts + 1
    from claimed where e.id = claimed.id
  returning e.*;
end;
$$;

create or replace function public.ack_event_outbox(p_id uuid, p_worker text)
returns boolean language plpgsql security definer set search_path = '' as $$
declare affected integer;
begin
  if coalesce(auth.jwt() ->> 'role', '') <> 'service_role' then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  update public.event_outbox set published_at=now(), locked_at=null, locked_until=null,
    locked_by=null,
    last_error=null where id=p_id and locked_by=p_worker and published_at is null;
  get diagnostics affected = row_count;
  return affected = 1;
end;
$$;

create or replace function public.nack_event_outbox(
  p_id uuid, p_worker text, p_error text, p_max_attempts integer default 8
)
returns boolean language plpgsql security definer set search_path = '' as $$
declare affected integer;
begin
  if coalesce(auth.jwt() ->> 'role', '') <> 'service_role' then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  update public.event_outbox
     set locked_at=null, locked_until=null, locked_by=null, last_error=left(p_error, 2000),
         dead_lettered_at=case when attempts >= p_max_attempts then now() else null end,
         available_at=case when attempts >= p_max_attempts then available_at
           else now() + make_interval(secs => least(300, (power(2, attempts))::integer)) end
   where id=p_id and locked_by=p_worker and published_at is null;
  get diagnostics affected = row_count;
  return affected = 1;
end;
$$;

revoke execute on function public.claim_event_outbox(text, integer, integer)
from public, anon, authenticated;
revoke execute on function public.ack_event_outbox(uuid, text)
from public, anon, authenticated;
revoke execute on function public.nack_event_outbox(uuid, text, text, integer)
from public, anon, authenticated;
grant execute on function public.claim_event_outbox(text, integer, integer) to service_role;
grant execute on function public.ack_event_outbox(uuid, text) to service_role;
grant execute on function public.nack_event_outbox(uuid, text, text, integer) to service_role;

commit;
