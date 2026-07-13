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
- [x] UI nunca oferece transicao invalida para o estado/perfil atual.
- [x] Resposta 409 exibe conflito e recarrega sem perder texto do usuario.
- [x] Dependencia circular e representada como erro de campo.
- [x] Logs e custos fazem paginação e nao bloqueiam o detalhe.
- [x] Contrato lista estados terminal, lease, retry e classificacao de falha.

## Evidencia

Cobertura web T14-T19 e E2E run -> aprovacao; testes unitarios explicitos validam preservacao do texto no 409 e paginacao por cursor sem substituir a pagina anterior. T16 deriva destinos de `allowedTaskTransitions`: cada opcao e aceita pela state machine backend e estados terminais desabilitam o submit; teste comprova `new -> triaged|canceled` sem expor `in_progress`. `PATCH /v1/tasks/{taskId}/dependencies` substitui dependencias em transacao, valida `expectedVersion`, converte o trigger de ciclo em `409` e a UI o associa ao campo. `TaskOperationalPanels` mantem o resumo renderizado e pagina logs/custos independentemente. Revisao independente: `PASS` para ambos.

## Fora de escopo

- Orquestrador e workers reais.
