# Contratos por tela

Este documento conecta cada tela T01-T56 a seus contratos primarios. Quando uma tela for majoritariamente local nesta Sprint, isso aparece explicitamente.

| Tela | Nome | Query/Command/Eventos principais |
|---|---|---|
| T01 | Login | `POST /v1/auth/login` |
| T02 | Recuperacao e redefinicao | `POST /v1/auth/recovery` futuro; tela local nesta Sprint |
| T03 | Aceite de convite | `POST /v1/invitations/{token}/accept` futuro; tela local nesta Sprint |
| T04 | Onboarding | `POST /v1/onboarding` futuro; tela local nesta Sprint |
| T05 | Seletor de organizacao | `GET /v1/organizations` |
| T06 | Home operacional | `GET /v1/analytics/summary` |
| T07 | Busca global e command palette | `POST /v1/search/global` futuro; tela local nesta Sprint |
| T08 | Notificacoes | `GET /v1/notifications` |
| T09 | Perfil e sessoes | `GET /v1/profile`, `GET /v1/sessions` futuros |
| T10 | Lista de salas | `GET /v1/rooms`, `POST /v1/rooms` |
| T11 | Sala conversacional | `GET /v1/rooms/{roomId}/messages`, evento `room.message.created` futuro |
| T12 | Informacoes e membros da sala | `PATCH /v1/rooms/{roomId}` futuro |
| T13 | Arquivos da sala | `GET /v1/rooms/{roomId}/files` futuro |
| T14 | Inbox de tarefas | `GET /v1/tasks` |
| T15 | Criacao de tarefa | `POST /v1/tasks` |
| T16 | Detalhe da tarefa | `GET /v1/tasks/{taskId}` futuro, `POST /v1/tasks/{taskId}/transition` |
| T17 | Monitor de execucao | `GET /v1/runs`, evento `run.step.requested` |
| T18 | Fila de falhas | `GET /v1/runs?status=failed` futuro |
| T19 | Calendario e SLA | `GET /v1/tasks?view=sla` futuro |
| T20 | Inbox de aprovacoes | `GET /v1/approvals` |
| T21 | Detalhe da aprovacao | `POST /v1/approvals/{approvalId}/decision` |
| T22 | Scorecards Sentinel QA | `GET /v1/approvals/{approvalId}/scorecard` futuro |
| T23 | Politicas de aprovacao | `GET /v1/policies/approvals` futuro |
| T24 | Portal externo | `GET /v1/portal/items/{token}` |
| T25 | Catalogo de agentes | `GET /v1/agents` |
| T26 | Configuracao do agente | `GET /v1/agents/{agentId}`, `PATCH /v1/agents/{agentId}` futuros |
| T27 | Catalogo de skills | `GET /v1/skills` |
| T28 | Configuracao/teste da skill | `POST /v1/skills/{skillId}/validate` futuro |
| T29 | Provedores e modelos | `GET /v1/models` futuro |
| T30 | Biblioteca e versoes de prompts | `GET /v1/prompts` futuro |
| T31 | Lista de workflows | `GET /v1/workflows` |
| T32 | Editor visual de workflow | `GET /v1/workflows/{workflowId}` futuro |
| T33 | Historico de versoes | `GET /v1/workflows/{workflowId}/versions` futuro |
| T34 | Biblioteca de playbooks | `GET /v1/playbooks` futuro |
| T35 | Biblioteca de conhecimento | `GET /v1/knowledge/documents` |
| T36 | Documento e ingestao | `POST /v1/knowledge/documents` futuro |
| T37 | Memoria operacional | `GET /v1/memory/items` futuro |
| T38 | Busca semantica/debug RAG | `POST /v1/search/semantic` |
| T39 | Contas e contatos | `GET /v1/crm/accounts` futuro |
| T40 | Leads | `GET /v1/crm/leads` |
| T41 | Detalhe do lead | `GET /v1/crm/leads/{leadId}` futuro |
| T42 | Pipeline e oportunidades | `GET /v1/crm/opportunities` futuro |
| T43 | Campanhas | `GET /v1/content/campaigns` |
| T44 | Estudio de conteudo | `GET /v1/content/assets`, `POST /v1/content/assets` futuros |
| T45 | Calendario editorial/publicacoes | `GET /v1/content/publications` futuro |
| T46 | Lista de experimentos | `GET /v1/experiments` |
| T47 | Configuracao e resultado do experimento | `GET /v1/experiments/{experimentId}` futuro |
| T48 | Dashboard executivo | `GET /v1/analytics/summary` |
| T49 | Operacoes e SLA | `GET /v1/analytics/operations` futuro |
| T50 | Performance de agentes/skills | `GET /v1/analytics/agents` futuro |
| T51 | Custos, budgets e quotas | `GET /v1/analytics/costs` futuro |
| T52 | Funil e atribuicao | `GET /v1/analytics/funnel` futuro |
| T53 | Organizacao e branding | `GET /v1/organizations/{organizationId}` futuro |
| T54 | Membros, convites e papeis | `GET /v1/memberships`, `POST /v1/invitations` futuros |
| T55 | Integracoes e webhooks | `GET /v1/integrations`, `POST /v1/webhooks/test` futuros |
| T56 | Privacidade, retencao e auditoria | `GET /v1/audit/events` |
