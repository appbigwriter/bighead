param(
  [string]$Container = "supabase_db_bighead-local",
  [string]$SourceDatabase = "postgres",
  [string]$RestoreDatabase = "",
  [int]$ExpectedPublicTables = 55,
  [int]$RtoSeconds = 28800
)

$ErrorActionPreference = "Stop"
if (-not $RestoreDatabase) { $RestoreDatabase = "bighead_restore_verify_$PID" }
if ($SourceDatabase -notmatch '^[a-z_][a-z0-9_]*$') { throw "Unsafe source database name" }
if ($RestoreDatabase -notmatch '^[a-z_][a-z0-9_]*$') { throw "Unsafe restore database name" }
if ($RestoreDatabase -eq $SourceDatabase -or $RestoreDatabase -match '^(postgres|template0|template1)$') {
  throw "Restore database must be a disposable, non-system database distinct from the source"
}
$dumpPath = "/tmp/bighead-restore-test-$PID.dump"
$snapshotSqlPath = "/tmp/bighead-restore-snapshot-$PID.sql"
$snapshotMetaPath = "/tmp/bighead-restore-snapshot-$PID.meta"
$snapshotBackendPid = $null
$restoreCreated = $false
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

  Invoke-DockerChecked @("exec", $Container, "rm", "-f", $dumpPath, $snapshotMetaPath)
  Invoke-DockerChecked @("cp", "ops/restore-snapshot.sql", "${Container}:${snapshotSqlPath}")
  $keeperCommand = "psql -U postgres -d $SourceDatabase -Atq -f $snapshotSqlPath > $snapshotMetaPath"
  Invoke-DockerChecked @("exec", "-d", $Container, "sh", "-c", $keeperCommand)
  $snapshotMeta = ""
  for ($attempt = 0; $attempt -lt 50 -and -not $snapshotMeta; $attempt++) {
    Start-Sleep -Milliseconds 100
    $snapshotLine = & docker exec $Container sh -c "head -n 1 $snapshotMetaPath 2>/dev/null"
    $snapshotMeta = "$snapshotLine".Trim()
  }
  if ($snapshotMeta -notmatch '^(\d+):([0-9A-F-]+)$') { throw "Could not acquire consistent source snapshot" }
  $snapshotBackendPid = $Matches[1]
  $snapshotId = $Matches[2]
  Invoke-DockerChecked @("exec", $Container, "pg_dump", "-U", "postgres", "-d", $SourceDatabase, "--snapshot=$snapshotId", "-Fc", "-n", "public", "-n", "private", "-n", "storage", "-n", "auth", "-f", $dumpPath)
  $destinationExists = & docker exec $Container psql -U postgres -d $SourceDatabase -Atqc "select 1 from pg_database where datname='$RestoreDatabase'"
  if ($LASTEXITCODE -ne 0) { throw "Could not verify restore destination" }
  if ($destinationExists -eq "1") { throw "Restore destination already exists; refusing to drop or overwrite it" }
  Invoke-DockerChecked @("exec", $Container, "createdb", "-U", "postgres", "-T", "template0", $RestoreDatabase)
  $restoreCreated = $true
  $bootstrap = "drop schema public cascade; create schema extensions; create extension vector with schema extensions; create extension pgcrypto with schema extensions; create extension citext with schema extensions;"
  Invoke-DockerChecked @("exec", $Container, "psql", "-U", "postgres", "-d", $RestoreDatabase, "-v", "ON_ERROR_STOP=1", "-c", $bootstrap)
  # The local `postgres` role intentionally cannot SET ROLE to every managed
  # Supabase owner. Keep ACLs, but let supabase_admin own restored objects.
  Invoke-DockerChecked @("exec", $Container, "pg_restore", "-U", "supabase_admin", "-d", $RestoreDatabase, "--no-owner", "--exit-on-error", $dumpPath)

  $tableQuery = "select n.nspname||'.'||c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname in ('public','private','storage','auth') and c.relkind='r' order by 1"
  $snapshotPrefix = "begin isolation level repeatable read read only; set transaction snapshot '$snapshotId'; "
  $tables = @(& docker exec $Container psql -U postgres -d $SourceDatabase -Atq -c "${snapshotPrefix}${tableQuery}; commit;")
  $publicCount = @($tables | Where-Object { $_ -like "public.*" }).Count
  if ($LASTEXITCODE -ne 0 -or $publicCount -ne $ExpectedPublicTables) {
    throw "Expected $ExpectedPublicTables public tables in source, found $publicCount"
  }

  foreach ($qualifiedTable in $tables) {
    if ($qualifiedTable -notmatch '^(public|private|storage|auth)\.[a-z_][a-z0-9_]*$') { throw "Unsafe table name: $qualifiedTable" }
    $integrityQuery = "select count(*)||':'||coalesce(md5(string_agg(md5(row_to_json(t)::text),'' order by md5(row_to_json(t)::text))),'empty') from $qualifiedTable t"
    $sourceSignature = & docker exec $Container psql -U postgres -d $SourceDatabase -Atq -c "${snapshotPrefix}${integrityQuery}; commit;"
    $restoredSignature = & docker exec $Container psql -U postgres -d $RestoreDatabase -Atqc $integrityQuery
    if ($LASTEXITCODE -ne 0 -or $sourceSignature -ne $restoredSignature) {
      throw "Integrity mismatch for $qualifiedTable"
    }
  }

  $catalogQuery = "select jsonb_build_object('rls',coalesce((select md5(string_agg(n.nspname||'.'||c.relname,',' order by n.nspname,c.relname)) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname in ('public','private','storage','auth') and c.relkind='r' and c.relrowsecurity),'empty'),'policies',coalesce((select md5(string_agg(pn.nspname||'.'||pc.relname||':'||p.polname||':'||p.polcmd::text||':'||p.polpermissive::text||':'||p.polroles::text||':'||coalesce(pg_get_expr(p.polqual,p.polrelid),'')||':'||coalesce(pg_get_expr(p.polwithcheck,p.polrelid),''),',' order by pn.nspname,pc.relname,p.polname)) from pg_policy p join pg_class pc on pc.oid=p.polrelid join pg_namespace pn on pn.oid=pc.relnamespace where pn.nspname in ('public','private','storage','auth')),'empty'),'functions',coalesce((select md5(string_agg(md5(pg_get_functiondef(p.oid)),',' order by n.nspname,p.proname,p.oid)) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname in ('public','private','storage','auth')),'empty'),'triggers',coalesce((select md5(string_agg(pg_get_triggerdef(t.oid),',' order by n2.nspname,c2.relname,t.tgname)) from pg_trigger t join pg_class c2 on c2.oid=t.tgrelid join pg_namespace n2 on n2.oid=c2.relnamespace where n2.nspname in ('public','private','storage','auth') and not t.tgisinternal),'empty'),'indexes',coalesce((select md5(string_agg(pg_get_indexdef(i.indexrelid),',' order by n3.nspname,c3.relname,ic.relname)) from pg_index i join pg_class c3 on c3.oid=i.indrelid join pg_class ic on ic.oid=i.indexrelid join pg_namespace n3 on n3.oid=c3.relnamespace where n3.nspname in ('public','private','storage','auth')),'empty'),'client_acl',coalesce((select md5(string_agg(table_schema||'.'||table_name||':'||grantee||':'||privilege_type,',' order by table_schema,table_name,grantee,privilege_type)) from information_schema.role_table_grants where table_schema in ('public','private','storage','auth') and grantee in ('anon','authenticated','service_role')),'empty'))"
  $sourceCatalog = & docker exec $Container psql -U postgres -d $SourceDatabase -Atq -c "${snapshotPrefix}${catalogQuery}; commit;"
  $restoredCatalog = & docker exec $Container psql -U postgres -d $RestoreDatabase -Atqc $catalogQuery
  if ($LASTEXITCODE -ne 0 -or $sourceCatalog -ne $restoredCatalog) {
    throw "Catalog security/object signature differs after restore (source=$sourceCatalog restored=$restoredCatalog)"
  }

  $timer.Stop()
  if ($timer.Elapsed.TotalSeconds -gt $RtoSeconds) {
    throw "Restore exceeded RTO: $([math]::Round($timer.Elapsed.TotalSeconds, 2))s > ${RtoSeconds}s"
  }
  Write-Output "restore=PASS public_tables=$ExpectedPublicTables protected_schemas=4 integrity=hash catalog=matched elapsed_seconds=$([math]::Round($timer.Elapsed.TotalSeconds, 2)) rto_seconds=$RtoSeconds"
}
finally {
  if ($snapshotBackendPid -and $snapshotBackendPid -match '^\d+$') {
    & docker exec $Container psql -U postgres -d $SourceDatabase -Atqc "select pg_terminate_backend($snapshotBackendPid)" 2>$null | Out-Null
  }
  if ($restoreCreated) {
    & docker exec $Container dropdb -U postgres --if-exists $RestoreDatabase 2>$null | Out-Null
  }
  & docker exec $Container rm -f $dumpPath $snapshotSqlPath $snapshotMetaPath 2>$null | Out-Null
}
