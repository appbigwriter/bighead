# Provisionamento e variaveis

## Ambientes

| Ambiente | Objetivo | Protecao minima |
|---|---|---|
| `development` | desenvolvimento local com mocks e stack local | secrets locais, dados descartaveis |
| `test` | CI, testes de contrato e smoke | banco isolado, sem acesso a producao |
| `staging` | homologacao integrada | secrets rotacionados, auditoria ligada |
| `production` | operacao real | secrets gerenciados, backups, observabilidade e least privilege |

## Catalogo de variaveis

| Grupo | Variavel | Finalidade | Formato | Ambiente | Responsavel |
|---|---|---|---|---|---|
| Aplicacao | `APP_ENV` | liga modo do processo | `development|test|staging|production` | todos | engenharia |
| Aplicacao | `APP_URL` | URL canonica do frontend | URL HTTPS em ambientes remotos | web/api | engenharia |
| Aplicacao | `API_URL` | URL publica da API | URL HTTPS | web/api | engenharia |
| Aplicacao | `CORS_ORIGINS` | origens permitidas | CSV de URLs | api | engenharia |
| Aplicacao | `LOG_LEVEL` | verbosidade | `DEBUG|INFO|WARNING|ERROR` | todos | engenharia |
| Supabase | `SUPABASE_URL` | endpoint do projeto | URL | todos | plataforma |
| Supabase | `SUPABASE_PUBLISHABLE_KEY` | chave cliente/SSR | string | web/api | plataforma |
| Supabase | `NEXT_PUBLIC_SUPABASE_URL` | endpoint publico incorporado no build web | URL HTTPS | web | plataforma |
| Supabase | `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | chave publica incorporada no build web | string publica | web | plataforma |
| Supabase | `SUPABASE_SECRET_KEY` | service role server-only | string secreta | api/worker | plataforma |
| Supabase | `DATABASE_URL` | conexao pooler com papel tenant/RLS e TLS | DSN Postgres | api | plataforma |
| Supabase | `DATABASE_SERVICE_URL` | conexao pooler com papel interno minimo, distinta do tenant | DSN Postgres com TLS | api | plataforma |
| Supabase | `DIRECT_DATABASE_URL` | conexao administrativa exclusiva do job de migrations | DSN Postgres com TLS | release job | plataforma |
| Supabase | `STORAGE_BUCKET` | bucket privado default | slug | api/worker | produto/plataforma |
| Seguranca | `MALWARE_SCANNER_URL` | endpoint homologado de scan | URL HTTPS | worker | plataforma |
| Seguranca | `MALWARE_SCANNER_API_KEY` | credencial Bearer do scanner | string secreta | worker | plataforma |
| Redis | `REDIS_URL` | fila e cache efemero | DSN Redis | api/worker | plataforma |
| Redis | `QUEUE_NAME` | fila principal | string | api/worker | engenharia |
| Redis | `JOB_LEASE_SECONDS` | lease do worker | inteiro > 0 | api/worker | engenharia |
| Auth | `AUTH_GOOGLE_CLIENT_ID` | OAuth Google | string | todos | plataforma |
| Auth | `AUTH_GOOGLE_CLIENT_SECRET` | segredo OAuth | string secreta | api | plataforma |
| Auth | `AUTH_MICROSOFT_CLIENT_ID` | OAuth Microsoft | string | todos | plataforma |
| Auth | `AUTH_MICROSOFT_CLIENT_SECRET` | segredo OAuth | string secreta | api | plataforma |
| Auth | `SMTP_HOST` | envio transacional | host | api | plataforma |
| Auth | `SMTP_PORT` | porta SMTP | inteiro | api | plataforma |
| Auth | `SMTP_USERNAME` | usuario SMTP | string | api | plataforma |
| Auth | `SMTP_PASSWORD` | senha SMTP | string secreta | api | plataforma |
| IA | `LLM_PROVIDER_DEFAULT` | provedor default | string | api/worker | produto/engenharia |
| IA | `LLM_PROVIDER_FALLBACK` | fallback controlado | string | api/worker | produto/engenharia |
| IA | `LLM_MODEL_DEFAULT` | modelo principal | string | api/worker | produto/engenharia |
| IA | `LLM_MODEL_FALLBACK` | modelo fallback | string | api/worker | produto/engenharia |
| IA | `EMBEDDING_MODEL` | modelo de embedding | string | api/worker | produto/engenharia |
| IA | `EMBEDDING_DIMENSION` | dimensao vetorial | inteiro | api/worker | produto/engenharia |
| IA | `LLM_MONTHLY_BUDGET_CENTS` | budget mensal | inteiro | api | produto |
| IA | `OPENAI_API_KEY` | provider selecionavel | string secreta | api/worker | plataforma |
| IA | `ANTHROPIC_API_KEY` | `OPTIONAL_UNTIL_PROVIDER_SELECTED` | string secreta | api/worker | plataforma |
| IA | `GOOGLE_GENAI_API_KEY` | `OPTIONAL_UNTIL_PROVIDER_SELECTED` | string secreta | api/worker | plataforma |
| Integracoes | `CRM_BASE_URL` | CRM externo | URL | api | engenharia |
| Integracoes | `CRM_API_KEY` | acesso ao CRM | string secreta | api | plataforma |
| Integracoes | `ENRICHMENT_API_KEY` | enriquecimento | string secreta | api/worker | plataforma |
| Integracoes | `EMAIL_PROVIDER_API_KEY` | envio de campanhas | string secreta | api/worker | plataforma |
| Integracoes | `SOCIAL_PUBLISHING_API_KEY` | publicacao social | string secreta | api/worker | plataforma |
| Integracoes | `WEBHOOK_SIGNING_SECRET` | assinatura de webhooks | string secreta | api | engenharia |
| Observabilidade | `SENTRY_DSN` | captura de erro | DSN | api/worker | plataforma |
| Observabilidade | `OTEL_EXPORTER_OTLP_ENDPOINT` | exportador OTLP | URL | api/worker | plataforma |
| Observabilidade | `OTEL_EXPORTER_OTLP_HEADERS` | headers do OTLP | `k=v,k=v` | api/worker | plataforma |
| Observabilidade | `OTEL_SERVICE_NAME` | nome do servico | string | todos | engenharia |
| Seguranca | `ENCRYPTION_KEY` | criptografia de segredos derivados | string 32+ chars | api | plataforma |
| Seguranca | `PORTAL_TOKEN_PEPPER` | hardening de tokens externos | string secreta | api | plataforma |
| Seguranca | `SIGNED_URL_TTL_SECONDS` | vida das URLs assinadas | inteiro | api | engenharia |

## Runbook de provisionamento

1. Criar um projeto Supabase por ambiente e registrar as URLs/chaves publicas e a `SUPABASE_SECRET_KEY` somente nos runtimes que a consomem.
2. Provisionar logins Postgres separados para `DATABASE_URL` (tenant/RLS) e `DATABASE_SERVICE_URL` (operacoes internas minimas); reservar `DIRECT_DATABASE_URL` ao job de migrations.
3. Habilitar Auth, callbacks OAuth e SMTP transacional.
4. Criar bucket privado `artifacts` e buckets adicionais quando definidos no backend.
5. Provisionar Redis TLS isolado por ambiente.
6. Provisionar endpoint OTLP e projeto Sentry.
7. Armazenar secrets em secret manager do ambiente; somente URL e publishable key podem usar `NEXT_PUBLIC_*`.

## Rotacao e ownership

- Secrets de providers e SMTP: ownership de Plataforma, rotacao trimestral ou sob incidente.
- `SUPABASE_SECRET_KEY`, `CRM_API_KEY`, `OPENAI_API_KEY`: acesso apenas backend/worker.
- `PORTAL_TOKEN_PEPPER` e `ENCRYPTION_KEY`: rotacao assistida com janela de dupla leitura quando implementado no backend.

## Guard rails

- Valor vazio conta como ausente.
- URLs invalidas bloqueiam startup.
- `test` e `development` nao podem usar hosts de producao.
- Scanner de secrets deve rodar em CI antes de merge.
