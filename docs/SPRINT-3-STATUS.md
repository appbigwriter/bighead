# Sprint 3 - Status de implementacao

Atualizado em 2026-07-13 08:20 America/Sao_Paulo.

## Fase comprovada

- As 46 tabelas de dominio previstas foram criadas e possuem RLS habilitada.
- A linha de base validada possui nove migrations reproduziveis, incluindo hardening comercial, leases do outbox e auditoria atomica de transicoes.
- O pgTAP totaliza 76 assercoes em oito arquivos, cobrindo estrutura, RLS, isolamento entre tenants, limites de autorizacao, auditoria, Storage, seed RBAC, outbox/leases e hardening comercial.
- A API implementa Auth/identidade, colaboracao, governanca, conhecimento, comercial e administracao. A suite registrada passou com 48 testes e tres skips de integracao controlados.
- O contrato OpenAPI canonico possui 67 paths e passou os testes de sincronismo com o snapshot, cobertura da matriz, referencias e operacoes FastAPI publicadas.
- Auth, Postgres/RLS, Storage e colaboracao reais foram exercitados em tres integracoes Supabase, todas aprovadas.
- O E2E sem MSW passou em desktop e mobile: 18/18 execucoes para as nove jornadas representativas.
- O outbox possui lease transacional, teste concorrente de publicacao unica e smoke real de RPC, Redis Stream, ACK, reconexao e deduplicacao por id; isso nao comprova todos os workers e providers externos previstos.
- O seed local cria dois tenants deterministas, cada um com usuarios Auth para owner, admin, manager, member, reviewer e analyst.

## Evidencia local

- `pnpm db:verify`: PASS com reset local, nove migrations, seed, pgTAP, lint e advisors.
- `supabase test db`: oito arquivos, 76 assercoes, PASS.
- `supabase db lint --local --schema public,private,storage --level error`: zero erros na execucao registrada.
- `supabase db advisors --local --type all --level warn --fail-on error`: sem erro bloqueante na execucao registrada.
- Suite API: 48 PASS e tres SKIP de integracao controlados.
- Contract tests OpenAPI: PASS para 67 paths canonicos e snapshot sincronizado.
- `pnpm test:integration:supabase`: 3/3 PASS, incluindo Auth real, membership/RLS, Storage assinado/quarentena, round-trip comercial/outbox e replays de colaboracao apos suspensao, retry concorrente e auditoria.
- `pnpm test:integration:outbox`: 1/1 PASS contra Supabase e Redis reais locais, cobrindo claim/ack RPC, Redis Stream, reconexao e evento unico por id.
- E2E real sem MSW: 18/18 PASS, nove jornadas em desktop e mobile.
- `pnpm db:performance-test`: PASS independente, 750 amostras; p95 de 159,673 ms para notificacoes, 166,252 ms para salas e 157,264 ms para tarefas, todos abaixo de 500 ms; rollback comprovado por contagens `0:0:0` apos o gate.
- `pnpm db:restore-test`: PASS independente em 38,53 s; 46 tabelas publicas e quatro schemas, hashes de dados e catalogo equivalentes no mesmo snapshot exportado; sem banco, arquivo temporario ou snapshot keeper residual.
- Secret guard: PASS independente, sem isencao por placeholder e com tratamento de desaparecimento de arquivo entre `stat` e leitura.

## Limite da evidencia

- As 56 telas nao possuem comprovacao individual de ponta a ponta contra backend real. As 18 execucoes E2E cobrem nove jornadas representativas, nao 56/56 telas nem todos os caminhos T01-T56.
- Nao houve deploy ou validacao em staging. Restore, performance e E2E registrados foram executados contra a stack local.
- O restore local prova recuperacao logica e RTO local; nao prova RPO, blobs do Storage, backup gerenciado, banda ou volume de staging.
- A performance medida cobre consultas Postgres/RLS locais; nao comprova API, pooler, rede, disponibilidade mensal ou volume representativo de producao.
- Providers externos de OAuth, email, IA, CRM, enriquecimento e publicacao nao possuem round-trip completo comprovado. Fallback, circuit breaker, billing e dead-letter de provider continuam abertos.
- Realtime possui estrutura/publicacao, mas reconnect, ordenacao e deduplicacao no cliente ainda nao foram comprovados ponta a ponta.
- Outbox/leases possuem testes focados e smoke real Redis, mas concorrencia completa de transicoes, aprovacoes, webhooks, experimentos e todos os workers permanece aberta.
- Nao ha evidencia para go-live nem aprovacao de Produto, Engenharia e Seguranca.

## Criterios comprovados nesta fatia

- 46/46 tabelas possuem RLS verificada e os testes adversariais exercitados nao encontraram acesso cross-tenant.
- Os testes pgTAP, API e contratos T01-T19 registrados passam, complementados por 3/3 integracoes reais Supabase e 1/1 smoke real de outbox/Redis.
- Replays de mensagem e tarefa revalidam membership ativa na mesma transacao; retry concorrente retorna o mesmo run e nao degrada em erro 500.
- T13 retorna preview assinado apenas para artefato `clean`, e atualizacoes de sala, criacao/transicao de tarefa e retry geram auditoria append-only.
- O seed reproduz dois tenants e todos os seis papeis em cada tenant, incluindo identidades aceitas pelo GoTrue.
- Storage rejeita acesso cross-tenant, path traversal, MIME/extensao divergentes, checksum ausente e bypass de quarentena nos testes exercitados.
- Dependencia circular de tarefas e rejeitada no banco.
- Audit log nao pode ser alterado ou excluido por papeis de aplicacao nos testes pgTAP registrados.
- Restore e performance locais passaram por revisao independente, com limpeza e rollback comprovados.

## Riscos residuais

- Cobertura estrutural de RLS em todas as tabelas nao substitui testes adversariais CRUD para cada dominio, operacao e papel.
- Os skips da API devem permanecer identificados e nao contam como aprovacao dos fluxos que dependem de infraestrutura externa.
- Analytics/Logflare local permanece desabilitado no Windows, reduzindo paridade com staging.
- A suite local nao substitui observabilidade, alertas, restore, carga e smoke tests em staging.
