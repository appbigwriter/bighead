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

- 32/32 execucoes Playwright aprovadas: 16 cenarios em cada projeto desktop/mobile, cobrindo as nove jornadas, o shell e regressoes criticas.
- Axe integrado aos cenarios sem violacao critica/seria.
- Fixture guard aprovado; snapshot OpenAPI e matriz 56/56 versionados.
- Transporte assincrono e request-scoped tenant possuem testes dedicados.
- A revisao independente final encerrou com `PASS` para codigo, contratos, gates e acessibilidade automatizada; a validacao manual de teclado permanece aberta em BH-S2-01.

## Fora de escopo

- Corrigir backend ainda inexistente ou substituir mocks nesta story.
