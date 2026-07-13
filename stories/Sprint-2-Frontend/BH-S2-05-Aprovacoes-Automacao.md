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
- [ ] Autoaprovacao bloqueada no mock quando politica exige segregacao.
- [ ] Token do portal nao revela shell ou recursos externos ao escopo.
- [ ] Publicacao gera versao imutavel e diff compreensivel.
- [ ] Editor impede publicar grafo invalido, ciclo indevido ou schema incompatível.
- [ ] Desabilitar skill/modelo mostra consumidores afetados.
- [x] Handoff descreve cada comando, status assíncrono e erro.

## Evidencia

Cobertura web T20-T34 e E2E run -> aprovacao/portal externo; teste unitario comprova bloqueio apos decisao imutavel. `docs/frontend-backend/governanca-automacao.md` cataloga os comandos T20-T34, controles de concorrencia/idempotencia, estados assincronos, eventos e tratamento por codigo; `pnpm sprint2:handoff-check` cruza a cobertura T10-T45 e operacoes criticas com OpenAPI. Os criterios funcionais de segregacao, portal, publicacao, editor e impacto permanecem abertos sem prova especifica.

## Casos de borda

Decisao concorrente, link no limite de uso, rollback com runs antigos, node removido com arestas, teste de skill timeout, preço sem vigencia.

## Fora de escopo

- Execucao real de agentes, ferramentas ou portal token validation.
