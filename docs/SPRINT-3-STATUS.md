# Sprint 3 - Status de implementacao

Atualizado em 2026-07-13 09:47 America/Sao_Paulo.

## Fase comprovada

- As 46 tabelas de dominio previstas foram criadas e possuem RLS habilitada.
- A linha de base validada possui 20 migrations reproduziveis, incluindo hardening de Data API/RLS, leases recuperaveis, privacidade e auditoria atomica.
- O pgTAP totaliza 131 assercoes em dez arquivos, cobrindo estrutura, RLS, isolamento entre tenants, autorizacao, auditoria, Storage, seed RBAC, outbox/leases e regras selecionadas que suportam os dominios T01-T56.
- A API implementa os dominios T01-T56. A suite registrada passou com 54 testes e cinco skips que sao executados separadamente contra Supabase real; o worker passou 17 testes e um skip de integracao executado separadamente.
- O contrato OpenAPI canonico possui 74 paths e passou sincronismo com snapshot, matriz, referencias e operacoes FastAPI publicadas.
- Auth, Postgres/RLS, Storage e os fluxos integrados foram exercitados em cinco integracoes Supabase, todas aprovadas.
- O E2E sem MSW passou em desktop e mobile: 18/18 execucoes para as nove jornadas representativas.
- O outbox possui lease transacional, teste concorrente de publicacao unica e smoke real de RPC, Redis Stream, ACK, reconexao e deduplicacao por id; isso nao comprova todos os workers e providers externos previstos.
- O seed local cria dois tenants deterministas, cada um com usuarios Auth para owner, admin, manager, member, reviewer e analyst.

## Evidencia local

- `pnpm db:verify`: PASS com reset local, 20 migrations, seed, 131 testes pgTAP, lint e advisors.
- `supabase test db`: dez arquivos, 131 assercoes, PASS.
- `supabase db lint --local --schema public,private,storage --level error`: zero erros na execucao registrada.
- `supabase db advisors --local --type all --level warn --fail-on error`: sem erro bloqueante na execucao registrada.
- Suite API: 54 PASS e cinco SKIP de integracao controlados; worker: 17 PASS e um SKIP controlado; web: 141/141 PASS.
- Contract tests OpenAPI: PASS para 74 paths canonicos e snapshot sincronizado.
- `pnpm test:integration:supabase`: 5/5 PASS, incluindo Auth real, membership/RLS, Storage assinado/quarentena, round-trips dos dominios e recuperacao/idempotencia.
- `pnpm test:integration:outbox`: 1/1 PASS contra Supabase e Redis reais locais, cobrindo claim/ack RPC, Redis Stream, reconexao e evento unico por id.
- E2E real sem MSW: 18/18 PASS apos correcao de regressao SQL, nove jornadas em desktop e mobile, com Axe sem violacao seria/critica e sem service worker/MSW.
- `pnpm db:performance-test`: PASS, 750 amostras; p95 de 88,012 ms para notificacoes, 84,242 ms para salas e 84,572 ms para tarefas, todos abaixo de 500 ms; dados de carga revertidos ao final.
- `pnpm db:restore-test`: PASS em 32,19 s; 46 tabelas publicas e quatro schemas, hashes de dados e catalogo equivalentes no mesmo snapshot exportado; sem residuo temporario.
- Secret guard: PASS independente, sem isencao por placeholder e com tratamento de desaparecimento de arquivo entre `stat` e leitura.

## Limite da evidencia

- As 56 telas nao possuem comprovacao individual de ponta a ponta contra backend real. As 18 execucoes E2E cobrem nove jornadas representativas, nao 56/56 telas nem todos os caminhos T01-T56.
- Nao houve deploy ou validacao em staging. Restore, performance e E2E registrados foram executados contra a stack local.
- O restore local prova recuperacao logica e RTO local; nao prova RPO, blobs do Storage, backup gerenciado, banda ou volume de staging.
- A performance medida cobre consultas Postgres/RLS locais; nao comprova API, pooler, rede, disponibilidade mensal ou volume representativo de producao.
- Providers externos de OAuth, email, IA, CRM, enriquecimento e publicacao nao possuem round-trip completo comprovado. Fallback, circuit breaker, billing e dead-letter de provider continuam abertos.
- Realtime possui estrutura/publicacao, mas reconnect, ordenacao e deduplicacao no cliente ainda nao foram comprovados ponta a ponta.
- Outbox e webhook possuem retry/dead-letter; webhook e privacidade possuem retomada de lease; idempotencia foi comprovada para ledger/outbox e mutacao LGPD. O efeito externo de webhook permanece at-least-once.
- Nao ha evidencia para go-live nem aprovacao de Produto, Engenharia e Seguranca.

## Criterios comprovados nesta fatia

- 46/46 tabelas possuem RLS verificada e os testes adversariais exercitados nao encontraram acesso cross-tenant.
- Os testes pgTAP, API, worker e contratos cobrem fronteiras de servidor que suportam os dominios T01-T56, complementados por 5/5 integracoes reais Supabase, 1/1 smoke real de outbox/Redis e revisoes independentes com veredito PASS.
- Replays de mensagem e tarefa revalidam membership ativa na mesma transacao; retry concorrente retorna o mesmo run e nao degrada em erro 500.
- T13 retorna preview assinado apenas para artefato `clean`, e atualizacoes de sala, criacao/transicao de tarefa e retry geram auditoria append-only.
- O seed reproduz dois tenants e todos os seis papeis em cada tenant, incluindo identidades aceitas pelo GoTrue.
- Storage rejeita acesso cross-tenant, path traversal, MIME/extensao divergentes, checksum ausente e bypass de quarentena nos testes exercitados.
- Dependencia circular de tarefas e rejeitada no banco.
- Audit log nao pode ser alterado ou excluido por papeis de aplicacao nos testes pgTAP registrados.
- Restore e performance locais passaram por revisao independente, com limpeza e rollback comprovados.
- Webhook usa assinatura HMAC, retry/dead-letter e destino validado com resolucao IP; privacidade cobre lifecycle, legal hold tenant-scoped, export assinado, anonimizacao e retomada de lease.

## Riscos residuais

- Cobertura estrutural de RLS em todas as tabelas nao substitui testes adversariais CRUD para cada dominio, operacao e papel.
- Os skips das suites unitarias sao cobertos pelos comandos de integracao locais, mas nao contam como aprovacao de provedores externos ou staging.
- Analytics/Logflare local permanece desabilitado no Windows, reduzindo paridade com staging.
- A suite local nao substitui observabilidade, alertas, restore, carga e smoke tests em staging.
