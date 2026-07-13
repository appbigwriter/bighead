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
- [x] Timeline com 5.000 fixtures permanece utilizavel.
- [x] Mensagem otimista reconcilia ID temporario sem duplicar.
- [x] Membro sem acesso nao ve sala privada em busca ou contador.
- [x] Falha de upload/realtime pode ser recuperada.
- [x] Contrato documenta ordenacao, cursor, idempotency key e limites de arquivo.

## Evidencia

Cobertura web T10-T13 e E2E conversa -> tarefa em desktop/mobile; teste unitario explicito valida reconciliacao e retry sem duplicacao. `VirtualTimeline` e usada por T11 com 5.000 fixtures, mantem menos de 20 elementos no DOM e alcanca o item 5.000 por scroll. T13 repete uploads com falha `408/429/5xx` em ate tres tentativas; o controlador Realtime reconcilia em conexao/reconexao, deduplica eventos e ignora versoes antigas. `docs/frontend-backend/colaboracao.md` fixa ordenacao, cursor, idempotencia e limite de 50 MiB. `003_domain_schema_rls.sql` comprova que membro do mesmo tenant sem membership da sala nao a recebe em listagem/busca nem em `count(*)`; pgTAP local: 8/8 `PASS`.

## Casos de borda

Mensagem removida com replies, reconnect fora de ordem, upload duplicado, mencao a membro suspenso, remocao do ultimo moderador.

## Fora de escopo

- WebSocket/Realtime real e processamento de audio.
