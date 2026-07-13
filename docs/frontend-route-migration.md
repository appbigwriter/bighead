# S4-00 — mapa de migração do frontend

Data do gate: 2026-07-13  
Commit inspecionado: `83c59aef55d821f0ed99f5a7b798b74a0ba6423a`  
Catálogo: `apps/web/src/lib/screen-catalog.ts`  
Contrato canônico: `packages/contracts/openapi/openapi.yaml`  
Snapshot: `docs/frontend-backend/openapi-snapshot.yaml`

## Veredito

**BLOCKED.** OpenAPI canônico e snapshot são idênticos (`sha256:9d90485065ceef9c54153251eb2c9176c552cf4ff13e26bde2f4a8ccd269074f`), porém contratos obrigatórios da Sprint 4 estão ausentes ou divergentes:

1. não existe leitura de detalhe de tarefa (`GET /v1/tasks/{taskId}`);
2. não existe leitura de detalhe/histórico de aprovação (`GET /v1/approvals/{approvalId}`), e `ApprovalDecisionResponse` não contém histórico, ator ou timestamp;
3. bloqueio de autoaprovação existe no repositório, mas retorna `409`, não o `403` exigido, e não possui teste de integração específico;
4. não existe leitura do board de pipeline;
5. não existe mutação de follow-up vinculada ao lead/oportunidade;
6. filtros de tarefas contratados aceitam apenas `status`, `cursor` e `limit`; faltam owner, risco e SLA exigidos pela sprint.

Pela regra S4-00, nenhum mock ou contrato inventado libera S4-01. Backend/Produto precisam replanejar ou versionar os contratos antes da implementação.

## Estado atual das rotas

O App Router possui uma única rota autenticada dinâmica, `apps/web/src/app/(workspace)/[...slug]/page.tsx`. Ela resolve todas as entradas do catálogo e renderiza `ScreenTemplate`; portanto, existência atual de URL não prova experiência de produto. Rotas especiais reais: `/login`, `/catalogo`, `/portal/{token}` e `/auth/update-password`.

Valores de classificação:

- `productize_s4`: substituição integral nesta sprint;
- `productize_later`: mantém deep link atual e sai da navegação primária;
- `redirect`: URL antiga preservada via redirecionamento ao destino indicado;
- `catalog_only`: somente documentação técnica em `/catalogo`;
- `remove`: sem produto ou destino válido; deve retornar 404/410 conforme decisão.

## Classificação das 56 telas

