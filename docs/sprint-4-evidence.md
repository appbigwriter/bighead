# Sprint 4 — evidências

Atualizado em 2026-07-13. Um critério só entra como comprovado quando há implementação, teste e revisão correspondentes.

## Comprovado

- S4-00: 56 rotas classificadas e destinos de redirect/remove registrados em `docs/frontend-route-migration.md`.
- S4-01: shell operacional, navegação curta, troca de tenant e estados de acesso validados por testes focados e revisão independente.
- S4-02: Home usa respostas reais do workspace, prioridades exibem responsável/prazo/risco/próxima ação, Busca Global usa BFF autenticado e IDs reais, Notificações usa o endpoint real e abre recursos suportados por ID.
- S4-03, recorte contratável: salas e criação real, seleção por `roomId`, timeline real, envio idempotente, reconciliação Realtime, rascunho offline e inspector de contexto/arquivos. Revisão independente: PASS sem P0/P1/P2 no recorte suportado.
- S4-04, recorte contratável: inbox, criação idempotente com contexto, detalhe por `taskId` e transição com `expectedVersion`/409. Revisão independente final: PASS sem P0/P1/P2.
- Login: 8 de 8 hashes do baseline preservados após as mudanças.

## Validação executada

- Testes S4-02 integrados: 15 de 15 passaram antes da revisão; após os ajustes da revisão, Busca/Notificações/Wiring: 11 de 11 passaram.
- `pnpm --filter @bighead/web typecheck`: passou.
- `pnpm --filter @bighead/web lint`: passou.
- Build de produção isolado (`NEXT_DIST_DIR=.next-s402`): passou.
- S4-03 após correções: 21 de 21 testes locais passaram; revisão independente repetiu 19 testes focados com PASS.
- S4-04 após correções: 25 de 25 testes integrados passaram; o último recheck independente passou 10 de 10.

## Bloqueios abertos

- Deep links carregam IDs reais, mas as telas de detalhe ainda precisam consumi-los. Isso será fechado por S4-03, S4-04, S4-05 e S4-06.
- O inspector integral de sala está bloqueado por contrato: não existe GET read-only de membros e `GET /v1/tasks` não aceita filtro `roomId`. Nenhum dado foi inventado.
- Tarefas seguem limitadas pelo contrato: não existe `GET /v1/tasks/{taskId}`, filtros owner/risco/SLA nem payload de detalhe com dependências, timeline, artefatos e custos. O detalhe procura o ID na página suportada de até 100 itens e informa a limitação.
- O contrato vigente de notificações não possui mutação para marcar uma notificação como lida; nenhuma ação foi simulada.
- O gate completo de contratos listado em `docs/frontend-route-migration.md` permanece bloqueado nos itens ausentes do backend.
- S4-07 (E2E real desktop/mobile, Axe, performance, fixture guard, diff visual e revisão final) ainda não foi executada.

## Revisão independente

Veredito atual de S4-02: **FAIL controlado** por um P1 transversal — as futuras telas de detalhe ainda não consomem os IDs dos deep links. Os três P2 locais encontrados (concorrência de busca, fuso horário e CTA de 403) foram corrigidos e revalidados.
