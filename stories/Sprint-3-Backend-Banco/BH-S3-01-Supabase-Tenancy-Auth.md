# BH-S3-01 - Supabase, identidade, tenancy e seguranca base

**Dominio:** Database/Backend/Security  
**Depende de:** Sprint 1, matriz T01-T09  
**Estimativa:** 21 pontos

## Historia

Como owner, quero identidade e isolamento multi-tenant confiaveis para que nenhuma funcionalidade possa cruzar dados entre organizacoes.

## Escopo

- Converter `prd/03-Schema-Supabase.sql` em migrations Supabase ordenadas e reversiveis quando seguro.
- Implementar extensoes, tipos, `profiles`, `organizations`, `organization_members`, `organization_invites` e helpers privados.
- Integrar Supabase Auth: signup/login/providers/magic link/recovery/session revocation.
- Implementar onboarding atomico, convite idempotente e protecao do ultimo owner.
- Criar matriz RBAC/ABAC e dependency FastAPI que resolve usuario, membership, papel e tenant.
- Configurar bucket privado, paths por organização, signed URLs e validacao MIME/extensao/tamanho/checksum/quarentena.
- Seed local com dois tenants e todos os papeis.

## APIs

Implementar contratos T01-T09: auth callbacks, `/me`, profiles, organizations, switch context, memberships, invites, sessions e preferences.

## Invariantes

- Nenhuma autorizacao usa metadata editavel pelo usuario.
- Service key existe apenas no backend/worker.
- Alterar `organization_id`, papel ou ownership por payload e recusado.
- Remover/rebaixar ultimo owner e impossível.

## Criterios de aceite

- [x] Migrations sobem em banco vazio e reset local e deterministico.
- [x] Todas as tabelas criadas nesta story possuem RLS e grants mínimos.
- [x] User A/Org A nao le, conta, busca ou altera Org B.
- [x] Convite expirado/revogado/usado falha sem efeito parcial.
- [x] Storage impede acesso e path traversal cross-tenant.
- [x] pgTAP, testes API e contract tests T01-T09 passam.

Evidencia registrada em 2026-07-13: 69 assercoes pgTAP antes da migration
posterior, suite API com 47 PASS e dois SKIP controlados, contratos OpenAPI
sincronizados e 2/2 integracoes reais de Auth, RLS/Postgres e Storage.

Evidencia complementar em 2026-07-13: teste de integracao Postgres executa duas
aceitacoes concorrentes do mesmo convite (um sucesso e um `409`) e comprova que
convites expirado/revogado retornam `410` sem criar membership nem alterar
profile; suite de integracao Supabase 7/7 PASS.

## Casos de borda

Auth user sem profile, convite concorrente, email case-insensitive, membership suspensa com token antigo, troca de tenant durante request, arquivo MIME falso.

## Fora de escopo

- Dominios operacionais e providers externos.
