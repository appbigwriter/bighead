# Dependencias e bibliotecas - BigHead V3

**Status:** proposta para revisao. Versoes devem ser fixadas no lockfile no momento do bootstrap; nao usar `latest` em producao.

## Frontend

| Pacote | Finalidade | Necessidade |
|---|---|---|
| `next`, `react`, `react-dom`, `typescript` | aplicacao App Router tipada | obrigatoria |
| `@supabase/supabase-js`, `@supabase/ssr` | Auth, sessao SSR, Storage e Realtime | obrigatoria |
| `tailwindcss` | tokens e composicao visual | proposta |
| `radix-ui` ou `@radix-ui/react-*` | primitivas acessiveis | proposta |
| `lucide-react` | icones | proposta |
| `react-hook-form`, `zod`, `@hookform/resolvers` | formularios e validacao | obrigatoria |
| `@tanstack/react-query` | estado remoto, retries e invalidacao | proposta |
| `@tanstack/react-table` | grids de tarefas, leads e auditoria | proposta |
| `zustand` | estado local complexo do editor | opcional |
| `tiptap` | editor rico de mensagens/artefatos | proposta |
| `react-dropzone` | anexos | proposta |
| `date-fns` | datas e SLA | proposta |
| `recharts` ou `echarts` | dashboards | proposta; escolher uma |
| `reactflow` | editor visual de workflows | fase 2 |
| `next-intl` | internacionalizacao | opcional/fase futura |
| `@sentry/nextjs` | erros e traces | proposta |

## Backend Python

| Pacote | Finalidade | Necessidade |
|---|---|---|
| `fastapi`, `uvicorn[standard]` | API ASGI | obrigatoria |
| `pydantic`, `pydantic-settings` | contratos e configuracao | obrigatoria |
| `sqlalchemy[asyncio]`, `asyncpg`, `alembic` | persistencia e migrations auxiliares | obrigatoria |
| `supabase` | Auth/Storage quando a API do Supabase for adequada | proposta |
| `pyjwt[crypto]` ou `python-jose[cryptography]` | validacao JWT; escolher uma | obrigatoria |
| `redis`, `arq` ou `dramatiq` | fila e workers; escolher um framework | obrigatoria |
| `httpx` | clientes HTTP assincronos | obrigatoria |
| `tenacity` | retries delimitados | proposta |
| `openai` | gateway OpenAI | conforme provedor |
| SDKs dos demais modelos | adaptadores de LLM | conforme provedores aprovados |
| `tiktoken` | estimativa/contagem de tokens | conforme modelos |
| `pgvector` | tipos vetoriais no ORM | obrigatoria para RAG |
| `python-multipart` | upload via API | obrigatoria |
| `python-magic` | deteccao de MIME | proposta |
| `bleach` | sanitizacao de HTML | proposta |
| `structlog` | logs estruturados | proposta |
| `opentelemetry-api`, `opentelemetry-sdk` e instrumentacoes | tracing e metricas | obrigatoria |
| `sentry-sdk[fastapi]` | captura de falhas | proposta |
| `prometheus-client` | metricas se nao usar collector gerenciado | opcional |

## Dados e infraestrutura

| Componente | Finalidade |
|---|---|
| Supabase Postgres | fonte de verdade transacional |
| Supabase Auth | identidade e sessao |
| Supabase Storage | artefatos e anexos privados |
| Supabase Realtime | mensagens, tarefas e notificacoes |
| `vector`/pgvector | embeddings e busca semantica |
| Redis | filas, leases curtos, cache e eventos efemeros |
| Secret manager | credenciais de providers e skills |
| Sentry e/ou OpenTelemetry Collector | observabilidade |
| Docker e Docker Compose | ambiente local e empacotamento |

## Qualidade e desenvolvimento

### Frontend

`eslint`, `prettier`, `eslint-config-next`, `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `playwright`, `axe-core`, `@axe-core/playwright`, `msw`.

### Backend

`pytest`, `pytest-asyncio`, `pytest-cov`, `respx`, `hypothesis`, `ruff`, `mypy`, `bandit`, `pip-audit`.

### Banco e contratos

Supabase CLI, `pgTAP`, SQLFluff, OpenAPI gerado pelo FastAPI, `openapi-typescript` para tipos do cliente e geracao de tipos Supabase. Testes obrigatorios devem cobrir RLS cross-tenant, state machine, idempotencia, concorrencia de leases e permissoes de Storage.

## Decisoes pendentes

- Monorepo (`pnpm` workspaces/Turborepo) ou repos separados.
- `arq` versus Dramatiq para workers.
- biblioteca de graficos e editor visual.
- provider de email, notificacoes, CRM e publicacao social.
- provedor de observabilidade e secret manager.
- modelos e dimensao de embeddings.
- estrategia de deploy: Vercel + container backend, ou infraestrutura unificada.

## Regras de supply chain

Fixar versoes, manter lockfiles, habilitar Dependabot/Renovate, gerar SBOM, verificar licencas, executar auditoria de dependencias no CI e nunca expor `service_role` ou chaves secretas em variaveis `NEXT_PUBLIC_*`.
