# Handoff de APIs e providers externos

## Objetivo

Nenhum provider é considerado pronto por possuir apenas variável de ambiente.
Cada integração exige owner, contrato, credencial por ambiente, smoke, limites,
observabilidade, fallback e procedimento de revogação.

## Checklist por provider

- [ ] Owner técnico e owner de negócio.
- [ ] Sandbox/staging separado de produção.
- [ ] Base URL, região, versão da API e SLA registrados.
- [ ] Secret no secret manager, least privilege, expiração e rotação.
- [ ] Allowlist de origem/destino e validação SSRF quando aplicável.
- [ ] Timeout, retry, backoff, circuit breaker e limite de concorrência.
- [ ] Idempotency key e semântica at-least-once documentadas.
- [ ] Rate limits, quotas, custo e alertas.
- [ ] Schemas de request/response e redaction de logs.
- [ ] Tratamento de 401/403/409/422/429/5xx e indisponibilidade.
- [ ] Webhook: HMAC, timestamp, event ID, replay e rotação de secret.
- [ ] Teste de contrato e round-trip no ambiente alvo.
- [ ] Fallback/degradação e reconciliação manual.
- [ ] Contato/status page e runbook de incidente.
- [ ] Aprovação de privacidade, retenção e residência de dados.

## Inventário e estado

| Integração | Variáveis/componentes | Estado comprovado |
|---|---|---|
| Supabase Database/Auth/Storage | `SUPABASE_*`, `DATABASE_URL`, `DIRECT_DATABASE_URL` | integração local real; remoto pendente |
| Redis | `REDIS_URL`, worker/outbox | smoke local real; gerenciado remoto pendente |
| OAuth Google/Microsoft | client ID/secret, callbacks | configuração e round-trip remotos pendentes |
| SMTP/Auth email | `SMTP_*` | provider e entregabilidade pendentes |
| LLM/embedding | provider/model/API keys | seleção, fallback, custo e round-trip pendentes |
| CRM/enriquecimento | `CRM_*`, `ENRICHMENT_API_KEY` | provider externo pendente |
| Email/social publishing | respectivas API keys | provider externo pendente |
| Malware scanner | `MALWARE_SCANNER_URL` e `MALWARE_SCANNER_API_KEY` no worker | adapter Bearer, claim/lease/backoff testados; serviço remoto pendente |
| Webhooks de saída | Vault secret, HMAC, ledger/worker | contrato/worker testados; endpoint externo pendente |
| OTLP/Sentry | endpoint, headers, DSN | configuração local; ingestão remota pendente |
| Supabase Realtime | publication/client | estrutura local; E2E remoto de reconnect pendente |

## Handoff de webhook para consumidores

Entregar ao consumidor:

- algoritmo `HMAC-SHA256`;
- headers `X-BigHead-Event-Id`, `X-BigHead-Timestamp` e
  `X-BigHead-Signature` (`sha256=<hex>`);
- bytes canônicos assinados: `<timestamp>.<body bruto>`;
- janela de timestamp/replay acordada pelo consumidor;
- deduplicação obrigatória por event ID;
- resposta 2xx apenas depois de persistir o efeito;
- retry exponencial, máximo de tentativas e contato para dead-letter;
- processo de rotação do secret sem enviá-lo por ticket/email.

O BigHead entrega webhooks at-least-once. O consumidor deve ser idempotente.

## Critério de aceite do provider

1. Teste de contrato passa contra sandbox.
2. Round-trip controlado passa em staging.
3. Retry, 429, timeout, credencial inválida e indisponibilidade são exercitados.
4. Métricas/logs/alertas chegam sem secrets ou PII.
5. Reprocessamento não duplica efeito.
6. Revogação/rotação é ensaiada.
7. Owner assina o handoff e riscos residuais ficam registrados.
