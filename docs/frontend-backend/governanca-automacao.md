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

## Erros obrigatorios

- `401` token de portal expirado
- `403` autoaprovacao bloqueada
- `409` decisao concorrente ou rollback incompatível
- `422` workflow invalido
- `504` teste de skill excedeu timeout
