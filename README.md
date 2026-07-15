# BigHead

Workspace executavel do BigHead, com frontend, API, worker, contratos, banco multi-tenant e stack local equivalente aos processos de producao.

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
- `pnpm test:e2e:real`: E2E real que inicia API/web isolados em `8010/3101`.
- `pnpm test:e2e:deployed`: reutiliza a mesma suíte real contra web/API já ativos
  em `127.0.0.1:3002/8000`, sem `webServer`, build ou MSW. Requer Supabase local,
  Redis, seed determinístico e containers saudáveis; aceita
  `BIGHEAD_DEPLOYED_WEB_URL` e `BIGHEAD_DEPLOYED_API_URL` para sobrescrever URLs.
- `pnpm db:start`: inicia Supabase local, Redis e collector OTEL.
- `pnpm db:reset`: reseta banco local do Supabase.

## Simulacao local de producao

Com o Docker Desktop ativo, o script abaixo inicia o Supabase local e executa as imagens de producao do frontend, API e worker, mais Redis e ClamAV. O proxy TLS/Caddy nao e iniciado localmente porque essa responsabilidade pertence ao Easypanel no deploy.

```powershell
.\scripts\start-local-stack.ps1 up
```

- Frontend: [http://127.0.0.1:3002/login](http://127.0.0.1:3002/login)
- API: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Supabase Studio: [http://127.0.0.1:55323](http://127.0.0.1:55323)
- Mailpit: [http://127.0.0.1:55324](http://127.0.0.1:55324)

Use `status`, `logs` ou `down` no lugar de `up` para inspecionar ou encerrar os processos da aplicacao. A porta pode ser alterada com `-WebPort`; o padrao e `3002` para nao conflitar com outros projetos. As credenciais e chaves locais sao obtidas dinamicamente do Supabase CLI e nao sao persistidas pelo script.

## Health checks

- Liveness: [http://localhost:8000/health/live](http://localhost:8000/health/live)
- Readiness: [http://localhost:8000/health/ready](http://localhost:8000/health/ready)

`/health/live` nao consulta dependencias. `/health/ready` verifica Postgres e Redis sem derrubar o processo HTTP.

## Proximos artefatos desta Sprint

- [Provisionamento](docs/PROVISIONAMENTO.md)
- [Contratos de tela](docs/CONTRATOS-DE-TELA.md)
- [ADR da stack](docs/adr/0001-foundation-stack.md)
