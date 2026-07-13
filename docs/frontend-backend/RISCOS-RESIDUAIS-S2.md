# Riscos residuais da Sprint 2

## Validacao concluida

- Lint, typecheck, testes raiz, 141 testes web, build e guards passaram.
- E2E passou em 20/20 execucoes: 10 cenarios em desktop e mobile, incluindo as nove jornadas previstas e auditoria Axe.
- A fronteira de dados e assincrona e permite substituir o mock por HTTP sem alterar componentes.
- O contexto de tenant e isolado por request, inclusive em execucoes SSR concorrentes.
- A revisao independente registrou veredito `PASS`.

## Riscos confirmados

- Criterios mantidos abertos nas stories nao tem evidencia automatizada ou manual suficiente nesta rodada; nao devem ser inferidos a partir da cobertura geral T01-T56.
- A cobertura de acessibilidade comprovada e a automatizada por Axe; leitor de tela e toda a auditoria manual WCAG 2.2 AA continuam sem evidencia registrada.
- A Sprint 3 ainda precisa validar os contratos contra backend, RLS e migrations reais; o `PASS` desta Sprint cobre somente o frontend e seu handoff.

## Dependencias para Sprint 3

- Backend precisa confirmar os shapes finais de analytics agregados e de privacy requests.
- Alguns endpoints do PRD ainda estao representados como contratos de handoff e nao como OpenAPI detalhado.
- A selecao do transporte mock/HTTP existe na fronteira; a ativacao por dominio deve ser exercitada com o backend real na Sprint 3.

## Decisoes pendentes

- Estrategia final de polling vs realtime para notificacoes, runs e dashboards.
- Granularidade dos caches por tela de analytics.
- Mapeamento final de erros problem+json por dominio comercial e compliance.
