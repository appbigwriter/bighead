# Acesso e organizacoes

## Escopo

Cobertura das telas `T01-T09`: login, recuperacao, convite, onboarding, seletor de tenant, home, busca global, notificacoes e perfil.

## Contratos necessarios

| Tela | Endpoint | Request/response principal | Observacoes |
|---|---|---|---|
| T01 | `POST /v1/auth/login` | `{ email, password?, provider? } -> { userId, memberships[] }` | erro deve ser indistinto para email inexistente ou senha invalida |
| T02 | `POST /v1/auth/recovery` | `{ email } -> { status }` | nao enumerar email |
| T03 | `GET/POST /v1/invitations/{token}` | convite + acao de aceite | token pode estar `expired`, `revoked`, `used` |
| T04 | `POST /v1/onboarding` | wizard incremental | salvar progresso por passo |
| T05 | `GET /v1/organizations` | lista de memberships | troca de tenant invalida caches e subscriptions |
| T06 | `GET /v1/analytics/summary` | cards e blocos da home | permitir partial payload com freshness |
| T07 | `POST /v1/search/global` | busca multiindice | sempre respeitar tenant e papel |
| T08 | `GET /v1/notifications` | notificacoes e contadores | polling/realtime; alvo pode ter sido removido |
| T09 | `GET/PATCH /v1/preferences` | preferencias visuais e operacionais | persistencia por usuario/tenant |

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
