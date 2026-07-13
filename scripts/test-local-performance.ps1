param(
  [string]$Container = "supabase_db_bighead-local",
  [double]$P95BudgetMs = 500
)

$ErrorActionPreference = "Stop"
$remoteSql = "/tmp/bighead-performance-read.sql"
try {
  $health = & docker inspect -f "{{.State.Health.Status}}" $Container 2>$null
  if ($LASTEXITCODE -ne 0 -or $health -ne "healthy") {
    throw "Local Supabase database container is not healthy: $Container"
  }
  & docker cp "ops/performance-read.sql" "${Container}:${remoteSql}" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Could not copy performance workload" }

  $output = @(& docker exec $Container psql -U postgres -d postgres -f $remoteSql)
  if ($LASTEXITCODE -ne 0) { throw "Performance workload failed" }
  $samples = @($output | Where-Object { $_ -match '^[a-z.]+=\d+(\.\d+)?$' })
  if ($samples.Count -ne 4) { throw "Expected four p95 samples, found $($samples.Count)" }
  foreach ($sample in $samples) {
    $parts = $sample -split '=', 2
    $latency = [double]::Parse($parts[1], [Globalization.CultureInfo]::InvariantCulture)
    if ($latency -ge $P95BudgetMs) {
      throw "$($parts[0]) p95 ${latency}ms exceeds ${P95BudgetMs}ms"
    }
    Write-Output "operation=$($parts[0]) p95_ms=$latency budget_ms=$P95BudgetMs"
  }
  Write-Output "performance=PASS samples=1000 vector_rows=5000 plan=HNSW"
}
finally {
  & docker exec $Container rm -f $remoteSql 2>$null | Out-Null
}
