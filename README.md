# BigHead

Base executavel da Sprint 1 para o sistema BigHead. Este workspace entrega o monorepo, contratos compartilhados, configuracao de ambiente, mocks, gates de qualidade e o esqueleto operacional de `web`, `api`, `worker` e stack local.

## Arquitetura

- `apps/web`: Next.js App Router, shell inicial, provider de mocks e cliente HTTP tipado.
- `apps/api`: FastAPI assincrona com health checks, configuracao validada e modulos por dominio.
- `apps/worker`: processo separado para jobs e heartbeats.
- `packages/contracts`: OpenAPI, tipos TypeScript gerados, fixtures e MSW.
- `packages/ui`: componentes base reutilizaveis.
- `packages/config`: configuracoes compartilhadas de TypeScript, ESLint e Prettier.
- `packages/pycore`: modelos Python compartilhados entre API e worker.
- `supabase/`: configuracao local, migrations iniciais, seed e testes.

## Requisitos

- Node `24.11.1`
- pnpm `10.26.2`
- Python `3.14.0`
- `uv` `0.11.15+`
- Docker Desktop

## Onboarding em menos de 10 minutos

1. Copie `.env.example` para `.env`.
2. Copie `apps/web/.env.example` para `apps/web/.env.local`.
3. Copie `apps/api/.env.example` e `apps/worker/.env.example` para seus respectivos `.env`.
4. Rode `pnpm install`.
5. Rode `uv sync --all-packages --all-extras`.
6. Rode `pnpm db:start`.
7. Rode `pnpm dev`.

## Comandos principais

- `pnpm dev`: sobe frontend, API, worker e watch de contratos.
- `pnpm build`: build de producao de web, pacotes TS e build Python.
- `pnpm lint`: lint de TypeScript e Python.
- `pnpm typecheck`: typecheck de TS e mypy.
- `pnpm test`: testes unitarios, contratos e API.
- `pnpm test:e2e`: smoke E2E da shell inicial.
- `pnpm db:start`: inicia Supabase local, Redis e collector OTEL.
- `pnpm db:reset`: reseta banco local do Supabase.

## Health checks

- Liveness: [http://localhost:8000/health/live](http://localhost:8000/health/live)
- Readiness: [http://localhost:8000/health/ready](http://localhost:8000/health/ready)

`/health/live` nao consulta dependencias. `/health/ready` verifica Postgres e Redis sem derrubar o processo HTTP.

## Proximos artefatos desta Sprint

- [Provisionamento](docs/PROVISIONAMENTO.md)
- [Contratos de tela](docs/CONTRATOS-DE-TELA.md)
- [ADR da stack](docs/adr/0001-foundation-stack.md)
