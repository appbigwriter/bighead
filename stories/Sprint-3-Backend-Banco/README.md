# Sprint 3 - Backend, banco e integracoes

## Objetivo

Substituir todos os mocks da Sprint 2 por FastAPI, workers, Supabase/PostgreSQL, Storage, Realtime, Redis e providers reais aprovados, mantendo os contratos congelados.

## Stories e ownership

| Story | Dominios/tabelas principais |
|---|---|
| [BH-S3-01](BH-S3-01-Supabase-Tenancy-Auth.md) | profiles, organizations, members, invites, RLS, Storage/Auth |
| [BH-S3-02](BH-S3-02-Colaboracao-Tarefas.md) | rooms, room_members, messages, tasks, dependencies, transitions, artifacts |
| [BH-S3-03](BH-S3-03-Orquestracao-Agentes-Workflows.md) | providers, models, agents, versions, skills, workflows, playbooks, runs/steps/tool_calls/costs |
| [BH-S3-04](BH-S3-04-Aprovacoes-Qualidade-Portal.md) | approvals, decisions, links, scorecards, evaluations |
| [BH-S3-05](BH-S3-05-Conhecimento-Memoria.md) | knowledge_documents, chunks, memory_items, pgvector |
| [BH-S3-06](BH-S3-06-CRM-Conteudo-Experimentos.md) | accounts, contacts, leads, signals, opportunities, campaigns, assets, experiments, variants |
| [BH-S3-07](BH-S3-07-Analytics-Notificacoes-Integracoes.md) | analytics_events, notifications, webhooks, outbox, audit_log |
| [BH-S3-08](BH-S3-08-Seguranca-E2E-Producao.md) | revisao independente, pgTAP, E2E, performance, DR e release |

## Done da Sprint

- [x] 46/46 tabelas possuem migration, RLS e testes.
- [ ] RF-01 a RF-15 e T01 a T56 usam backend real.
- [ ] State machines, idempotencia, leases e outbox passam sob concorrencia.
- [x] Zero acesso cross-tenant nos testes adversariais.
- [ ] Deploy staging passa smoke, E2E, advisors, restore e observabilidade.

## Auditoria dos itens ainda abertos (2026-07-13)

| Item | Evidencia local disponivel | Motivo para permanecer aberto |
|---|---|---|
| RF-01 a RF-15 e T01 a T56 usam backend real | `verify-screen-contracts` confirma 56/56 telas mapeadas; `contracts:check` confirma OpenAPI canonico sem drift; os handoffs T01-T45 passam | o mapeamento nao prova 56 jornadas contra a stack real; Realtime reconnect e efeitos de providers externos ainda nao possuem round-trip completo |
| State machines, idempotencia, leases e outbox sob concorrencia | pgTAP e integracoes locais cobrem transicao, approval, lease, outbox e start concorrente de experimento | efeito externo de job/webhook permanece `at-least-once`; politica publicada da skill e reconnect Realtime ainda nao estao comprovados ponta a ponta |
| Deploy staging | migrations, advisors, restore, performance, E2E e runbooks possuem evidencia local | nao houve deploy, smoke, observabilidade, carga ou restore de backup no ambiente de staging |

Nenhum item acima deve ser marcado somente com evidencia local parcial.
