# Observabilidade, SLOs e alertas

## Estado atual

A API expõe `/health/live` e `/health/ready`; readiness testa Postgres e Redis.
API e worker aceitam exportação OTLP e configuração Sentry. O ambiente local
possui OpenTelemetry Collector. Não há evidência de dashboards, alertas ou
retenção configurados em staging/produção.

## SLOs candidatos a validar em staging

| SLI | Objetivo | Janela |
|---|---:|---|
| disponibilidade das jornadas críticas | >= 99,5% | 30 dias |
| latência p95 de operação interativa | < 500 ms | 30 dias |
| readiness API | 100% durante janela de atendimento | 5 min |
| processamento de jobs | definir por fila/provider | pendente |
| webhook entregue sem dead-letter | definir com Produto | pendente |

99,5% em 30 dias corresponde a aproximadamente 3 h 36 min de error budget.
Isso é cálculo de planejamento, não disponibilidade medida.

## Sinais obrigatórios

- API: taxa, latência p50/p95/p99, 4xx/5xx por rota, readiness e saturação.
- Postgres: conexões/pool, CPU, IO, locks, WAL, storage, queries lentas e RLS.
- Redis/worker: heartbeat, fila, item mais antigo, duração, retry, lease expirado.
- Outbox/webhook: pending, retrying, delivered, dead-letter, idade e provider.
- Auth: login/recovery/OAuth/SMTP, erro e rate limit sem PII.
- Storage: upload/download, quarentena, scanner, signed URL e erro por bucket.
- Realtime: conexões, reconnect, lag, duplicação/ordenação quando instrumentados.
- Negócio: budgets/quotas e falhas de publicação/provider, sem payload sensível.
- Segurança: falha de autorização, portal rate limit, secret scan e audit gaps.

## Alertas iniciais propostos

Estes limiares precisam de baseline em staging antes de serem aprovados:

| Alerta | Condição inicial | Ação |
|---|---|---|
| API indisponível | readiness falha por 2 min | SEV-1/SEV-2 conforme alcance |
| erro elevado | 5xx > 2% por 5 min | investigar release/dependência |
| latência | p95 > 500 ms por 10 min | verificar DB/pool/provider |
| conexões DB | > 80% por 10 min | conter carga e investigar leak |
| fila atrasada | item mais antigo > 5 min | verificar workers/provider |
| dead-letter | qualquer item crítico ou crescimento | reconciliar por event ID |
| backup atrasado | restore point > 24 h | bloquear release/go-live |
| Storage/scanner | falha sustentada por 5 min | bloquear download/promoção |

## Dashboard mínimo

1. Saúde geral e error budget.
2. API por rota/tenant sem expor identificador pessoal.
3. Postgres/Supabase, Redis e workers.
4. Outbox, webhook, privacy e providers.
5. Auth, Storage e Realtime.
6. Release annotations para correlacionar regressão.

## Validação

- [ ] OTLP/Sentry recebem evento sintético em staging.
- [ ] Logs possuem trace ID e redaction de secrets/PII.
- [ ] Alertas chegam ao canal e responsável correto.
- [ ] Runbook está ligado a cada alerta.
- [ ] Um alerta é disparado e resolvido em game day.
- [ ] Retenção e acesso a logs/audit atendem política aprovada.
- [ ] Métricas Supabase/Logs Explorer ou integração equivalente estão ativas.
