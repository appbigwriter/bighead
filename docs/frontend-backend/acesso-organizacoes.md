# Acesso e organizacoes

## Escopo

Cobertura das telas `T01-T09`: login, recuperacao, convite, onboarding, seletor de tenant, home, busca global, notificacoes e perfil.

## Contratos necessarios

| Tela | Endpoint | Request/response principal | Observacoes |
|---|---|---|---|
| T01 | `POST /v1/auth/login` | `LoginRequest -> AuthSessionResponse` | erro deve ser indistinto para email inexistente ou senha invalida |
| T02 | `POST /v1/auth/recovery` | `{ email } -> { status }` | nao enumerar email |
| T03 | `POST /v1/invitations/{token}/accept` | `InvitationAcceptRequest -> InvitationAcceptResponse` | token pode estar expirado, revogado ou usado |
| T04 | `POST /v1/onboarding` | `OnboardingSubmitRequest -> OnboardingSubmitResponse` | submissao atomica cria organizacao e owner |
| T05 | `GET /v1/organizations` | lista de memberships | troca de tenant invalida caches e subscriptions |
| T05 | `POST /v1/organizations/{organizationId}/switch` | sem body -> `SwitchOrganizationResponse` | exige membership ativa |
| T06 | `GET /v1/analytics/summary` | cards, drilldowns, reconciliation e freshness | filtros `from`, `to`, `timezone`, `cards` |
| T07 | `POST /v1/search/global` | busca multiindice | sempre respeitar tenant e papel |
| T08 | `GET /v1/notifications` | notificacoes e contadores | polling/realtime; alvo pode ter sido removido |
| T09 | `GET/PATCH /v1/preferences`, `POST /v1/sessions/revoke` | preferencias e revogacao local/global | persistencia por usuario/tenant |

## Envelope, autenticacao e campos

Endpoints privados exigem `Authorization: Bearer <access-token>` e
`x-organization-id: <uuid>`. Datas usam ISO-8601 UTC, ids sao UUID e listas usam
`{ items, nextCursor }` somente quando o response model declarar esses campos. Erros usam
`{ type, title, status, detail, traceId }`. O frontend nunca escolhe tenant apenas a partir
de query/cookie: o backend valida membership ativa do usuario autenticado.

| Jornada | Request completo | Response minimo |
|---|---|---|
| Login | `{ email, passwordOrMagicLink?, provider? }`; `provider` em login retorna `422` e OAuth usa callback PKCE | `{ session: { id, accessToken?, refreshToken?, expiresAt? }?, user: { id?, email, sessionId?, expiresAt? }, memberships: [{ id, organizationId, userId, role, status }], status }` |
| Recovery | `{ email }` | `202 { status: "requested", expiresAt? }` tanto para email existente quanto inexistente |
| Convite | token no path; `{ fullName, password?, accept }` | `{ membership: { id, organizationId, userId, role, status }, nextRoute }` |
| Onboarding | `{ profile: { displayName, locale, timezone }, organization: { name, slug, timezone, locale }, goals[], approvalPolicy }` | `201 { organizationId, ownerMembershipId, nextRoute }` |
| Organizacoes | query `{ includeSuspended?, currentOrganizationId? }` | `{ organizations: [{ id, name, slug, timezone, locale }], currentOrganizationId? }` |
| Analytics summary | query `{ from?, to?, timezone?, cards?[] }` | `{ cards: [{ key, value, source, period, timezone, freshness }], drilldowns: [{ card, dimension, value, recordIds: [uuid], recordCount, recordsTruncated, recordsEndpoint }], alerts: [{}], source: ["tasks"], period: { from, to, boundary }, timezone, freshness, calculatedAt, filters: { cards: [] }, reconciliation: { card, cardValue, drilldownValue, reconciled } }`; `GET /v1/analytics/summary/records?dimension&from&to&cursor&limit` pagina todos os registros do mesmo tenant sem inventar IDs |
| Troca de contexto | UUID no path, sem body | `{ organizationId, role, status: "active" }` |
| Home | query `{ from?, to?, timezone?, cards?[] }` | `{ cards: [{ key, value, source, period, timezone, freshness }], drilldowns[], alerts[], reconciliation, period, timezone, freshness }` |
| Busca global | `{ query, scopes?: ("rooms"|"messages"|"tasks")[], limit?: 1..50 }` | `{ groups[], shortcuts[], removedCount }` |
| Notificacoes | query `{ filter?: "all"|"unread", limit?: 1..100 }` | `{ items[], unreadCount, nextCursor? }` |
| Preferencias | patch `{ theme?: "light"|"dark"|"system", locale?, timezone?, accessibility?, expectedUpdatedAt? }` | `{ profile: { id, displayName, avatarPath?, locale, timezone, updatedAt }, preferences, sessions[] }` |
| Revogar sessoes | `{ scope: "local"|"global" }` | `204` sem body |

Login invalido e normalizado pelo frontend para o mesmo feedback `invalid_credentials`, sem indicar
se email, senha, confirmacao ou conta falhou. Recovery sempre devolve `202 accepted`. O
frontend descarta cache, dados renderizados, queries pendentes e subscriptions antes de
aplicar `contextVersion` de outra organizacao.

## Cache, paralelismo e eventos

- Depois do contexto, home, notificacoes e preferencias podem carregar em paralelo; convite,
  onboarding e troca de tenant sao sequenciais.
- `organizations.membership.updated` invalida `tenant-context` e `GET /v1/organizations`.
- `analytics.summary.updated` invalida o periodo afetado; payload parcial conserva
  `freshness` por card.
- `notifications.updated` atualiza itens e contador com dedupe por id.
- `preferences.updated` invalida somente a preferencia do usuario/tenant correspondente.
- Toda troca de tenant cancela requests anteriores com `AbortSignal`; a resposta so e aplicada
  depois de o endpoint confirmar membership `active` para o UUID selecionado.

## Chaves de cache e invalidacao

- `tenant-context`
- `dashboard-summary:{tenantId}:{period}`
- `global-search:{tenantId}:{query}`
- `notifications:{tenantId}:{userId}`
- `preferences:{tenantId}:{userId}`

## Erros obrigatorios

- `401` sessao expirada
- `403` membership suspensa
- `404` convite inexistente
- `409` tenant removido ou preferencia desatualizada
- `422` campo invalido no wizard
