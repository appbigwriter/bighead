begin;
revoke all on function private.protect_running_experiment_variant()
from public, anon, authenticated;
commit;
