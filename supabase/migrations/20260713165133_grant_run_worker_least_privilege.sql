-- The run RPCs are SECURITY INVOKER by design. Give the service role only the
-- relation privileges required by those RPCs; application roles still cannot
-- execute them and the private schema is not exposed by the Data API.
grant select, update on public.runs to service_role;
grant select, insert on public.cost_events to service_role;
grant usage on schema private to service_role;
grant select, insert, update on private.run_effect_ledger to service_role;
