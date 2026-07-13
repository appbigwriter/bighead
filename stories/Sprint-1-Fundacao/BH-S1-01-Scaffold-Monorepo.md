# BH-S1-01 - Scaffold do monorepo

**Dominio:** Infra/Frontend/Backend  
**Prioridade:** bloqueadora  
**Depende de:** N/A  
**Estimativa:** 8 pontos

## Historia

Como equipe de desenvolvimento, quero um monorepo com fronteiras claras para que frontend, API, workers e contratos evoluam sem duplicacao ou acoplamento acidental.

## Escopo

- Criar workspace `pnpm` com `apps/web`, `apps/api`, `apps/worker`, `packages/contracts`, `packages/ui` e `packages/config`.
- Configurar Next.js App Router + TypeScript strict em `apps/web`.
- Configurar FastAPI assíncrono em `apps/api`, com modulos por dominio e `/health/live` e `/health/ready`.
- Configurar processo worker separado, sem executar jobs dentro do processo HTTP.
- Criar `supabase/` para migrations, seed e testes pgTAP.
- Criar `docs/adr/`, `scripts/`, `.github/workflows/`, `.editorconfig`, `.gitignore` e READMEs.
- Definir comandos raiz: `dev`, `build`, `lint`, `typecheck`, `test`, `test:e2e`, `db:start`, `db:reset`.

## Estrutura minima

```text
apps/web
apps/api/src/{identity,organizations,collaboration,tasks,orchestration,agents,skills,workflows,approvals,artifacts,memory,crm,content,experiments,analytics,notifications,audit}
apps/worker/src
packages/contracts
packages/ui
packages/config
supabase/{migrations,seed.sql,tests}
```

## Invariantes

- `apps/web` nao importa codigo Python ou credenciais server-only.
- `apps/api` e `apps/worker` compartilham schemas por pacote Python interno, nao por copia.
- Rotas, services e repositories permanecem separados por dominio.
- Nenhum segredo ou endpoint real e commitado.

## Criterios de aceite

- [ ] `pnpm install` conclui em clone limpo e gera lockfile.
- [ ] Frontend, API e worker iniciam com um unico comando documentado.
- [ ] `/health/live` responde sem consultar dependencias; `/health/ready` verifica banco e Redis.
- [ ] TypeScript strict e Python type checking estao ativos.
- [ ] Build de producao dos tres processos conclui.
- [ ] README raiz explica arquitetura e comandos em ate 10 minutos de onboarding.

## Casos de borda e testes

- [ ] Porta ocupada produz erro claro.
- [ ] Redis ou banco indisponivel deixa readiness falhar sem derrubar liveness.
- [ ] Windows e CI Linux usam comandos equivalentes.

## Fora de escopo

- Implementar telas, autenticacao real, migrations de dominio ou chamadas de LLM.
