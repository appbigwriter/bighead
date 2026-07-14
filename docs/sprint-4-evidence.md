# Sprint 4 — evidências

Atualizado em 2026-07-13. Critérios são marcados somente quando implementação e teste correspondente existem.

## Comprovado

- S4-00: 56 rotas classificadas; contratos de sala, tarefa, aprovação e comercial presentes no OpenAPI com 89 paths.
- S4-01/S4-02: shell curto, tenant confiável, estados de acesso, Home, Busca e Notificações usam a fronteira BFF/API real.
- S4-03: salas, timeline, envio idempotente, inspector de membros/arquivos/tarefas, rascunho offline e reconciliação Realtime com `roomId` real.
- S4-04: inbox com filtros de estado/owner/risco/SLA, criação idempotente, detalhe por `taskId`, transição versionada e tratamento de 409.
- S4-05: filas pendente/vencida/decidida, detalhe contextual, histórico, decisão e bloqueio de autoaprovação.
- S4-06: leads, detalhe, follow-up idempotente e pipeline persistente.
- Login: hashes dos 8 arquivos congelados continuam idênticos ao manifesto.

## Validação final local

- `pnpm lint`, `pnpm typecheck` e `pnpm test`: PASS.
- API: 98 passed, 13 integrações opt-in skipped na suíte unitária; integração Supabase separada: 12 passed.
- Worker: 60 passed, 2 integrações opt-in skipped.
- Web: 63 arquivos, 332 testes; UI package: 3; contracts package: 1.
- Build Next de produção: PASS.
- OpenAPI: 89 paths sincronizados; fixture guard, UI primitive guard, screen-contract guard e secret guard: PASS.
- Banco reconstruído por migrations e seed: 18 arquivos pgTAP, 272 testes; advisors sem issues; outbox real 1 passed.
- E2E real sem MSW: 20/20 PASS, 10 desktop + 10 mobile, com Axe nos fluxos, IDs reais, RLS Atlas/Beacon, reconnect e deduplicação.
- Restore lógico: PASS, 54 tabelas e 4 schemas, catálogo/hash equivalentes, 41,41 s. Performance local: PASS, 1.000 amostras e 5.000 vetores; p95 abaixo de 105 ms para orçamento de 500 ms.

## Pendências não comprovadas

- Produto ainda não forneceu/aprovou screenshots desktop/mobile do login; o pixel diff de 0,5% permanece sem baseline visual aprovado.
- A suíte real cobre 10 jornadas ponta a ponta, mas não prova individualmente as 14 rotas S4 nem os cenários comerciais completos em ambos os viewports.
- Performance medida localmente não substitui três medições no domínio remoto.
- Deploy, migrations remotas, round-trip de LLM/SMTP/Storage, restore de backup gerenciado com blobs e aceite humano só podem ser comprovados na produção.

## Revisão independente

A primeira revisão encontrou cinco P1 e dois P2. Foram corrigidos: Redis Docker no boot de produção, fila `all` de aprovações, lint do contrato gerado, snapshot imutável de contexto LLM, preço obrigatório, comparação das roles de banco e remoção de 309 artefatos Next antes versionados. Revalidação independente final: **PASS, zero P0/P1/P2**.
