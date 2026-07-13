# ADR 0001 - Stack de fundacao da Sprint 1

## Status

Aceito

## Contexto

A Sprint 1 precisa permitir desenvolvimento paralelo de frontend e backend, isolamento multiapp, contratos compartilhados e evolucao segura para Supabase, Redis, filas e observabilidade.

## Decisao

- Monorepo com `pnpm` workspaces e `turbo`.
- Frontend com Next.js App Router, Tailwind CSS, Radix e TanStack Query/Table.
- API com FastAPI assincrona e Pydantic Settings.
- Worker dedicado com ARQ.
- Graficos com Recharts.
- Editor visual de workflow com `@xyflow/react` na Sprint 2.
- Contratos compartilhados em OpenAPI, tipos TypeScript gerados e Zod nas bordas.
- Observabilidade base com JSON logs e OpenTelemetry.

## Consequencias

- Frontend e backend podem evoluir sobre o mesmo contrato antes da persistencia real.
- ARQ simplifica Redis-first jobs e leases curtos.
- Recharts e `@xyflow/react` equilibram curva de implementacao e capacidade para dashboards/workflows.
- `uv` garante lockfile e reproducibilidade Python no mesmo workspace.
