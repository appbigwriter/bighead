# BH-S3-02 - Colaboracao, tarefas, artefatos e realtime

**Dominio:** Backend/Database  
**Depende de:** BH-S3-01  
**Estimativa:** 21 pontos

## Historia

Como operador, quero conversar e executar tarefas com estado consistente para preservar contexto e responsabilidade.

## Escopo

- Implementar `rooms`, `room_members`, `messages`, `tasks`, `task_dependencies`, `task_transitions` e `artifacts`.
- APIs T10-T19 com cursor, filtros, views lógicas, contadores e comandos idempotentes.
- Políticas específicas de salas privadas; mensagens herdam acesso da sala.
- Threads, mencoes, reacoes (adicionar tabela/migration se confirmadas pelo contrato), edicao/exclusao auditada.
- Upload lifecycle e conversao mensagem -> tarefa.
- State machine transacional com optimistic locking; deteccao de ciclo em dependencias.
- Realtime para mensagem, tarefa e notificacao; deduplicacao e ordenacao por evento.
- SLA scheduler para alertas e aging.

## Criterios de aceite

- [x] APIs T10-T19 substituem mocks sem alterar tipos.
- [x] Sala privada nao aparece em busca/contagem para nao membro.
- [x] Duas transicoes concorrentes geram um sucesso e um 409.
- [x] Dependencia direta ou indireta circular e rejeitada.
- [x] Reconnect realtime nao duplica mensagens.
- [x] URL assinada expira e respeita tenant.
- [x] Auditoria registra edicao, exclusao, transicao e reatribuicao.

## Testes de carga/borda

Timeline de 100 mil mensagens, paginação estável com novos inserts, task source removida, último moderador, SLA em timezone diferente, upload cancelado.

Evidencia registrada em 2026-07-13: o teste real
`test_real_collaboration_replay_membership_retry_and_audit_guards` passou contra o
Supabase local. O replay de criacao preservou o mesmo `client_id` e uma unica linha, e a trilha registrou
`message.edited`, `message.deleted`, `task.transitioned` e `task.reassigned`.
Evidencia complementar registrada em 2026-07-13: o E2E real fecha a assinatura no evento
`offline` sem desmontar a tela, cria uma mensagem durante o gap, abre nova assinatura e aguarda
`ready`, reconcilia o snapshot por `id`/`client_id` e comprova uma unica ocorrencia na API e na UI.
Um canal Beacon autenticado permanece ativo, recebe um evento-controle do proprio tenant e nao
recebe o ID Atlas. Desktop e mobile passaram (2/2); revisao independente final: PASS.

## Fora de escopo

- Execucao de agentes e aprovação.
