# BH-S3-07 - Analytics fechado, notificacoes, webhooks e auditoria

**Dominio:** Backend/Worker/Database/Observabilidade  
**Depende de:** BH-S3-02 a BH-S3-06  
**Estimativa:** 34 pontos

## Historia

Como owner e analista, quero medir operação e receita com origem verificável, receber alertas e auditar ações críticas.

## Escopo de dados

`analytics_events`, `notifications`, `webhook_endpoints`, `event_outbox`, `audit_log`; adicionar tabelas de budgets, deliveries, privacy requests e retention policies se confirmadas pelos contratos T51/T55/T56.

## Escopo funcional

- Ingestao idempotente de eventos e dimensões consistentes de tenant/timezone.
- Agregações executivo, SLA, agentes/skills, custos e funil/atribuição; drill-down reconciliável.
- Budgets, quotas e alertas por organização/projeto/agente/provider.
- Notificações in-app e adapters email/outros canais, preferências e digest.
- Webhook delivery com HMAC, timestamp, retry, replay protection e dead-letter.
- Outbox publisher transacional e consumidor idempotente.
- Audit log append-only com redaction, exportação autorizada e retenção.
- Jobs LGPD: exportar, anonimizar/excluir quando permitido, legal hold e evidência.

## Criterios de aceite

- [ ] APIs T48-T56 substituem mocks.
- [ ] Todo KPI declara fonte, período, timezone, freshness e modelo de atribuição.
- [ ] Soma de drill-down reconcilia KPI dentro da regra documentada.
- [ ] Evento/webhook duplicado não duplica efeito.
- [x] Audit log não pode ser alterado/excluído por papel de aplicação.
- [ ] Budget excedido aplica alerta/bloqueio configurado.
- [ ] Pedido LGPD possui lifecycle, evidência e tratamento de legal hold.

Evidencia registrada em 2026-07-13: os testes pgTAP de fronteiras de seguranca
recusam alteracao e exclusao do audit log pelos papeis de aplicacao. Os demais
criterios desta story permanecem abertos, inclusive webhook/provider real.

## Fora de escopo

- Data warehouse externo; PostgreSQL atende a baseline até medição de escala.
