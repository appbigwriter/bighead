$ErrorActionPreference = "Stop"

$statusText = & cmd /d /s /c "pnpm exec supabase status -o json 2>nul"
if ($LASTEXITCODE -ne 0) {
  throw "Local Supabase is not running. Run pnpm db:start first."
}
$status = $statusText | ConvertFrom-Json

$env:BIGHEAD_RUN_OUTBOX_INTEGRATION = "1"
$env:SUPABASE_INTEGRATION_URL = $status.API_URL
$env:SUPABASE_INTEGRATION_SECRET_KEY = $status.SECRET_KEY
$env:SUPABASE_INTEGRATION_DATABASE_URL = $status.DB_URL
if (-not $env:REDIS_URL) {
  $env:REDIS_URL = "redis://127.0.0.1:6379/0"
}

uv run --project apps/worker --extra dev pytest apps/worker/tests/test_outbox_integration.py -q
exit $LASTEXITCODE
