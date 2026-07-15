param(
  [ValidateSet("up", "down", "status", "logs")]
  [string]$Action = "up",
  [ValidateRange(1024, 65535)]
  [int]$WebPort = 3002
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-Compose {
  param([string[]]$Arguments)
  & docker compose --project-name bighead-local-app `
    -f compose.production.yml -f compose.local.yml @Arguments
  if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed with exit code $LASTEXITCODE" }
}

$null = & cmd.exe /d /c "pnpm exec supabase status --output json 2>nul"
if ($LASTEXITCODE -ne 0) {
  & pnpm exec supabase start
  if ($LASTEXITCODE -ne 0) { throw "Could not start the local Supabase stack" }
}
$Supabase = (& cmd.exe /d /c "pnpm exec supabase status --output json 2>nul" | Out-String) | ConvertFrom-Json

$env:APP_URL = "http://127.0.0.1:$WebPort"
$env:API_URL = "http://127.0.0.1:8000"
$env:CORS_ORIGINS = $env:APP_URL
$env:WEB_BIND_ADDRESS = "127.0.0.1"
$env:API_BIND_ADDRESS = "127.0.0.1"
$env:WEB_PORT = [string]$WebPort
$env:API_PORT = "8000"
$env:WEB_DOMAIN = "localhost"
$env:API_DOMAIN = "api.localhost"
$env:ACME_EMAIL = "local@bighead.invalid"

$env:NEXT_PUBLIC_SUPABASE_URL = [string]$Supabase.API_URL
$env:NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = [string]$Supabase.PUBLISHABLE_KEY
$env:SUPABASE_URL = ([string]$Supabase.API_URL).Replace("127.0.0.1", "host.docker.internal")
$env:SUPABASE_PUBLIC_URL = [string]$Supabase.API_URL
$env:SUPABASE_PUBLISHABLE_KEY = [string]$Supabase.PUBLISHABLE_KEY
# The local gateway still authorizes PostgREST server calls with the service-role JWT.
# Production may use the dashboard secret key, but the CLI's sb_secret_* value is not
# interchangeable with service_role against every local service.
$env:SUPABASE_SECRET_KEY = [string]$Supabase.SERVICE_ROLE_KEY
$env:DATABASE_URL = ([string]$Supabase.DB_URL).Replace("127.0.0.1", "host.docker.internal")
$env:DATABASE_SERVICE_URL = $env:DATABASE_URL
$env:DIRECT_DATABASE_URL = [string]$Supabase.DB_URL
$env:SUPABASE_AUTH_SITE_URL = $env:APP_URL
$env:SUPABASE_AUTH_REDIRECT_URLS = "$($env:APP_URL)/auth/callback"
$env:SUPABASE_AUTH_SMTP_CONFIGURED = "true"
$env:STORAGE_BUCKET = "artifacts"
$env:SIGNED_URL_TTL_SECONDS = "900"

$env:REDIS_PASSWORD = "bighead-local-redis-only"
$env:QUEUE_NAME = "bighead:local"
$env:JOB_LEASE_SECONDS = "30"
$env:MALWARE_SCANNER_URL = "clamd://clamav:3310"
$env:MALWARE_SCANNER_API_KEY = ""

$env:LLM_PROVIDER_DEFAULT = "openai"
$env:LLM_PROVIDER_FALLBACK = "anthropic"
$env:LLM_MODEL_DEFAULT = "local-unconfigured-primary"
$env:LLM_MODEL_FALLBACK = "local-unconfigured-fallback"
$env:LLM_TIMEOUT_SECONDS = "60"
$env:OPENAI_API_KEY = ""
$env:ANTHROPIC_API_KEY = ""
$env:GOOGLE_GENAI_API_KEY = ""
$env:RUN_PROVIDER_URL = ""
$env:RUN_PROVIDER_API_KEY = ""
$env:CRM_PROVIDER_ENDPOINTS = "{}"

$env:LOG_LEVEL = "INFO"
$env:SENTRY_DSN = ""
$env:OTEL_EXPORTER_OTLP_ENDPOINT = ""
$env:OTEL_EXPORTER_OTLP_HEADERS = ""
$env:OTEL_SERVICE_NAME = "bighead-api-local"
$env:WORKER_OTEL_SERVICE_NAME = "bighead-worker-local"
$env:ENCRYPTION_KEY = "bighead-local-encryption-key-32-characters"
$env:WEBHOOK_SIGNING_SECRET = "bighead-local-webhook-signing-secret"
$env:PORTAL_TOKEN_PEPPER = "bighead-local-portal-token-pepper"

if ($Action -eq "down") {
  Invoke-Compose @("down", "--remove-orphans")
  exit 0
}
if ($Action -eq "status") {
  Invoke-Compose @("ps")
  exit 0
}
if ($Action -eq "logs") {
  Invoke-Compose @("logs", "--tail", "200", "web", "api", "worker", "redis", "clamav")
  exit 0
}

Invoke-Compose @("config", "-q")
Invoke-Compose @("up", "-d", "--build", "web", "api", "worker", "redis", "clamav")
Invoke-Compose @("ps")
