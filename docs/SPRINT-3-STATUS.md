# Sprint 3 - Status de implementacao

Atualizado em 2026-07-13, America/Sao_Paulo.

## Resultado local comprovado

- 35 migrations reproduziveis criam 46 tabelas de dominio e oito tabelas de
  integracao, totalizando 54 tabelas publicas. RLS, grants e isolamento
  multi-tenant permanecem ativos.
- `pnpm db:verify`: PASS; 16 arquivos e 249 assercoes pgTAP, lint e advisors
  sem achados.
- OpenAPI canonico sincronizado: 83 paths.
- Suite consolidada: API 86 PASS/12 integracoes opt-in SKIP; worker 49 PASS/2
  integracoes opt-in SKIP; web 242 PASS; contratos 1 PASS; UI 3 PASS.
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
- O full E2E real registrado anteriormente passou 18/18; apos as mudancas mais
  recentes foi reexecutado apenas o focused Realtime 2/2, por decisao de reduzir
  tempo ate o staging.
- Efeitos externos continuam at-least-once quando o provider nao oferece chave
  idempotente; ledger, fencing e reconciliacao evitam duplicacao local.

Conclusao: codigo local apto a seguir para staging controlado. Producao publica
continua bloqueada pelas credenciais, infraestrutura e provas remotas acima.
