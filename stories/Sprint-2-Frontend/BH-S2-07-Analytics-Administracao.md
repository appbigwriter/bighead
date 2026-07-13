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
- [x] Dashboard permite rastrear indicador ate registros componentes.
- [x] Ultimo owner nao pode ser removido/rebaixado no mock.
- [x] Secret de webhook aparece apenas uma vez.
- [x] Ações LGPD exibem escopo, impacto e status do job.
- [x] Auditoria nao possui acao de editar/excluir.

## Evidencia

Cobertura web T46-T56 e E2E de leitura/configuracao de experimento, analytics,
integracoes e auditoria em desktop/mobile. Testes unitarios comprovam que, apos
rebaixar um de dois owners, o controle do owner restante fica desabilitado; o secret e
gerado apenas no reveal, apagado ao consumir e permanece indisponivel no remount da sessao;
jobs LGPD exibem Escopo, Impacto e Status; e eventos de auditoria usam lista somente leitura
sem botoes. T48 consome o tenant ativo e `AnalyticsSummaryDrilldown.recordIds` retornado por
`/v1/analytics/summary`; o backend produz UUIDs tenant-scoped e declara `recordCount`,
`recordsTruncated` e `recordsEndpoint`. `workspace-service.test.ts` comprova a preservacao desses campos na fronteira,
e os testes de `ScreenExperience` e `sprint2-domain-experiences` comprovam a navegacao do KPI
para a lista de UUIDs componentes e para a referencia escolhida, com fonte, periodo, timezone e
freshness visiveis. Para dimensoes com mais de 100 registros, a UI informa cobertura parcial e
oferece continuidade em `GET /v1/analytics/summary/records`, que pagina por cursor, periodo/status
e RLS tenant. Gates backend/OpenAPI e integracao real aprovados; lint e typecheck web aprovados;
Vitest web 205/205. A continuacao paginada passa por BFF Next autenticada, preserva tenant,
dimension, periodo e cursor, e possui teste de contrato dedicado.

## Fora de escopo

- Calculo estatistico e jobs reais.
