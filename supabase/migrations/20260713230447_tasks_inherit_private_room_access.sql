-- Tasks linked to a private room inherit that room's visibility.  This keeps
-- direct Data API access aligned with the collaboration API and prevents a
-- same-tenant member from discovering private-room work by ID or filters.

drop policy if exists tasks_select on public.tasks;
create policy tasks_select on public.tasks for select to authenticated using (
  private.current_user_is_member(organization_id)
  and (
    room_id is null
    or exists (
      select 1 from public.rooms room
      where room.id = tasks.room_id
        and room.organization_id = tasks.organization_id
    )
  )
);

drop policy if exists tasks_insert on public.tasks;
create policy tasks_insert on public.tasks for insert to authenticated with check (
  private.current_user_is_member(organization_id)
  and (
    room_id is null
    or exists (
      select 1 from public.rooms room
      where room.id = tasks.room_id
        and room.organization_id = tasks.organization_id
    )
  )
);

drop policy if exists tasks_update_safe on public.tasks;
create policy tasks_update_safe on public.tasks for update to authenticated using (
  private.current_user_is_member(organization_id)
  and (
    room_id is null
    or exists (
      select 1 from public.rooms room
      where room.id = tasks.room_id
        and room.organization_id = tasks.organization_id
    )
  )
) with check (
  private.current_user_is_member(organization_id)
  and (
    room_id is null
    or exists (
      select 1 from public.rooms room
      where room.id = tasks.room_id
        and room.organization_id = tasks.organization_id
    )
  )
);
