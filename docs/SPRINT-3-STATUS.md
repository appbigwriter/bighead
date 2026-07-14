# Sprint 3 - Status de implementacao

Atualizado em 2026-07-13, America/Sao_Paulo.

## Resultado local comprovado

- 39 migrations reproduziveis criam 46 tabelas de dominio e oito tabelas de
  integracao, totalizando 54 tabelas publicas. RLS, grants e isolamento
  multi-tenant permanecem ativos.
- A ultima rodada integral de `db:verify` permanece PASS. O estado atual possui
  18 arquivos e 275 assercoes pgTAP; nesta retomada, os testes alterados de
  seguranca/outbox passaram 35/35, e DB lint/advisors ficaram sem achados. O
  reset/pgTAP integral nao foi reexecutado porque o sandbox negou o pipe Docker.
- OpenAPI canonico sincronizado: 89 paths.
- Suite consolidada atual: API 98 PASS/13 integracoes opt-in SKIP; worker 60
  PASS/2 integracoes opt-in SKIP; web 332 PASS; contratos 1 PASS; UI 3 PASS.
- Lint, Bandit, typecheck, build e auditoria de dependencias: PASS. Nenhuma
  vulnerabilidade conhecida foi encontrada.
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
- Performance local: HNSW com 5.000 vetores, p95 2,592 ms; notificacoes 65,241
  ms; salas 70,934 ms; tarefas 66,81 ms. Orcamento: 500 ms.
- Restore local: PASS em 37,53 s; 54 tabelas publicas, quatro schemas, hashes de
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
- O full E2E real registrado anteriormente passou 20/20. A reexecucao desta
  retomada foi bloqueada antes da primeira pagina por `spawn EPERM` ao iniciar o
  Chromium; nao ha evidencia de regressao funcional, mas o gate atual permanece
  sem nova prova desktop/mobile/Axe.
- Efeitos externos continuam at-least-once quando o provider nao oferece chave
  idempotente; ledger, fencing e reconciliacao evitam duplicacao local.

## Hardening de 2026-07-13

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
