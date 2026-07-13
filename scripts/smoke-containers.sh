#!/usr/bin/env sh
set -eu

compose_file="${COMPOSE_FILE:-compose.production.yml}"
timeout_seconds="${SMOKE_TIMEOUT_SECONDS:-180}"
elapsed=0

while [ "$elapsed" -lt "$timeout_seconds" ]; do
  unhealthy="$(docker compose -f "$compose_file" ps --format json | grep -c '"Health":"unhealthy"' || true)"
  api_status="$(curl -fsS -o /dev/null -w '%{http_code}' "${SMOKE_API_URL:-http://127.0.0.1:8000/health/ready}" || true)"
  web_status="$(curl -fsS -o /dev/null -w '%{http_code}' "${SMOKE_WEB_URL:-http://127.0.0.1:3000}" || true)"
  worker_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "${COMPOSE_PROJECT_NAME:-bighead}-worker-1" 2>/dev/null || true)"

  if [ "$unhealthy" -eq 0 ] && [ "$api_status" = "200" ] && [ "$web_status" = "200" ] && [ "$worker_health" = "healthy" ]; then
    echo "Container smoke test passed."
    exit 0
  fi
  sleep 5
  elapsed=$((elapsed + 5))
done

docker compose -f "$compose_file" ps
docker compose -f "$compose_file" logs --tail=100 api worker web
echo "Container smoke test timed out after ${timeout_seconds}s." >&2
exit 1

