# BH-S2-05 - Aprovacoes, agentes, skills, workflows e playbooks

**Telas:** T20-T34  
**Depende de:** BH-S2-01, BH-S2-04  
**Estimativa:** 21 pontos

## Historia

Como owner, gestor ou revisor, quero governar automacoes e aprovar entregas de acordo com risco, mantendo versoes e impacto visiveis.

## Escopo

- Inbox/detalhe de aprovação, comparacao, comentarios e decisao imutavel.
- Scorecards Sentinel e politicas de aprovação com simulador.
- Portal externo isolado, branded, responsivo, com token expirado/revogado/usado.
- Catalogo/configuracao/teste/versionamento/metricas de agentes, modelos, prompts e skills.
- Catalogo de workflows, editor React Flow, validacao, simulacao, publicacao, diff e rollback.
- Biblioteca de playbooks e inicio parametrizado.

## Contratos backend

Approvals/decisions/links; QA scorecards/evaluations; agents/versions; providers/models/pricing; skills/test/health; workflows/versions/validate/simulate/publish; playbooks/instantiate. Definir imutabilidade, schemas JSON, permissões e análise de impacto.

## Criterios de aceite

- [x] T20-T34 completas.
- [x] Autoaprovacao bloqueada no mock quando politica exige segregacao.
- [x] Token do portal nao revela shell ou recursos externos ao escopo.
- [x] Publicacao gera versao imutavel e diff compreensivel.
- [x] Editor impede publicar grafo invalido, ciclo indevido ou schema incompatível.
- [x] Desabilitar skill/modelo mostra consumidores afetados.
- [x] Handoff descreve cada comando, status assíncrono e erro.

## Evidencia

Cobertura web T20-T34 e E2E run -> aprovacao/portal externo. `sprint2-domain-experiences.test.tsx` comprova no mock frontend o bloqueio de autoaprovacao T20 por identidade de sessao imutavel, impacto nomeado nas telas T27/T29, versionamento visual com diff T30/T33 e bloqueio interativo de ciclo/schema T32. `sprint2-domain-rules.test.ts` comprova tambem nodes vazios/duplicados e componentes desconectados. `portal-experience.test.tsx` injeta campos internos adicionais e comprova que o portal renderiza somente o contrato permitido, sem shell, navegacao ou dados fora do escopo. Concorrencia e persistencia real do versionamento pertencem ao backend. Gates: lint e typecheck aprovados; Vitest web 205/205.

## Casos de borda

Decisao concorrente, link no limite de uso, rollback com runs antigos, node removido com arestas, teste de skill timeout, preço sem vigencia.

## Fora de escopo

- Execucao real de agentes, ferramentas ou portal token validation.
