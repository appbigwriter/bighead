# Analytics, administracao e compliance

## Escopo

Cobertura de `T46-T56`: experimentos, dashboards, budgets, atribuicao, organizacao, membros, integracoes, privacidade e auditoria.

## Contratos necessarios

| Bloco | Endpoint | Regra chave |
|---|---|---|
| Experimentos | `GET /v1/experiments`, `GET/PATCH /v1/experiments/{experimentId}` | campos de configuracao ficam imutaveis apos start |
| Analytics resumo | `GET /v1/analytics/summary` | KPI com periodo, timezone, freshness e drill-down |
| Analytics operacao | `GET /v1/analytics/operations` | SLA, throughput e backlog por equipe |
| Analytics agentes | `GET /v1/analytics/agents` | latencia, custo e sucesso por agente/skill/modelo |
| Custos e budgets | `GET /v1/analytics/costs`, `GET /v1/budgets` | quotas e alertas por tenant/equipe |
| Funil e atribuicao | `GET /v1/analytics/funnel` | modelo de atribuicao declarado |
| Organizacao | `GET/PATCH /v1/organizations/{organizationId}` | branding, timezone e defaults |
| Membros | `GET /v1/memberships`, `PATCH /v1/memberships/{id}` | ultimo owner protegido |
| Integracoes | `GET /v1/integrations`, `POST /v1/webhooks/test` | secret revela uma unica vez |
| Privacidade/Auditoria | `GET /v1/privacy/requests`, `GET /v1/audit/events` | auditoria append-only, exportacao e legal hold |

## Erros obrigatorios

- `403` tentativa de remover/rebaixar ultimo owner
- `409` experimento com campos travados ou conflito de membership
- `422` configuracao invalida de webhook ou branding
- `423` request LGPD bloqueado por legal hold
- `500` exportacao/auditoria indisponivel