| Tela | Nome | Deep link atual | Classificação | Destino/deep link final | Owner |
|---|---|---|---|---|---|
| T01 | Login | `/acesso/login` | `redirect` | `/login` (congelado) | Identidade |
| T02 | Recuperação e redefinição | `/acesso/recuperacao` | `redirect` | `/login` (seção “Outras formas de acesso”) | Identidade |
| T03 | Aceite de convite | `/acesso/convite` | `productize_later` | manter `/acesso/convite`; Sprint 7 | Identidade |
| T04 | Onboarding | `/acesso/onboarding` | `productize_later` | manter `/acesso/onboarding`; Sprint 7 | Identidade |
| T05 | Seletor de organização | `/acesso/organizacoes` | `productize_s4` | `/acesso/organizacoes` | Identidade + Frontend A/B |
| T06 | Home operacional | `/operacao/home` | `productize_s4` | `/operacao/home` | Produto + Frontend A |
| T07 | Busca global e command palette | `/operacao/busca-global` | `productize_s4` | `/operacao/busca-global` | Produto + Frontend A |
| T08 | Notificações | `/operacao/notificacoes` | `productize_s4` | `/operacao/notificacoes` | Produto + Frontend A |
| T09 | Perfil e sessões | `/operacao/perfil` | `productize_later` | manter `/operacao/perfil`; Sprint 7 | Identidade |
| T10 | Lista de salas | `/colaboracao/salas` | `productize_s4` | `/colaboracao/salas` | Colaboração + Frontend B |
| T11 | Sala conversacional | `/colaboracao/sala` | `productize_s4` | `/colaboracao/sala?roomId={roomId}` | Colaboração + Frontend B |
| T12 | Informações e membros da sala | `/colaboracao/membros` | `redirect` | `/colaboracao/sala?roomId={roomId}&panel=members` | Colaboração |
| T13 | Arquivos da sala | `/colaboracao/arquivos` | `redirect` | `/colaboracao/sala?roomId={roomId}&panel=files` | Colaboração |
| T14 | Inbox de tarefas | `/tarefas/inbox` | `productize_s4` | `/tarefas/inbox` | Trabalho + Frontend B |
| T15 | Criação de tarefa | `/tarefas/criar` | `productize_s4` | `/tarefas/criar` | Trabalho + Frontend B |
| T16 | Detalhe da tarefa | `/tarefas/detalhe` | `productize_s4` | `/tarefas/detalhe?taskId={taskId}` | Trabalho + Frontend B |
| T17 | Monitor de execução | `/tarefas/execucao` | `redirect` | `/tarefas/detalhe?taskId={taskId}&panel=execution` | Trabalho |
| T18 | Fila de falhas | `/tarefas/falhas` | `redirect` | `/tarefas/inbox?status=failed` | Trabalho |
| T19 | Calendário e SLA | `/tarefas/sla` | `redirect` | `/tarefas/inbox?view=sla` | Trabalho |
| T20 | Inbox de aprovações | `/governanca/aprovacoes` | `productize_s4` | `/governanca/aprovacoes` | Governança + Frontend B |
| T21 | Detalhe da aprovação | `/governanca/aprovacao-detalhe` | `productize_s4` | `/governanca/aprovacao-detalhe?approvalId={approvalId}` | Governança + Frontend B |
| T22 | Scorecards Sentinel QA | `/governanca/scorecards` | `redirect` | `/governanca/aprovacao-detalhe?approvalId={approvalId}&panel=scorecard` | Governança |
| T23 | Políticas de aprovação | `/governanca/politicas` | `productize_later` | manter `/governanca/politicas`; Sprint 7 | Governança |
| T24 | Portal externo | `/governanca/portal-externo` | `redirect` | `/portal/{token}` | Governança |
| T25 | Catálogo de agentes | `/automacao/agentes` | `productize_later` | manter; Sprint 5 | Automação |
| T26 | Configuração do agente | `/automacao/agente-config` | `productize_later` | manter; Sprint 5 | Automação |
| T27 | Catálogo de skills | `/automacao/skills` | `productize_later` | manter; Sprint 5 | Automação |
| T28 | Configuração/teste da skill | `/automacao/skill-teste` | `productize_later` | manter; Sprint 5 | Automação |
| T29 | Provedores e modelos | `/automacao/modelos` | `productize_later` | manter; Sprint 5 | Automação |
| T30 | Biblioteca e versões de prompts | `/automacao/prompts` | `productize_later` | manter; Sprint 5 | Automação |
| T31 | Lista de workflows | `/automacao/workflows` | `productize_later` | manter; Sprint 5 | Automação |
| T32 | Editor visual de workflow | `/automacao/workflow-editor` | `productize_later` | manter; Sprint 5 | Automação |
| T33 | Histórico de versões | `/automacao/workflow-versoes` | `productize_later` | manter; Sprint 5 | Automação |
| T34 | Biblioteca de playbooks | `/automacao/playbooks` | `productize_later` | manter; Sprint 5 | Automação |
| T35 | Biblioteca de conhecimento | `/conhecimento/biblioteca` | `productize_later` | manter; Sprint 6 | Conhecimento |
| T36 | Documento e ingestão | `/conhecimento/ingestao` | `productize_later` | manter; Sprint 6 | Conhecimento |
| T37 | Memória operacional | `/conhecimento/memoria` | `productize_later` | manter; Sprint 6 | Conhecimento |
| T38 | Busca semântica/debug RAG | `/conhecimento/busca-semantica` | `productize_later` | manter; Sprint 6 | Conhecimento |
| T39 | Contas e contatos | `/comercial/contas-contatos` | `productize_later` | manter; Sprint 6 | Comercial |
| T40 | Leads | `/comercial/leads` | `productize_s4` | `/comercial/leads` | Comercial + Frontend A |
| T41 | Detalhe do lead | `/comercial/lead-detalhe` | `productize_s4` | `/comercial/lead-detalhe?leadId={leadId}` | Comercial + Frontend A |
| T42 | Pipeline e oportunidades | `/comercial/pipeline` | `productize_s4` | `/comercial/pipeline` | Comercial + Frontend A |
| T43 | Campanhas | `/comercial/campanhas` | `productize_later` | manter; Sprint 6 | Comercial |
| T44 | Estúdio de conteúdo | `/comercial/conteudo` | `productize_later` | manter; Sprint 6 | Comercial |
| T45 | Calendário editorial/publicações | `/comercial/publicacoes` | `productize_later` | manter; Sprint 6 | Comercial |
| T46 | Lista de experimentos | `/aprendizado/experimentos` | `productize_later` | manter; Sprint 7 | Analytics |
| T47 | Configuração e resultado do experimento | `/aprendizado/experimento-detalhe` | `productize_later` | manter; Sprint 7 | Analytics |
| T48 | Dashboard executivo | `/aprendizado/dashboard-executivo` | `productize_later` | manter; Sprint 7 | Analytics |
| T49 | Operações e SLA | `/aprendizado/analytics-sla` | `productize_later` | manter; Sprint 7 | Analytics |
| T50 | Performance de agentes/skills | `/aprendizado/analytics-agentes` | `productize_later` | manter; Sprint 7 | Analytics |
| T51 | Custos, budgets e quotas | `/aprendizado/custos` | `productize_later` | manter; Sprint 7 | Analytics |
| T52 | Funil e atribuição | `/aprendizado/funil` | `productize_later` | manter; Sprint 7 | Analytics |
| T53 | Organização e branding | `/administracao/organizacao` | `productize_later` | manter; Sprint 7 | Administração |
| T54 | Membros, convites e papéis | `/administracao/membros` | `productize_later` | manter; Sprint 7 | Administração |
| T55 | Integrações e webhooks | `/administracao/integracoes` | `productize_later` | manter; Sprint 7 | Administração |
| T56 | Privacidade, retenção e auditoria | `/administracao/privacidade-auditoria` | `productize_later` | manter; Sprint 7 | Administração |

