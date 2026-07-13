# Runbook de staging e produção

## Objetivo e estado

Validar uma release em staging isolado antes de qualquer promoção. O repositório
não define hoje uma plataforma de deploy para web, API ou worker; o comando
aprovado de cada serviço deve ser registrado no ticket da release antes da
janela. Ausência desse registro bloqueia promoção.

## Pré-requisitos por ambiente

- Projeto Supabase dedicado e referência confirmada por duas pessoas.
- Redis dedicado, sem compartilhamento de fila ou namespace.
- Buckets privados e policies conferidos.
- URLs HTTPS, CORS, callbacks Auth e SMTP configurados para o ambiente.
- OTLP e Sentry apontando para projetos do ambiente.
- Secrets presentes no secret manager e testados sem revelar valores.
- Backup gerenciado ou PITR verificado conforme o plano contratado.
- Responsáveis de Produto, Engenharia, Plataforma e Segurança identificados.
- Comandos de deploy e rollback da plataforma de web/API/worker documentados.

O catálogo de variáveis está em [PROVISIONAMENTO.md](../PROVISIONAMENTO.md).

## Validação local obrigatória

Executar em commit limpo e registrar logs/artefatos:

```powershell
pnpm install --frozen-lockfile
uv sync --all-packages --locked
pnpm contracts:check
node scripts/check-no-secrets.mjs
node scripts/verify-screen-contracts.mjs
pnpm frontend:fixture-guard
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm audit
pnpm db:verify
pnpm test:integration:supabase
pnpm test:integration:outbox
pnpm test:e2e:real
pnpm db:performance-test
pnpm db:restore-test
```

O comando `pnpm test:e2e:real` executa o E2E desktop/mobile sem MSW. Um PASS
anterior não substitui a execução no commit candidato.

## Promoção para staging

1. Fixar `RELEASE_SHA`, referência do projeto e janela no ticket.
2. Confirmar que o CLI está autenticado no perfil de staging e conferir a
   referência exibida. Não reutilizar sessão de produção.
3. Inspecionar migrations locais e remotas:

   ```powershell
   pnpm exec supabase migration list
   pnpm exec supabase db push --dry-run
   ```

4. Revisar cada migration pendente, locks esperados, tempo estimado e
   compatibilidade com a versão atualmente implantada.
5. Registrar restore point/backup conforme o runbook de backup.
6. Com aprovação do segundo operador, aplicar migrations uma única vez:

   ```powershell
   pnpm exec supabase db push
   ```

   Não usar `--include-seed` em staging persistente ou produção sem plano de
   dados explicitamente aprovado.
7. Implantar API e worker com o comando aprovado da plataforma; implantar web
   somente após API e worker estarem prontos.
8. Verificar `GET /health/live` e `GET /health/ready`. Readiness exige Database e
   Redis `ok`.
9. Executar smoke autenticado com tenant de teste: login, membership/RLS,
   leitura/escrita reversível, signed Storage e processamento de um job.
10. Exercitar webhook controlado, retry/dead-letter e recuperação de lease.
11. Executar E2E sem MSW, carga representativa e restore de backup de staging.
12. Observar métricas e logs pelo período definido no ticket. Qualquer critério
    de abortar aciona rollback/forward-fix.

## Promoção para produção

Produção só pode repetir um artefato e migrations já validados em staging. Antes
da escrita:

- [ ] Evidência de staging anexada.
- [ ] Backup/restore point e janela de recuperação confirmados.
- [ ] Mudança compatível com deploy gradual ou ordem de serviços definida.
- [ ] Alertas e responsáveis de plantão ativos.
- [ ] Produto, Engenharia e Segurança aprovaram a release.
- [ ] Critérios de abortar e forward-fix ensaiados.

Repetir inspeção `migration list` e `db push --dry-run` no projeto de produção,
com perfil separado. Aplicar somente após confirmação verbal/escrita dos dois
operadores. Não executar reset, seed, teste de carga destrutivo ou restore-test
local contra produção.

## Critérios de abortar

- Referência de projeto, commit ou lista de migrations divergente.
- Backup/PITR indisponível ou restore point fora do RPO acordado.
- Lock não previsto, migration acima da janela ou erro parcial.
- Readiness degradado, erro 5xx sustentado, fila crescendo ou falha de Auth/RLS.
- Inconsistência cross-tenant, perda de auditoria ou exposição de secret.
- Smoke de Storage, webhook, privacy ou worker sem resultado idempotente.

## Evidência a anexar

Commit/artefato, migrations antes/depois, horários, operadores, aprovações,
health/smokes, dashboards, alertas, restore point, decisão final e ações abertas.
