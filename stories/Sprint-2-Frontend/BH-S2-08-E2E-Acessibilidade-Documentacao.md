# BH-S2-08 - E2E, acessibilidade e handoff do frontend

**Telas:** T01-T56  
**Depende de:** BH-S2-01 a BH-S2-07  
**Estimativa:** 13 pontos

## Historia

Como equipe backend, quero receber frontend validado e contratos completos para conectar dados reais sem reinterpretar comportamento visual.

## Escopo

- E2E das jornadas: onboarding; conversa -> tarefa; run -> aprovação; portal externo; ingestao -> busca; lead -> oportunidade; conteudo -> publicação; experimento -> resultado; admin -> auditoria.
- Auditoria WCAG 2.2 AA, teclado, leitor de tela, contraste, zoom 200% e reduced motion.
- Testes visuais responsivos e estados de erro/permissao/offline.
- Consolidar `docs/frontend-backend/ENDPOINT-MATRIX.md` com T01-T56, endpoint, metodo, schema, papel, cache, evento e erro.
- Documentar troca MSW -> API real e feature flags.

## Criterios de aceite

- [x] Matriz possui 56/56 telas e nenhum campo `TBD` silencioso.
- [x] Nove jornadas E2E passam em desktop e viewport mobile critica.
- [x] Zero violacao crítica/seria de acessibilidade.
- [x] Nenhum componente importa fixture diretamente fora da camada MSW.
- [x] Snapshot OpenAPI usado pelo frontend esta versionado.
- [x] Relatorio lista riscos residuais e decisões pendentes para Sprint 3.

## Evidencias

- 34/34 execucoes Playwright mock aprovadas em desktop/mobile: oito jornadas
  completas, a barreira autenticada do onboarding, o shell e regressoes criticas.
- 20/20 execucoes Playwright reais sem MSW aprovadas em desktop/mobile com Axe;
  a jornada autenticada cria uma identidade sem membership e conclui o onboarding
  pela UI. As duas suites combinadas cobrem as nove jornadas previstas.
- Axe integrado aos cenarios sem violacao critica/seria.
- Fixture guard aprovado; snapshot OpenAPI e matriz 56/56 versionados.
- Transporte assincrono e request-scoped tenant possuem testes dedicados.
- Na retomada de 2026-07-14, foram corrigidos o fallback `ScreenExperience`
  T01-T56, os primitives compartilhados, o contraste WCAG e o seletor E2E.
- A revisao independente final encerrou com `PASS` para codigo, contratos, gates e acessibilidade automatizada; a validacao manual de teclado permanece aberta em BH-S2-01.

## Fora de escopo

- Corrigir backend ainda inexistente ou substituir mocks nesta story.
