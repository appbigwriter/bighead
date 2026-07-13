# Governanca e automacao

## Escopo

Cobertura de `T20-T34`: aprovacoes, scorecards, politicas, portal externo, agentes, skills, modelos, prompts, workflows e playbooks.

## Contratos necessarios

| Bloco | Endpoint | Regra chave |
|---|---|---|
| Aprovacoes | `GET /v1/approvals` | inbox ordenada por prazo e risco |
| Decisao | `POST /v1/approvals/{approvalId}/decision` | decisao imutavel e conflito concorrente |
| Scorecards | `GET /v1/approvals/{approvalId}/scorecard` | checklist e score por criterio |
| Politicas | `GET/PATCH /v1/policies/approvals` | simulador e segregacao |
| Portal | `GET /v1/portal/items/{token}` | token opaco, expiracao e escopo limitado |
| Agentes | `GET/PATCH /v1/agents/{agentId}` | owner, versao, impacto e consumidores |
| Skills | `GET /v1/skills`, `POST /v1/skills/{skillId}/validate` | schema, timeout e retries |
| Modelos | `GET /v1/models` | pricing com vigencia e fallback |
| Prompts | `GET /v1/prompts/{promptId}/versions` | diff e rollback |
| Workflows | `POST /v1/workflows/{workflowId}/validate` | bloqueia ciclo e schema incompatível |
| Playbooks | `POST /v1/playbooks/{playbookId}/instantiate` | instancia com parametros obrigatorios |

## Handoff de comandos

| Comando | Request/controle | Sucesso e estado | Erros tratados pela UI |
|---|---|---|---|
| Decidir aprovacao | `POST /v1/approvals/{approvalId}/decision`, `{ decision, comment?, expectedRound }` | `200`; decisao e imutavel | `403` autoaprovacao/segregacao, `404`, `409` concorrencia |
| Atualizar politica | `PATCH /v1/policies/approvals`, regras + versao esperada | `200`; simulacao e consumidores recalculados | `403`, `409`, `422` regra invalida |
| Decidir no portal | `POST /v1/portal/items/{token}/decision`, `Idempotency-Key` + decisao/comentario | `200`; replay devolve a mesma decisao | `401` token invalido, `409` payload divergente/ja decidido, `410` expirado/revogado/usado |
| Atualizar agente | `PATCH /v1/agents/{agentId}`, patch + versao esperada | `200`; devolve impacto/consumidores | `403`, `404`, `409`, `422` dependencia ativa |
| Validar skill | `POST /v1/skills/{skillId}/validate`, `{ payload, timeoutMs, retries }` | `200`, `{ runId, status: accepted/rejected, findings, redactions }`; o resultado ja e terminal | `403`, `404`, `408/504` timeout, `422` schema/retry |
| Validar workflow | `POST /v1/workflows/{workflowId}/validate`, `{ nodes, edges, parameters }` | `200`, `{ valid, findings, schemaErrors }`; nao publica | `403`, `404`, `422` schema/ciclo |
| Publicar workflow | nova versao somente depois de validacao `valid=true`; o contrato de versoes conserva snapshot/diff | `201`; versao publicada e imutavel | `403`, `409` versao concorrente, `422` grafo invalido |
| Rollback workflow | `POST /v1/workflows/{workflowId}/rollback`, `{ targetVersion, reason }` | `201`; cria nova versao, nao reescreve historico | `403`, `404`, `409` runs incompativeis, `422` alvo invalido |
| Instanciar playbook | `POST /v1/playbooks/{playbookId}/instantiate`, `Idempotency-Key` + parametros | `201`, `{ taskId, workflowInstanceId, summary: { status: queued }, replayed }`; run segue `queued -> running -> succeeded/failed` via `runs.updated` | `403`, `404`, `409` chave/payload, `422` parametro |

Todo comando autenticado envia `Authorization: Bearer` e `x-organization-id`; comandos
idempotentes reenviam a mesma chave somente para o mesmo payload. Respostas assincronas
exibem o status devolvido, observam o evento indicado e fazem polling com backoff como
fallback. `401` encerra a sessao, `403` mostra sem permissao, `404` remove o recurso da
visao, `409` preserva o rascunho e oferece recarregar, `422` mapeia erros de campo e
`429/504` oferece retry seguro quando o comando e idempotente.

## Erros obrigatorios

- `401` token de portal expirado
- `403` autoaprovacao bloqueada
- `409` decisao concorrente ou rollback incompatível
- `422` workflow invalido
- `504` teste de skill excedeu timeout
