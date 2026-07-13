# BH-S2-04 - Tarefas, state machine, execucoes e SLA

**Telas:** T14-T19  
**Depende de:** BH-S2-01, BH-S2-03  
**Estimativa:** 13 pontos

## Historia

Como gestor e operador, quero criar, acompanhar e recuperar tarefas para controlar ownership, SLA, custo e qualidade.

## Escopo

- Inbox tabela/kanban, filtros, views, lotes e paginação.
- Criacao/edicao com roteamento explicado, dependencias, risco e SLA.
- Detalhe com resumo, timeline, plano, artefatos, aprovacoes, execucoes, custos e auditoria.
- UI da state machine: destinos validos, motivo obrigatório, conflito de versao e confirmação.
- Monitor de runs/passos, heartbeat, tentativas, logs mascarados, cancel/retry.
- Fila de falhas e calendario/SLA.

## Contratos backend

Tasks CRUD, transition command com `expected_version`, dependencies, runs, steps, retry/cancel, artifacts, costs, failure aggregation e calendar. Definir eventos e frequencia de polling/realtime.

## Criterios de aceite

- [x] T14-T19 cobertas.
- [ ] UI nunca oferece transicao invalida para o estado/perfil atual.
- [x] Resposta 409 exibe conflito e recarrega sem perder texto do usuario.
- [ ] Dependencia circular e representada como erro de campo.
- [ ] Logs e custos fazem paginação e nao bloqueiam o detalhe.
- [x] Contrato lista estados terminal, lease, retry e classificacao de falha.

## Evidencia

Cobertura web T14-T19 e E2E run -> aprovacao; testes unitarios explicitos validam preservacao do texto no 409 e paginacao por cursor sem substituir a pagina anterior. `docs/frontend-backend/tarefas-execucoes.md` especifica estados terminais, lease/heartbeat, retry historico, limites e classes de falha; `pnpm sprint2:handoff-check` exige a presenca desses contratos e das operacoes correspondentes no OpenAPI. As regras de transicao na UI, ciclo como erro de campo e independencia de logs/custos permanecem abertas.

## Fora de escopo

- Orquestrador e workers reais.
