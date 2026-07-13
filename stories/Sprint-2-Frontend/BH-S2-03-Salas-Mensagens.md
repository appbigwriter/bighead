# BH-S2-03 - Salas, mensagens e anexos

**Telas:** T10-T13  
**Depende de:** BH-S2-01, BH-S2-02  
**Estimativa:** 13 pontos

## Historia

Como operador, quero colaborar com humanos e agentes em salas contextualizadas e transformar conversa em trabalho rastreavel.

## Escopo

- Lista de salas com favoritas, nao lidas, privadas e arquivadas.
- Sala com timeline virtualizada, threads, reacoes, mencoes, composer de texto/audio/arquivo, edicao e exclusao auditada.
- Indicacao visual distinta para humano/agente, fontes, custo e status de execucao.
- Criar tarefa a partir de mensagem sem perder origem.
- Painel de contexto, membros, tarefas e arquivos; administracao de privacidade/membros.
- Upload com progresso, cancelamento, quarantine, preview e URL assinada mockada.

## Contratos backend

CRUD de rooms/members/messages/reactions, cursor de timeline, contadores, presenca/realtime, upload lifecycle, signed URL e comando message-to-task. Definir eventos ordenados e estrategia de reconexao/deduplicacao.

## Criterios de aceite

- [x] T10-T13 completas em desktop/mobile.
- [ ] Timeline com 5.000 fixtures permanece utilizavel.
- [x] Mensagem otimista reconcilia ID temporario sem duplicar.
- [ ] Membro sem acesso nao ve sala privada em busca ou contador.
- [ ] Falha de upload/realtime pode ser recuperada.
- [x] Contrato documenta ordenacao, cursor, idempotency key e limites de arquivo.

## Evidencia

Cobertura web T10-T13 e E2E conversa -> tarefa em desktop/mobile; teste unitario explicito valida reconciliacao e retry sem duplicacao. `docs/frontend-backend/colaboracao.md` fixa ordenacao `(createdAt, id)`, cursor opaco, `clientId` idempotente e lifecycle/limite de 50 MiB do upload; `pnpm sprint2:handoff-check` valida esses invariantes contra a matriz e o snapshot OpenAPI. Timeline de 5.000 itens, isolamento de sala privada e recuperacao de upload/realtime permanecem abertos.

## Casos de borda

Mensagem removida com replies, reconnect fora de ordem, upload duplicado, mencao a membro suspenso, remocao do ultimo moderador.

## Fora de escopo

- WebSocket/Realtime real e processamento de audio.
