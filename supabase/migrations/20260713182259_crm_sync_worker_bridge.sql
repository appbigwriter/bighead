create table public.crm_sync_jobs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  connection_id uuid not null,
  status text not null default 'queued' check (status in ('queued','running','completed','dead_letter')),
  attempts integer not null default 0 check (attempts >= 0),
  available_at timestamptz not null default now(),
  locked_by text,
  lease_token uuid,
  locked_until timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  foreign key (organization_id, connection_id)
    references public.crm_connections(organization_id, id) on delete cascade
);
alter table public.crm_connections
  drop constraint if exists crm_connections_secret_ref_check,
  drop constraint if exists crm_connections_webhook_secret_ref_check,
  add constraint crm_connections_secret_ref_env_check
    check (length(secret_ref) between 18 and 134 and secret_ref ~ '^env://CRM_SECRET_[A-Z0-9_]*$'),
  add constraint crm_connections_webhook_secret_ref_env_check
    check (webhook_secret_ref is null or (length(webhook_secret_ref) between 18 and 134 and webhook_secret_ref ~ '^env://CRM_SECRET_[A-Z0-9_]*$')),
  add constraint crm_connections_configuration_no_secrets_check
    check (configuration::text !~* '(secret|token|password|api_key|apikey|authorization|url|endpoint)');
create unique index crm_sync_jobs_one_active_idx on public.crm_sync_jobs(connection_id)
where status in ('queued','running');
create index crm_sync_jobs_claim_idx on public.crm_sync_jobs(available_at,created_at)
where status='queued';
alter table public.crm_sync_jobs enable row level security;
create policy crm_sync_jobs_select on public.crm_sync_jobs for select to authenticated
using (private.current_user_has_role(organization_id,array['owner','admin','manager']::public.member_role[]));
grant select on public.crm_sync_jobs to authenticated;

create or replace function public.request_crm_sync(p_connection_id uuid, p_requested_by uuid)
returns uuid language plpgsql security definer set search_path='' as $$
declare v_org uuid; v_id uuid;
begin
  select c.organization_id into v_org from public.crm_connections c
   join public.organization_members m on m.organization_id=c.organization_id
   where c.id=p_connection_id and c.status='active' and m.user_id=p_requested_by
     and m.status='active' and m.role in ('owner','admin');
  if v_org is null then raise exception 'not_found_or_forbidden' using errcode='42501'; end if;
  insert into public.crm_sync_jobs(organization_id,connection_id) values(v_org,p_connection_id)
  on conflict (connection_id) where status in ('queued','running') do update
    set available_at=least(public.crm_sync_jobs.available_at,excluded.available_at)
  returning id into v_id;
  return v_id;
end $$;

create or replace function public.claim_crm_sync_jobs(p_worker text,p_limit integer default 5,p_lease_seconds integer default 60)
returns setof public.crm_sync_jobs language plpgsql security definer set search_path='' as $$
begin
  if coalesce(auth.jwt()->>'role','') <> 'service_role' then raise exception 'forbidden' using errcode='42501'; end if;
  return query with claimed as (
    select id from public.crm_sync_jobs where
      (status='queued' and available_at<=now() and (locked_until is null or locked_until<now()))
      or (status='running' and locked_until<now()) order by available_at,created_at
      for update skip locked limit least(greatest(p_limit,1),25)
  ) update public.crm_sync_jobs j set status='running',attempts=attempts+1,locked_by=p_worker,lease_token=gen_random_uuid(),
      locked_until=now()+make_interval(secs=>least(greatest(p_lease_seconds,10),300))
    from claimed where j.id=claimed.id returning j.*;
end $$;

create or replace function public.ack_crm_sync_job(p_id uuid,p_worker text,p_lease_token uuid)
returns boolean language plpgsql security definer set search_path='' as $$
declare n integer; begin
  if coalesce(auth.jwt()->>'role','') <> 'service_role' then raise exception 'forbidden' using errcode='42501'; end if;
  update public.crm_sync_jobs set status='completed',completed_at=now(),locked_by=null,lease_token=null,locked_until=null,last_error=null
   where id=p_id and status='running' and locked_by=p_worker and lease_token=p_lease_token and locked_until>now();
  get diagnostics n=row_count; return n=1;
