# Sprint 3 - Status de implementacao

Atualizado em 2026-07-13 07:23 America/Sao_Paulo.

## Fase comprovada

- As cinco migrations da Sprint 3 sobem a partir de banco vazio por reset local deterministico.
- As 46 tabelas de dominio previstas foram criadas e possuem RLS habilitada.
- Os testes pgTAP totalizam 47 assercoes em cinco arquivos e cobrem contagem das tabelas, RLS, isolamento entre tenants, limites de autorizacao, imutabilidade de auditoria e politicas de Storage.
- O lint do banco e os advisors locais passaram sem erro bloqueante.
- A API de identidade/Auth foi implementada para login, callback PKCE, recovery, onboarding, contexto de tenant, preferencias, memberships, convites e revogacao de sessao.
- O bucket privado, as politicas de Storage, a API de artefatos e o worker de quarentena/scan foram implementados.

## Evidencia local

- `supabase db reset --local --yes`: PASS em banco recriado.
- `supabase test db`: cinco arquivos, 47 assercoes, resultado PASS.
- `supabase db lint --local --schema public,private,storage --level error`: zero erros.
- `supabase db advisors --local --type all --level warn --fail-on error`: sem erro bloqueante.
- Testes API integrados no pacote: 19 cenarios com providers, repositorio e Storage fake.
- Testes do worker: nove cenarios, incluindo checksum, MIME, ZIP/OpenXML estrutural, malware e indisponibilidade do scanner.
- Revisao independente focada dos bloqueadores de seguranca: PASS.

## Limite da evidencia

- Auth ainda nao foi exercitado ponta a ponta contra Supabase Auth real.
- A API e o worker de Storage ainda nao foram exercitados contra Storage, banco e scanner reais; signed URLs, upload, quarentena e download estao comprovados por politicas pgTAP ou fakes, nao por integracao completa.
- Os contratos T01-T09 ainda nao possuem comprovacao integral contra servicos reais.
- As APIs, workers e contratos T10-T56 permanecem abertos.
- Realtime, filas, leases, concorrencia, idempotencia operacional e outbox ainda nao foram comprovados end-to-end.
- O seed local ainda nao fornece os dois tenants e todos os papeis exigidos pela BH-S3-01.
- E2E sem MSW, staging, restore, RPO/RTO, carga e performance permanecem abertos.

## Criterios comprovados nesta fatia

- 46/46 tabelas possuem migration e RLS verificadas no reset local.
- Os testes adversariais pgTAP comprovam isolamento cross-tenant nas fronteiras representativas exercitadas.
- As quatro tabelas da BH-S3-01 possuem RLS e grants minimos.
- Storage rejeita acesso cross-tenant, path traversal, MIME/extensao divergentes, checksum ausente e bypass de quarentena no nivel de politicas.
- Dependencia circular de tarefas e rejeitada no banco.

## Riscos residuais

- Cobertura estrutural de RLS em todas as tabelas nao substitui testes adversariais CRUD para cada dominio e papel.
- Providers fake podem divergir das respostas, erros, expiracao e revogacao reais do Supabase Auth e Storage.
- Realtime, outbox e workers de dominio ainda nao possuem fluxo funcional comprovado.
- Ausencia de seed completo reduz a reproducibilidade dos cenarios por papel.
- Analytics/Logflare local permanece desabilitado no Windows, reduzindo paridade com staging.
- O workspace nao possui repositorio Git funcional, impedindo diff/status confiaveis.
- A suite FastAPI emite um aviso de deprecacao externo entre Starlette TestClient e httpx; nao afeta os testes atuais, mas requer atualizacao coordenada de dependencias.