Contagem: 14 `productize_s4`, 33 `productize_later`, 9 `redirect`, 0 `catalog_only`, 0 `remove`.

## Matriz API, estados e owner — 14 rotas S4

`OK` significa contrato suficiente para o recorte explícito da rota. `PARCIAL` significa que existe base, mas algum requisito da Sprint 4 não é contratável. `BLOCKED` impede o cenário obrigatório.

| Tela/rota | Leitura | Mutação | Payload/estado decisivo | HTTP/erro contratado | Papel OpenAPI | Owner | Gate |
|---|---|---|---|---|---|---|---|
| T05 `/acesso/organizacoes` | `GET /v1/organizations` → `OrganizationListResponse` | `POST /v1/organizations/{organization_id}/switch` | path `organization_id`; resposta `organizationId`, `role`, `status` | GET `200/403/422`; switch `200/422` | member / sessão autenticada | Identidade + FE A/B | `PARCIAL`: switch não declara 403 no OpenAPI |
| T06 `/operacao/home` | `GET /v1/analytics/summary` → `AnalyticsSummaryResponse` | — | `period`, `timezone`, `cards`; cards/alerts/freshness | `200/206/403/422` | owner/analyst | Produto + FE A | `OK` para Owner |
| T07 `/operacao/busca-global` | — | `POST /v1/search/global` | `GlobalSearchRequest {query, scopes, limit}` → grupos/atalhos | `200/403/422` | member | Produto + FE A | `OK` |
| T08 `/operacao/notificacoes` | `GET /v1/notifications` → `NotificationListResponse` | — | `filter`, `cursor`, `limit`; items/unreadCount/nextCursor | `200/403/422` | member | Produto + FE A | `PARCIAL`: sem contrato para marcar lida/preferências nesta rota |
| T10 `/colaboracao/salas` | `GET /v1/rooms` → `RoomListResponse` | `POST /v1/rooms` → `Room` | filtros/cursor; `RoomCreateRequest` | GET `200/403/422`; POST `201/403/422` | member | Colaboração + FE B | `OK` |
| T11 `/colaboracao/sala` | `GET /v1/rooms/{roomId}/messages` → `MessageListResponse` | `POST /v1/rooms/{roomId}/messages` | `MessageCreateRequest {body,parentMessageId,clientId,metadata}`; idempotência por `clientId` | GET `200/403/409/422`; POST `201/422` | member | Colaboração + FE B | `PARCIAL`: POST não declara 403/409; menção/anexo/agente não têm schema explícito |
| T14 `/tarefas/inbox` | `GET /v1/tasks` → `TaskListResponse` | — | somente `status`, `cursor`, `limit` | `200/403/422` | member | Trabalho + FE B | `BLOCKED`: faltam filtros owner/risco/SLA |
| T15 `/tarefas/criar` | — | `POST /v1/tasks` + `Idempotency-Key` | `TaskCreateRequest` inclui `roomId` e `sourceMessageId`; estado inicial `new` | `201/409/422` | member | Trabalho + FE B | `OK` para vínculo mensagem→tarefa |
| T16 `/tarefas/detalhe` | **ausente** `GET /v1/tasks/{taskId}` | `POST /v1/tasks/{taskId}/transition` | `targetState`, `reason`, `expectedVersion`; enum contém `new` e `triaged` | `200/403/409/422` | member/reviewer | Trabalho + FE B | `BLOCKED`: sem leitura de detalhe; transição/version409 existe |
| T20 `/governanca/aprovacoes` | `GET /v1/approvals` → `Page` genérico | — | sem query de pendentes/vencidas/decididas no contrato | `200/403/422` | reviewer (owner/admin/reviewer no código) | Governança + FE B | `PARCIAL`: fila não possui filtros nem shape tipado de aprovação |
| T21 `/governanca/aprovacao-detalhe` | **ausente** `GET /v1/approvals/{approvalId}` | `POST /v1/approvals/{approvalId}/decision` | `decision`, `comment`, `expectedRound`; resposta sem histórico | `200/403/409/422` | reviewer | Governança + FE B | `BLOCKED`: sem detalhe/histórico; autoaprovação retorna 409, não 403 |
| T40 `/comercial/leads` | `GET /v1/crm/leads` → `LeadListResponse` | — | `stage`, `ownerId`, `scoreMin/scoreMax`, cursor | `200/403/422` | analyst/member | Comercial + FE A | `OK` |
| T41 `/comercial/lead-detalhe` | `GET /v1/crm/leads/{leadId}` → `LeadDetailResponse` | **ausente follow-up** | includeTimeline/includeSignals; lead/timeline/signals/suggestions | `200/403/404/422` | analyst/member | Comercial + FE A | `BLOCKED`: cenário exige criação persistida de follow-up |
| T42 `/comercial/pipeline` | **ausente board/lista de oportunidades** | `POST /v1/crm/opportunities/{id}/stage` | `targetStage`, `requiredFields`, `forecast` → opportunity/boardSummary/auditEntry | `200/403/409/422` | manager | Comercial + FE A | `BLOCKED`: sem leitura do pipeline; mutação de etapa existe |

