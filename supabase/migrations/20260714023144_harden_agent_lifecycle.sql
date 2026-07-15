-- Agents are managed through the audited API.  Direct Data API mutations would
-- bypass consumer checks, outbox events and optimistic versioning.
drop policy if exists agents_manage_insert on public.agents;
drop policy if exists agents_manage_update on public.agents;
drop policy if exists agents_manage_delete on public.agents;
drop policy if exists agent_versions_manage_insert on public.agent_versions;
drop policy if exists agent_versions_manage_update on public.agent_versions;
drop policy if exists agent_versions_manage_delete on public.agent_versions;
drop policy if exists agent_version_skills_manage_insert on public.agent_version_skills;
drop policy if exists agent_version_skills_manage_update on public.agent_version_skills;
drop policy if exists agent_version_skills_manage_delete on public.agent_version_skills;

create or replace function private.protect_published_agent_version()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if old.published_at is not null then
    raise exception 'published_agent_version_immutable' using errcode = '23514';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end;
$$;
revoke execute on function private.protect_published_agent_version() from public, anon, authenticated;

drop trigger if exists agent_versions_protect_published on public.agent_versions;
create trigger agent_versions_protect_published
before update or delete on public.agent_versions
for each row execute function private.protect_published_agent_version();
