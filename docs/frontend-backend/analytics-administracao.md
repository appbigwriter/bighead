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

## Metadados e reconciliacao de KPI

Todas as cinco views (`summary`, `operations`, `agents`, `costs` e `funnel`) devolvem
`source`, `period`, `timezone`, `freshness`, `calculatedAt`, filtros efetivos,
`attributionModel` e `attributionMethod`. Views sem atribuicao comercial declaram
explicitamente `not_applicable`; o funil declara o modelo solicitado e a propriedade de
receita usada no calculo.

Cada view inclui `reconciliation` com valor do KPI, soma do drill-down e `reconciled`.
A resposta so pode declarar reconciliacao quando ambos os lados usam o mesmo tenant,
periodo, timezone e filtros. O webhook envia `X-BigHead-Event-Id` e `Idempotency-Key`
estaveis, mas entrega HTTP e at-least-once: o consumidor externo precisa persistir a chave
antes do efeito para obter exactly-once no seu proprio dominio.

Custos por provider/modelo usam `cost_events.model_id` no instante do evento e nunca a
versao mais recente do agente. A view de agentes declara as tabelas de modelo/provider e
tambem devolve `skillMetrics`, calculado de `tool_calls.skill_id`; custos de skill nao sao
rateados artificialmente quando um run possui mais de uma skill.

## Erros obrigatorios

- `403` tentativa de remover/rebaixar ultimo owner
- `409` experimento com campos travados ou conflito de membership
- `422` configuracao invalida de webhook ou branding
- `423` request LGPD bloqueado por legal hold
- `500` exportacao/auditoria indisponivel
