# BH-S2-07 - Experimentos, analytics, administracao e compliance

**Telas:** T46-T56  
**Depende de:** BH-S2-01, BH-S2-02, BH-S2-06  
**Estimativa:** 21 pontos

## Historia

Como owner, analista ou administrador, quero medir resultado e configurar a plataforma sem perder governanca ou rastreabilidade.

## Escopo

- Experimentos: lista, configuracao, variantes, janela, stop rule e resultado.
- Dashboards executivo, SLA, agentes/skills, custos/quotas e funil/atribuicao.
- Organizacao/branding, membros/convites/papeis, integracoes/webhooks.
- Privacidade, retencao, legal hold, exportacao, exclusao e auditoria append-only.

## Contratos backend

Experiments/variants/metrics; analytics aggregates/drilldown/attribution; budgets; organization settings; memberships/invites; integrations/webhooks/deliveries; privacy requests/retention/audit export. Todo KPI deve declarar fonte, periodo, timezone e freshness.

## Criterios de aceite

- [x] T46-T56 completas.
- [x] Experimento iniciado bloqueia campos imutaveis.
- [ ] Dashboard permite rastrear indicador ate registros componentes.
- [ ] Ultimo owner nao pode ser removido/rebaixado no mock.
- [ ] Secret de webhook aparece apenas uma vez.
- [ ] Ações LGPD exibem escopo, impacto e status do job.
- [ ] Auditoria nao possui acao de editar/excluir.

## Evidencia

Cobertura web T46-T56 e E2E experimento -> resultado/admin -> auditoria em desktop/mobile; o E2E comprova bloqueio de campos depois do inicio. Os demais criterios permanecem abertos.

## Fora de escopo

- Calculo estatistico e jobs reais.