end $$;

create or replace function public.heartbeat_crm_sync_job(p_id uuid,p_worker text,p_lease_token uuid,p_lease_seconds integer default 60)
returns boolean language plpgsql security definer set search_path='' as $$
declare n integer; begin
  if coalesce(auth.jwt()->>'role','') <> 'service_role' then raise exception 'forbidden' using errcode='42501'; end if;
  update public.crm_sync_jobs set locked_until=now()+make_interval(secs=>least(greatest(p_lease_seconds,10),300))
   where id=p_id and status='running' and locked_by=p_worker and lease_token=p_lease_token and locked_until>now();
  get diagnostics n=row_count; return n=1;
end $$;

create or replace function public.nack_crm_sync_job(p_id uuid,p_worker text,p_lease_token uuid,p_error text,p_max_attempts integer default 8)
returns boolean language plpgsql security definer set search_path='' as $$
declare n integer; begin
  if coalesce(auth.jwt()->>'role','') <> 'service_role' then raise exception 'forbidden' using errcode='42501'; end if;
  update public.crm_sync_jobs set status=case when attempts>=p_max_attempts then 'dead_letter' else 'queued' end,
    available_at=case when attempts>=p_max_attempts then available_at else now()+make_interval(secs=>least(300,power(2,attempts)::integer)) end,
    locked_by=null,lease_token=null,locked_until=null,last_error=left(p_error,2000)
   where id=p_id and status='running' and locked_by=p_worker and lease_token=p_lease_token;
  get diagnostics n=row_count; return n=1;
end $$;

revoke all on function public.request_crm_sync(uuid,uuid),public.claim_crm_sync_jobs(text,integer,integer),
 public.ack_crm_sync_job(uuid,text,uuid),public.heartbeat_crm_sync_job(uuid,text,uuid,integer),
 public.nack_crm_sync_job(uuid,text,uuid,text,integer) from public,anon,authenticated;
grant execute on function public.request_crm_sync(uuid,uuid) to service_role;
grant execute on function public.claim_crm_sync_jobs(text,integer,integer),public.ack_crm_sync_job(uuid,text,uuid),
 public.heartbeat_crm_sync_job(uuid,text,uuid,integer),public.nack_crm_sync_job(uuid,text,uuid,text,integer) to service_role;

