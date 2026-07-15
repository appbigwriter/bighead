# Sprint 3 - Status de implementacao

Atualizado em 2026-07-14, America/Sao_Paulo.

## Resultado local comprovado

- 41 migrations reproduziveis criam 46 tabelas de dominio e oito tabelas de
  integracao, totalizando 54 tabelas publicas. RLS, grants e isolamento
  multi-tenant permanecem ativos.
- A rodada integral de `db:verify` passou: reset por migrations, 20 arquivos e
  290 assercoes pgTAP, lint e advisors sem achados. A integracao Supabase passou
  13 testes e a integracao real de outbox passou um teste adicional.
- OpenAPI canonico sincronizado: 89 paths.
- Suite consolidada atual: API 99 PASS/14 integracoes opt-in SKIP; worker 60
  PASS/2 integracoes opt-in SKIP; web 360 PASS; contratos 1 PASS; UI 3 PASS.
- Lint, typecheck, build, fixture guard e demais guards: PASS. `pip-audit` nao
  encontrou vulnerabilidades conhecidas nas dependencias auditaveis; pacotes
  locais nao puderam ser auditados. `npm audit` ficou inconclusivo porque o
  endpoint do registry respondeu HTTP 410, portanto nao ha PASS de auditoria npm.
- Realtime reconnect sem MSW: desktop e mobile 2/2 PASS. O teste comprova gap
  sem remount, nova subscription, reconciliacao sem duplicata, replay
  idempotente e canal Beacon vivo sem vazamento Atlas. Revisao independente:
  PASS.
- Auth/SMTP/config: callback PKCE, reset, cookies, protecao contra open redirect,
  rejeicao de chave privilegiada em bundle publico e matriz staging/producao
  passaram 31 testes focados e revisao independente.
- Gateway multi-LLM: adapters OpenAI, Anthropic e Google, timeout, JSON Schema,
  circuit breaker, fallback por capability, idempotencia e redaction passaram
  testes locais com transportes falsos e revisao independente.
- CRM: conexoes multi-tenant, segredo server-derived, endpoint allowlist, DNS
  resolvido uma vez e IP validado pinado, sync incremental, cursor monotonic,
  lease com fencing, retry/DLQ, inbox HMAC e mapping transacional passaram
  testes locais e revisao independente.
- Performance local: HNSW com 5.000 vetores, p95 3,158 ms; notificacoes 103,735
  ms; salas 107,055 ms; tarefas 115,436 ms. Orcamento: 500 ms.
- Restore local: PASS em 47,96 s; 54 tabelas publicas, quatro schemas, hashes de
  dados e assinatura de catalogo equivalentes. RTO local: 8 h.
- Imagens `bighead-web`, `bighead-api` e `bighead-worker` construidas; runtime
  nao-root UID 10001 e imports basicos validados. Compose de producao validado.

## Criterios fechados nesta rodada

- BH-S3-02: reconnect Realtime nao duplica mensagens.
- BH-S3-05: mudanca de modelo/dimensao usa reindexacao controlada com indices
  concorrentes e ativacao fail-closed.
- Auth web/config e fronteira SMTP estao prontas para configuracao Supabase
  Cloud.
- CRM provider-agnostic e gateway multi-LLM possuem wiring local, contratos,
  jobs, RLS, idempotencia e testes deterministas.

## Pendencias externas para go-live

- Criar projetos/servicos reais: Supabase Cloud, hosting web/API/worker, Redis,
  dominio/TLS, SMTP, scanner antimalware, OTLP/Sentry e secret manager.
- Informar credenciais e endpoints aprovados para CRM e LLMs; executar
  round-trip real, quota, billing, rate limit, fallback e reconciliacao.
- Aplicar migrations em staging; executar smoke, E2E completo sem MSW,
  observabilidade, carga e restore de backup gerenciado incluindo blobs Storage.
- Medir RPO/RTO e disponibilidade no ambiente remoto; obter aprovacoes de
  Produto, Engenharia e Seguranca.

## Limites da evidencia

- Testes com MockTransport comprovam contratos e falhas deterministas, nao o
  comportamento dos providers externos.
- Restore e performance locais nao comprovam rede, pooler, volume, blobs ou
  backup gerenciado de staging.
- O E2E mock passou 34/34 e o E2E real sem MSW passou 20/20, ambos em desktop e
  mobile com Axe. Essa prova e local; nao substitui E2E em staging/deploy.
- Efeitos externos continuam at-least-once quando o provider nao oferece chave
  idempotente; ledger, fencing e reconciliacao evitam duplicacao local.

## Retomada de 2026-07-14

- A cobertura T01-T56 via fallback `ScreenExperience` foi restaurada sem remover
  as experiencias especificas ja implementadas.
- O onboarding autenticado passou a consumir o contrato canonico `organizationId`,
  persistir o tenant correto e redirecionar no mesmo host; a jornada real cria
  uma identidade sem membership e conclui a organizacao pela UI.
- Primitives compartilhados de UI, contraste WCAG e o seletor usado pelo E2E
  foram corrigidos; as suites web, UI e Playwright acima cobrem as regressoes.
- A fronteira de dados continua permitindo trocar MSW pela API sem alteracoes
  nos componentes; o E2E real sem MSW comprova as jornadas representativas.

## Hardening mantido de 2026-07-13

- `organization_id` tornou-se imutavel em todas as 52 tabelas publicas que
  possuem essa chave. O teste adversarial comprova que um usuario membro de dois
  tenants nao consegue reparentear um documento entre eles.
- Claims do `event_outbox` agora recebem `lease_token` UUID renovado e
  `ack`/`nack` exigem worker, token e lease ainda ativa. Reutilizar o mesmo nome
  de worker nao permite que um consumidor obsoleto finalize a nova claim.
- Secret guard passou a ignorar caches conhecidos e falhar fechado em
  `EPERM`/`EACCES`; handoff automatizado agora cobre T10-T56.
- Revisoes independentes de seguranca e verificacao deram PASS para esses fixes.

Conclusao: codigo local apto a seguir para staging controlado. Producao publica
continua bloqueada pelas credenciais, infraestrutura e provas remotas acima.
