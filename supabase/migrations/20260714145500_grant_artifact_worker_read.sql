-- The artifact scanner reads only the immutable upload facts needed to verify
-- a claimed object. State changes remain behind security-definer RPCs.
grant select (id, storage_path, metadata, quarantine_status)
  on public.artifacts
  to service_role;
