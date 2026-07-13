# Sprint 3 - Status de implementacao

Atualizado em 2026-07-13 09:47 America/Sao_Paulo.

## Fase comprovada

- As 46 tabelas de dominio previstas foram criadas e possuem RLS habilitada.
- A linha de base validada possui 21 migrations reproduziveis, incluindo hardening de Data API/RLS, leases recuperaveis, privacidade, auditoria atomica e imutabilidade de versoes publicadas de scorecard.
- O pgTAP totaliza 149 assercoes em onze arquivos, cobrindo estrutura, RLS, isolamento entre tenants, autorizacao, auditoria, Storage, seed RBAC, outbox/leases, historico de scorecards e avaliacoes, claim/backoff do scanner e regras selecionadas que suportam os dominios T01-T56.
- A API publica no runtime todas as 86 operacoes da matriz T01-T56 e o comando adicional transacional de start de experimento. A suite registrada passou com 72 testes e cinco skips executados separadamente contra Supabase real; o worker passou 24 testes e um skip de integracao executado separadamente.
- O contrato OpenAPI canonico possui 75 paths e passou sincronismo com snapshot, matriz, referencias e operacoes FastAPI publicadas.
- Auth, Postgres/RLS, Storage e os fluxos integrados foram exercitados em seis integracoes Supabase, todas aprovadas.
- O E2E sem MSW passou em desktop e mobile: 18/18 execucoes para as nove jornadas representativas.
- O outbox possui lease transacional, teste concorrente de publicacao unica e smoke real de RPC, Redis Stream, ACK, reconexao e deduplicacao por id; isso nao comprova todos os workers e providers externos previstos.
- O seed local cria dois tenants deterministas, cada um com usuarios Auth para owner, admin, manager, member, reviewer e analyst.
- Runbooks de staging/producao, release/forward-fix, incidentes, backup/restore,
  SLOs/alertas e handoff de providers foram documentados; sua execucao remota
  permanece pendente.

## Evidencia local

- `pnpm db:verify`: PASS com reset local, 21 migrations, seed, 149 testes pgTAP, lint e advisors.
- `supabase test db`: onze arquivos, 149 assercoes, PASS.
- `supabase db lint --local --schema public,private,storage --level error`: zero erros na execucao registrada.
- `supabase db advisors --local --type all --level warn --fail-on error`: sem erro bloqueante na execucao registrada.
- Suite API: 72 PASS e cinco SKIP de integracao controlados; worker: 24 PASS e um SKIP controlado; web: 156/156 PASS antes da fatia final de Realtime/T47.
- Contract tests OpenAPI: PASS para 75 paths canonicos e snapshot sincronizado.
- `pnpm test:integration:supabase`: 6/6 PASS, incluindo Auth real, membership/RLS, Storage assinado/quarentena, round-trips dos dominios, recuperacao/idempotencia e start concorrente de experimento.
- `pnpm test:integration:outbox`: 1/1 PASS contra Supabase e Redis reais locais, cobrindo claim/ack RPC, Redis Stream, reconexao e evento unico por id.
- E2E real sem MSW: 18/18 PASS apos correcao de regressao SQL, nove jornadas em desktop e mobile, com Axe sem violacao seria/critica e sem service worker/MSW.
- `pnpm db:performance-test`: PASS, 750 amostras; p95 de 93,982 ms para notificacoes, 97,045 ms para salas e 94,723 ms para tarefas, todos abaixo de 500 ms; dados de carga revertidos ao final.
- `pnpm db:restore-test`: PASS em 35,88 s; 46 tabelas publicas e quatro schemas, hashes de dados e catalogo equivalentes no mesmo snapshot exportado; sem residuo temporario.
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
- O repositorio possui imagens e composicao local de producao para web, API e
  worker, mas a plataforma remota e seus comandos de promocao/rollback ainda
  precisam ser definidos antes do staging.

## Criterios comprovados nesta fatia

- 46/46 tabelas possuem RLS verificada e os testes adversariais exercitados nao encontraram acesso cross-tenant.
- Os testes pgTAP, API, worker e contratos cobrem fronteiras de servidor que suportam os dominios T01-T56, complementados por 6/6 integracoes reais Supabase e 1/1 smoke real de outbox/Redis. Revisoes independentes encontraram bloqueadores, corrigidos antes da nova rodada final de verificacao.
- Replays de mensagem e tarefa revalidam membership ativa na mesma transacao; retry concorrente retorna o mesmo run e nao degrada em erro 500.
- T13 retorna preview assinado apenas para artefato `clean`, e atualizacoes de sala, criacao/transicao de tarefa e retry geram auditoria append-only.
- O seed reproduz dois tenants e todos os seis papeis em cada tenant, incluindo identidades aceitas pelo GoTrue.
- Storage rejeita acesso cross-tenant, path traversal, MIME/extensao divergentes, checksum ausente e bypass de quarentena nos testes exercitados.
- Scanner de artefatos usa claim/lease atomico, backoff para falha transitoria e conclusao condicionada ao dono do lease; indisponibilidade do provider nao rejeita permanentemente o upload.
- Dependencia circular de tarefas e rejeitada no banco.
- Audit log nao pode ser alterado ou excluido por papeis de aplicacao nos testes pgTAP registrados.
- Scorecards publicados e avaliacoes historicas nao podem ser alterados ou excluidos; uma avaliacao so referencia scorecard publicado, e nova revisao exige nova versao. Nove assercoes pgTAP comprovam essas invariantes e a interpretacao pela versao original.
- Restore e performance locais passaram por revisao independente, com limpeza e rollback comprovados.
- Webhook usa assinatura HMAC, retry/dead-letter e destino validado com resolucao IP; privacidade cobre lifecycle, legal hold tenant-scoped, export assinado, anonimizacao e retomada de lease.

## Riscos residuais

- Cobertura estrutural de RLS em todas as tabelas nao substitui testes adversariais CRUD para cada dominio, operacao e papel.
- Os skips das suites unitarias sao cobertos pelos comandos de integracao locais, mas nao contam como aprovacao de provedores externos ou staging.
- Analytics/Logflare local permanece desabilitado no Windows, reduzindo paridade com staging.
- A suite local nao substitui observabilidade, alertas, restore, carga e smoke tests em staging.
- Os limiares de alerta e SLOs documentados sao candidatos para validacao em
  staging, nao configuracao operacional comprovada.