create or replace function public.apply_crm_sync_page(
  p_connection_id uuid,p_records jsonb,p_next_cursor text,p_high_watermark timestamptz,p_expected_version bigint
) returns bigint language plpgsql security definer set search_path='' as $$
declare v_org uuid; v_current bigint; v_existing_watermark timestamptz; v_record jsonb; v_type text; v_external text; v_local uuid; v_hash text;
begin
  if coalesce(auth.jwt()->>'role','') <> 'service_role' then raise exception 'forbidden' using errcode='42501'; end if;
  select organization_id into v_org from public.crm_connections where id=p_connection_id and status='active';
  if v_org is null then raise exception 'crm_connection_unavailable'; end if;
  insert into public.crm_sync_cursors(connection_id,organization_id,version)
    values(p_connection_id,v_org,0) on conflict(connection_id) do nothing;
  select version,high_watermark into v_current,v_existing_watermark from public.crm_sync_cursors where connection_id=p_connection_id for update;
  if v_current<>p_expected_version then raise exception 'crm_cursor_version_conflict' using errcode='40001'; end if;
  if p_high_watermark is not null and v_existing_watermark is not null and p_high_watermark<v_existing_watermark then
    raise exception 'crm_page_older_than_watermark' using errcode='40001';
  end if;
  for v_record in select value from jsonb_array_elements(coalesce(p_records,'[]'::jsonb)) loop
    v_type=v_record->>'entityType'; v_external=v_record->>'externalId';
    if v_type not in ('account','contact','lead','opportunity') or coalesce(v_external,'')='' then
      raise exception 'invalid_crm_record';
    end if;
    v_hash=encode(extensions.digest(convert_to((v_record->'fields')::text,'UTF8'),'sha256'),'hex');
    select local_id into v_local from public.crm_external_links
      where connection_id=p_connection_id and entity_type=v_type and external_id=v_external;
    if v_local is null then
      v_local=gen_random_uuid();
      if v_type='account' then
        insert into public.crm_accounts(id,organization_id,name,domain,metadata)
          values(v_local,v_org,coalesce(v_record#>>'{fields,name}',v_external),v_record#>>'{fields,domain}',v_record->'fields');
      elsif v_type='contact' then
        insert into public.crm_contacts(id,organization_id,name,email,phone,consent_status,legal_basis,metadata)
          values(v_local,v_org,coalesce(v_record#>>'{fields,name}',v_external),nullif(v_record#>>'{fields,email}',''),
            v_record#>>'{fields,phone}',coalesce(v_record#>>'{fields,consentStatus}','unknown'),v_record#>>'{fields,legalBasis}',v_record->'fields');
      elsif v_type='lead' then
        insert into public.leads(id,organization_id,status,source,score_factors)
          values(v_local,v_org,coalesce(v_record#>>'{fields,status}','new')::public.lead_status,v_record#>>'{fields,source}',v_record->'fields');
      else
        insert into public.opportunities(id,organization_id,name,stage,amount,currency,probability)
          values(v_local,v_org,coalesce(v_record#>>'{fields,name}',v_external),coalesce(v_record#>>'{fields,stage}','new'),
            nullif(v_record#>>'{fields,amount}','')::numeric,coalesce(v_record#>>'{fields,currency}','BRL'),
            nullif(v_record#>>'{fields,probability}','')::numeric);
      end if;
      insert into public.crm_external_links(organization_id,connection_id,entity_type,external_id,local_id,external_updated_at,payload_hash)
        values(v_org,p_connection_id,v_type,v_external,v_local,(v_record->>'updatedAt')::timestamptz,v_hash);
    elsif (select payload_hash from public.crm_external_links where connection_id=p_connection_id and entity_type=v_type and external_id=v_external)<>v_hash
      and (select external_updated_at from public.crm_external_links where connection_id=p_connection_id and entity_type=v_type and external_id=v_external) <= (v_record->>'updatedAt')::timestamptz then
      if v_type='account' then update public.crm_accounts set name=coalesce(v_record#>>'{fields,name}',name),metadata=v_record->'fields' where id=v_local and organization_id=v_org;
      elsif v_type='contact' then update public.crm_contacts set name=coalesce(v_record#>>'{fields,name}',name),metadata=v_record->'fields' where id=v_local and organization_id=v_org;
      elsif v_type='lead' then update public.leads set source=coalesce(v_record#>>'{fields,source}',source),score_factors=v_record->'fields' where id=v_local and organization_id=v_org;
      else update public.opportunities set name=coalesce(v_record#>>'{fields,name}',name),stage=coalesce(v_record#>>'{fields,stage}',stage) where id=v_local and organization_id=v_org; end if;
      update public.crm_external_links set payload_hash=v_hash,external_updated_at=(v_record->>'updatedAt')::timestamptz
       where connection_id=p_connection_id and entity_type=v_type and external_id=v_external;
    end if;
  end loop;
  update public.crm_sync_cursors set cursor=p_next_cursor,high_watermark=greatest(high_watermark,p_high_watermark),
    version=version+1,updated_at=now() where connection_id=p_connection_id returning version into v_current;
  update public.crm_connections set last_synced_at=now() where id=p_connection_id;
  return v_current;
end $$;
revoke all on function public.apply_crm_sync_page(uuid,jsonb,text,timestamptz,bigint) from public,anon,authenticated;
grant execute on function public.apply_crm_sync_page(uuid,jsonb,text,timestamptz,bigint) to service_role;
