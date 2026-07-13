$ErrorActionPreference = "Continue"

$statusText = & cmd /d /s /c "pnpm exec supabase status -o json 2>nul"
if ($LASTEXITCODE -ne 0) {
  throw "Local Supabase is not running. Run pnpm db:start first."
}
$status = $statusText | ConvertFrom-Json

$env:APP_ENV = "test"
$env:APP_URL = "http://127.0.0.1:3101"
$env:API_URL = "http://127.0.0.1:8010"
$env:API_PORT = "8010"
$env:BIGHEAD_REAL_API_URL = $env:API_URL
$env:BIGHEAD_WORKSPACE_MODE = "real"
$seedPath = Join-Path $PSScriptRoot "../supabase/seed.sql"
$seedText = Get-Content $seedPath -Raw
$atlasMatch = [regex]::Match($seedText, "owner@atlas\.bighead\.(dev|test)")
$beaconMatch = [regex]::Match($seedText, "owner@beacon\.bighead\.(dev|test)")
if (-not $atlasMatch.Success -or -not $beaconMatch.Success) {
  throw "Deterministic Atlas/Beacon owners are missing from supabase/seed.sql."
}
$env:BIGHEAD_E2E_EMAIL = $atlasMatch.Value
$env:BIGHEAD_E2E_BEACON_EMAIL = $beaconMatch.Value
$env:BIGHEAD_E2E_PASSWORD = "BigHeadLocalOnly!2026"
$env:BIGHEAD_E2E_ORGANIZATION_ID = "a7100000-0000-0000-0000-000000000001"
$env:BIGHEAD_REAL_SUPABASE_URL = $status.API_URL
$env:CORS_ORIGINS = "http://127.0.0.1:3101"
$env:LOG_LEVEL = "WARNING"
$env:DATABASE_URL = $status.DB_URL
$env:DIRECT_DATABASE_URL = $status.DB_URL
$env:SUPABASE_URL = $status.API_URL
$env:SUPABASE_PUBLISHABLE_KEY = $status.PUBLISHABLE_KEY
$env:NEXT_PUBLIC_SUPABASE_URL = $status.API_URL
$env:NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = $status.PUBLISHABLE_KEY
$env:SUPABASE_SECRET_KEY = $status.SECRET_KEY
$env:STORAGE_BUCKET = "artifacts"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:QUEUE_NAME = "bighead:e2e"
$env:JOB_LEASE_SECONDS = "30"
$env:OTEL_SERVICE_NAME = "bighead-api-e2e"
$env:OTEL_EXPORTER_OTLP_ENDPOINT = "http://127.0.0.1:4318"
$env:OTEL_EXPORTER_OTLP_HEADERS = ""
$env:SENTRY_DSN = ""
$env:ENCRYPTION_KEY = "local-e2e-encryption-key-32chars"
$env:WEBHOOK_SIGNING_SECRET = "local-e2e-webhook-secret"
$env:PORTAL_TOKEN_PEPPER = "local-e2e-portal-pepper"

pnpm --filter @bighead/web build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
pnpm --filter @bighead/web exec playwright test --config playwright.real.config.ts
exit $LASTEXITCODE
