param(
  [string]$Container = "supabase_db_bighead-local",
  [string]$SourceDatabase = "postgres",
  [string]$RestoreDatabase = "bighead_restore_verify",
  [int]$RtoSeconds = 28800
)

$ErrorActionPreference = "Stop"
$dumpPath = "/tmp/bighead-restore-test.dump"
$timer = [Diagnostics.Stopwatch]::StartNew()

function Invoke-DockerChecked {
  param([string[]]$DockerArguments)
  & docker @DockerArguments
  if ($LASTEXITCODE -ne 0) {
    throw "docker command failed with exit code $LASTEXITCODE"
  }
}

try {
  $health = & docker inspect -f "{{.State.Health.Status}}" $Container 2>$null
  if ($LASTEXITCODE -ne 0 -or $health -ne "healthy") {
    throw "Local Supabase database container is not healthy: $Container"
  }

  Invoke-DockerChecked @("exec", $Container, "rm", "-f", $dumpPath)
  Invoke-DockerChecked @("exec", $Container, "pg_dump", "-U", "postgres", "-d", $SourceDatabase, "-Fc", "-n", "public", "-n", "private", "-n", "storage", "-n", "auth", "-f", $dumpPath)
  & docker exec $Container dropdb -U postgres --if-exists $RestoreDatabase | Out-Null
  Invoke-DockerChecked @("exec", $Container, "createdb", "-U", "postgres", "-T", "template0", $RestoreDatabase)
  $bootstrap = "drop schema public cascade; create schema extensions; create extension vector with schema extensions; create extension pgcrypto with schema extensions; create extension citext with schema extensions;"
  Invoke-DockerChecked @("exec", $Container, "psql", "-U", "postgres", "-d", $RestoreDatabase, "-v", "ON_ERROR_STOP=1", "-c", $bootstrap)
  Invoke-DockerChecked @("exec", $Container, "pg_restore", "-U", "supabase_admin", "-d", $RestoreDatabase, "--no-owner", "--no-privileges", "--exit-on-error", $dumpPath)

  $tableQuery = "select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r' order by c.relname"
  $tables = @(& docker exec $Container psql -U supabase_admin -d $SourceDatabase -Atqc $tableQuery)
  if ($LASTEXITCODE -ne 0 -or $tables.Count -ne 46) {
    throw "Expected 46 public tables in source, found $($tables.Count)"
  }

  foreach ($table in $tables) {
    if ($table -notmatch '^[a-z_][a-z0-9_]*$') { throw "Unsafe table name: $table" }
    $sourceCount = & docker exec $Container psql -U supabase_admin -d $SourceDatabase -Atqc "select count(*) from public.$table"
    $restoredCount = & docker exec $Container psql -U supabase_admin -d $RestoreDatabase -Atqc "select count(*) from public.$table"
    if ($LASTEXITCODE -ne 0 -or $sourceCount -ne $restoredCount) {
      throw "Row-count mismatch for public.$table (source=$sourceCount restored=$restoredCount)"
    }
  }

  $timer.Stop()
  if ($timer.Elapsed.TotalSeconds -gt $RtoSeconds) {
    throw "Restore exceeded RTO: $([math]::Round($timer.Elapsed.TotalSeconds, 2))s > ${RtoSeconds}s"
  }
  Write-Output "restore=PASS tables=46 elapsed_seconds=$([math]::Round($timer.Elapsed.TotalSeconds, 2)) rto_seconds=$RtoSeconds"
}
finally {
  & docker exec $Container dropdb -U postgres --if-exists $RestoreDatabase 2>$null | Out-Null
  & docker exec $Container rm -f $dumpPath 2>$null | Out-Null
}
