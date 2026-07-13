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

## Erros obrigatorios

- `409` version conflict
- `422` transition invalid
- `423` active lease conflict
- `429` retry limit reached
- `500` provider/tool execution failure