## Verificação dos contratos essenciais

| Contrato obrigatório | Evidência | Resultado |
|---|---|---|
| `roomId` | `Task` e `TaskCreateRequest` no OpenAPI | PASS |
| `sourceMessageId` | `Task` e `TaskCreateRequest` no OpenAPI | PASS |
| `new -> triaged` | enum `TaskStatus`; teste `test_collaboration_api.py` envia `triaged` | PASS |
| `expectedVersion` + 409 | `TaskTransitionRequest`; resposta 409; teste de API cobre transição | PASS |
| decisão de aprovação | `ApprovalDecisionRequest/Response`; POST contratado | PASS |
| histórico com ator/timestamp | nenhum GET de detalhe; resposta não possui histórico/ator/timestamp | **FAIL** |
| bloqueio de autoaprovação 403 | SQL impede `requested_by = user_id` quando segregação ativa, mas falha vira 409; nenhum teste específico | **FAIL** |

## Decisões necessárias para desbloqueio

1. Backend owner publica contratos tipados para detalhe de tarefa, detalhe/histórico de aprovação, board do pipeline e follow-up.
2. Produto decide se inbox de tarefas perde filtros owner/risco/SLA ou backend os adiciona.
3. Governança define erro estável de autoaprovação: recomendado Problem `403` com código `approval_self_decision_forbidden`, separado de concorrência `409`.
4. Identidade adiciona 403 documentado ao switch de organização.
5. Produto confirma se T03/T04/T09 entram realmente na Sprint 7; roadmap atual não os nomeia.

