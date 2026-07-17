# Riscos residuais da Sprint 2

## Validacao concluida

- Lint, typecheck, testes raiz, 435 testes web, build e guards passaram.
- E2E mock passou em 34/34 execucoes desktop/mobile; E2E real sem MSW passou
  20/20 em desktop/mobile. Ambos incluem auditoria Axe.
- A fronteira de dados e assincrona e permite substituir o mock por HTTP sem alterar componentes.
- As 24 telas que ainda compartilhavam o playbook sintetico agora possuem
  guards, correcoes, evidencias e efeitos especificos por regra critica.
- O contexto de tenant e isolado por request, inclusive em execucoes SSR concorrentes.
- A revisao independente final registrou `PASS` para codigo, contratos, gates e acessibilidade automatizada.

## Riscos confirmados

- Criterios mantidos abertos nas stories nao tem evidencia automatizada ou manual suficiente nesta rodada; nao devem ser inferidos a partir da cobertura geral T01-T56.
- Teclado real em browser desktop/mobile e Axe possuem evidencia focada em `docs/qa/sprint2-component-accessibility-evidence.md`; leitor de tela e a auditoria manual WCAG 2.2 AA completa continuam sem evidencia registrada.
- O E2E real valida jornadas representativas contra backend/RLS/migrations
  locais, mas nao comprova deploy/staging, providers externos ou as 56 jornadas
  individualmente.

## Dependencias para Sprint 3

- Backend precisa confirmar os shapes finais de analytics agregados e de privacy requests.
- Alguns endpoints do PRD ainda estao representados como contratos de handoff e nao como OpenAPI detalhado.
- A selecao do transporte mock/HTTP existe na fronteira; a ativacao por dominio deve ser exercitada com o backend real na Sprint 3.

## Decisoes pendentes

- Estrategia final de polling vs realtime para notificacoes, runs e dashboards.
- Granularidade dos caches por tela de analytics.
- Mapeamento final de erros problem+json por dominio comercial e compliance.
