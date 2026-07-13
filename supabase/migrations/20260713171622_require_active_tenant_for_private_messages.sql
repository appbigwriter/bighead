drop policy if exists messages_select on public.messages;
create policy messages_select on public.messages for select to authenticated using (
  private.current_user_is_member(organization_id)
  and exists (
    select 1 from public.rooms room
     where room.id=messages.room_id
       and room.organization_id=messages.organization_id
       and (
         not room.is_private
         or private.current_user_has_role(
           room.organization_id,array['owner','admin']::public.member_role[]
         )
         or private.current_user_is_room_member(room.id)
       )
  )
);

drop policy if exists messages_insert on public.messages;
create policy messages_insert on public.messages for insert to authenticated with check (
  author_user_id=(select auth.uid())
  and private.current_user_is_member(organization_id)
  and exists (
    select 1 from public.rooms room
     where room.id=messages.room_id
       and room.organization_id=messages.organization_id
       and (not room.is_private or private.current_user_is_room_member(room.id))
  )
);

drop policy if exists messages_update_own on public.messages;
create policy messages_update_own on public.messages for update to authenticated
using (
  author_user_id=(select auth.uid()) and deleted_at is null
  and private.current_user_is_member(organization_id)
  and exists (
    select 1 from public.rooms room
     where room.id=messages.room_id
       and room.organization_id=messages.organization_id
       and (not room.is_private or private.current_user_is_room_member(room.id))
  )
)
with check (
  author_user_id=(select auth.uid())
  and private.current_user_is_member(organization_id)
  and exists (
    select 1 from public.rooms room
     where room.id=messages.room_id
       and room.organization_id=messages.organization_id
       and (not room.is_private or private.current_user_is_room_member(room.id))
  )
);
