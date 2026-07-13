# BigHead production-readiness without external provider credentials

## Objective

Finish every production-readiness item that can be implemented and verified without
credentials for OAuth, SMTP, LLM, CRM, enrichment, campaign email or social providers.
External integrations must remain fail-closed, explicitly disabled and documented.

## Required outcomes

1. Replace the web E2E credential adapter with real per-user Supabase SSR authentication.
2. Make production fail closed when mocks, E2E credentials or placeholder secrets are configured.
3. Connect the web shell and supported commands to authenticated API calls; no production copy may claim mocks.
4. Add reproducible deployment artifacts for web, API and worker, with non-root containers and health checks.
5. Expand CI to verify database reset/pgTAP/advisors, real integrations, E2E, security audits and container builds where practical.
6. Wire OpenTelemetry/Sentry only when configured; expose operational health for API and worker.
7. Correct configuration drift, including signed URL TTL and production-only validation.
8. Add staging/production runbooks, release/rollback, incident response, backups, restore, alerting and provider handoff checklist.
9. Preserve all existing changes and secrets; do not deploy remotely or invent provider credentials.

## Acceptance

- Existing lint, typecheck, unit, build, contracts, fixture guard, secret guard and database gates pass.
- Real E2E uses user-scoped sessions without fixed E2E credentials in production code.
- Production startup rejects mock mode, placeholders and unsafe URLs/origins.
- Container images build and run health checks locally where the host supports it.
- Independent architecture, security and code review all return PASS or remaining blocks are external-only.

## External-only blockers

- Provider credentials and provider-side account/domain approval.
- Remote Supabase/staging/production project creation and dashboard settings.
- DNS, TLS, billing plan, SMTP reputation, OAuth consent and human go-live approval.
