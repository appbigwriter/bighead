# Tarefas e execucoes

## Escopo

Cobertura de `T14-T19`: inbox, criacao, detalhe, monitor de run, fila de falhas e calendario SLA.

## Contratos necessarios

| Tela | Endpoint | Regra chave |
|---|---|---|
| T14 | `GET /v1/tasks` | tabela/kanban, filtros, lotes e cursor |
| T15 | `POST /v1/tasks` | `Idempotency-Key` e validacao de dependencia circular |
| T16 | `POST /v1/tasks/{taskId}/transition` | `expected_version`, motivo e conflito `409` |
| T17 | `GET /v1/runs` | polling/realtime, heartbeat e mascara de logs |
| T17 | `POST /v1/runs/{runId}/retry` | nova tentativa sem apagar historico |
| T18 | `GET /v1/failures` | agrupamento por classificacao e impacto |
| T19 | `GET /v1/tasks/calendar` | leitura por data, owner e workflow |

## Invariantes frontend-backend

- UI nunca oferece transicao invalida.
- `409` deve devolver payload suficiente para recarregar sem perder rascunho local.
- logs e custos sao paginados e nao bloqueiam o detalhe da tarefa.
- lease e heartbeat precisam ter status textual e timestamp legiveis.

## Estados e execucao

Estados de tarefa: `new`, `triaged`, `in_progress`, `waiting_tool`, `waiting_human`,
`ready_for_review`, `approved`, `failed`, `done` e `canceled`. `done` e `canceled` sao terminais:
nao aceitam nova transicao. Cada resposta de
`POST /v1/tasks/{taskId}/transition` devolve `allowedTransitions`; a UI usa somente essa
lista e envia `expectedVersion`. Versao divergente retorna `409` com o estado atual, sem
apagar o texto local. Dependencia direta ou transitiva que fecha um ciclo retorna `422` com
o caminho do ciclo em erro de campo.

Estados de run: `queued`, `running`, `waiting`, `succeeded`, `failed`, `canceled` e
`dead_letter`. `succeeded`, `canceled` e `dead_letter` sao terminais. Run `running` inclui `lockedBy`, `lockedUntil` e `heartbeatAt`;
`lockedUntil` no passado e apresentado como `lease_expired`. Um worker nao pode confirmar
ou estender lease de outro worker (`423`).

`POST /v1/runs/{runId}/retry` nunca altera/apaga a tentativa original. A resposta inclui
`previousRunId` e o novo run `queued` com `attempt + 1`. Run com lease ativo retorna `423`;
qualquer tentativa sem lease ativo e abaixo do limite pode ser repetida de forma idempotente,
e a quinta tentativa retorna `429`.

Falhas sao classificadas pelo `errorCode` persistido (fallback `unknown`) e agrupadas em
`GET /v1/failures` com `count`, `affectedTasks` e `latestAt`. Classes que a UI deve tratar:
`validation`, `provider`, `tool`, `timeout`, `permission`, `quota`, `lease_expired` e
`unknown`. `errorDetail` e dado de diagnostico mascarado e nunca deve ser renderizado como
HTML. Logs, custos e runs usam cursor opaco, `limit` de `1..100`, e carregamento incremental;
falha de uma aba nao bloqueia resumo/timeline da tarefa.

## Erros obrigatorios

- `409` version conflict
- `422` transition invalid
- `423` active lease conflict
- `429` retry limit reached
- `500` provider/tool execution failure
