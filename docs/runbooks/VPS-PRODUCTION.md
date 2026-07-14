# Deploy BigHead em VPS própria

## Decisão de ambiente

O primeiro ambiente remoto será produção controlada, sem staging separado, por
decisão do owner em 2026-07-13. Isso não reduz os gates: migrations passam por
`dry-run`, o deploy usa smoke reversível e nenhuma carga, reset, seed ou restore
é executado contra produção.

Domínios:

- frontend: `https://head.fbr.news`;
- API: `https://apibig.fbr.news`.

## O que deve ser disponibilizado

1. VPS Linux x86_64 com no mínimo 4 vCPU, 8 GiB RAM e 80 GiB SSD. ClamAV é o
   principal consumidor de memória; 4 GiB pode funcionar, mas não é o perfil
   recomendado para web, API, worker, Redis e scanner no mesmo host.
2. Ubuntu 24.04 LTS ou Debian 12 atualizado, Docker Engine e plugin Docker
   Compose.
3. Usuário SSH nominal com chave, `sudo`, diretório `/opt/bighead` e acesso ao
   repositório ou registry. Não habilitar login SSH por senha para root.
4. Registros DNS `A` e, se houver IPv6, `AAAA` para os dois domínios apontando à
   VPS. Portas públicas: TCP 80/443 e UDP 443; SSH restrito aos IPs de operação.
5. E-mail operacional para ACME. Caddy emite e renova TLS automaticamente.
6. Arquivo `/opt/bighead/.env.production`, owner root/deploy e modo `0600`,
   preenchido a partir de `deploy/.env.production.example`. Nunca enviar esse
   arquivo ao Git.
7. Projeto Supabase Cloud e variáveis remotas: Project URL, publishable/secret
   keys, DSNs de aplicação, serviço e migration, project ref, access token e
   database password. `DATABASE_URL` e `DATABASE_SERVICE_URL` devem usar roles
   distintas e TLS.
8. Supabase Auth com Site URL `https://head.fbr.news`, redirect exato
   `https://head.fbr.news/auth/callback` e SMTP transacional testado no painel.
9. Dois provedores LLM distintos entre OpenAI, Anthropic e Google, respectivos
   nomes de modelo e chaves server-only. Só chaves dos provedores escolhidos são
   obrigatórias.

### Roles do banco exigidas pela API

Não reutilize `postgres` nas duas conexões. Antes do deploy, conecte pelo DSN
direto administrativo e crie o login tenant sem senha no SQL; defina a senha
depois pelo comando interativo `\password`, para não deixá-la no histórico:

```sql
create role bighead_app_login login noinherit;
grant authenticated to bighead_app_login;
```

`DATABASE_URL` usa `bighead_app_login` e executa cada operação tenant com
`SET LOCAL ROLE authenticated` e claims RLS. `DATABASE_SERVICE_URL` usa a role
administrativa `postgres` do projeto Supabase, somente no container da API;
ela nunca é exposta ao frontend. Os dois DSNs devem usar o pooler, TLS e roles
distintas. Valide o login tenant antes do deploy:

```sql
set role authenticated;
reset role;
```

Se o pooler exigir o formato `<role>.<project-ref>`, copie o formato exibido em
Supabase Dashboard > Connect e substitua somente a role. Nunca coloque essas
senhas em migration ou no repositório.

OAuth Google/Microsoft, CRM externo, Sentry e OTLP são opcionais. O CRM do PRD
é interno. Redis e ClamAV são provisionados privadamente pelo Compose e não
publicam portas no host.

## Preparação segura

```bash
sudo install -d -m 0750 -o deploy -g deploy /opt/bighead
cd /opt/bighead
cp deploy/.env.production.example .env.production
chmod 0600 .env.production
docker compose --env-file .env.production -f compose.production.yml config -q
```

Antes da primeira migration, carregar `SUPABASE_ACCESS_TOKEN` e
`SUPABASE_DB_PASSWORD` no ambiente do operador e conferir o projeto exibido:

```bash
pnpm exec supabase link --project-ref "$SUPABASE_PROJECT_REF"
pnpm exec supabase migration list
pnpm exec supabase db push --dry-run
```

O `db push` real só ocorre após revisão do dry-run e confirmação explícita do
project ref. Nunca usar `db reset`, `--include-seed` ou restore-test em produção.

## Deploy

```bash
docker compose --env-file .env.production -f compose.production.yml build --pull
docker compose --env-file .env.production -f compose.production.yml up -d
docker compose --env-file .env.production -f compose.production.yml ps
curl --fail https://apibig.fbr.news/health/live
curl --fail https://apibig.fbr.news/health/ready
curl --fail --head https://head.fbr.news/login
```

O Caddy recebe tráfego público. Web e API continuam vinculados a localhost,
enquanto Redis e ClamAV existem apenas na rede Docker.

## Homologação no ambiente

Executar com tenant e usuários de smoke dedicados:

1. login, logout, recuperação e sessão expirada;
2. isolamento entre dois tenants;
3. conversa, Realtime/reconnect, mensagem para tarefa e transição;
4. aprovação, histórico, autoaprovação 403 e conflito 409;
5. lead, follow-up idempotente e mudança de pipeline;
6. upload limpo, arquivo EICAR rejeitado e signed download;
7. run LLM principal/fallback, outbox, Redis e worker;
8. E2E desktop/mobile, Axe, fixture guard e performance;
9. backup Supabase/PITR e restauração em destino isolado, nunca sobre produção.

Produto, Engenharia e Segurança registram o aceite somente depois dessas
evidências. Falha de readiness, RLS, upload, worker ou TLS aborta o lançamento.

## Rollback

Publique web/API/worker com tags imutáveis e registre as três tags anteriores
antes de cada release. Para rollback de aplicação, restaure essas tags no
arquivo `0600`, valide o Compose e recrie somente os serviços de aplicação:

```bash
docker compose --env-file .env.production -f compose.production.yml config -q
docker compose --env-file .env.production -f compose.production.yml up -d --no-deps web api worker
```

Migrations são forward-only. Não faça rollback destrutivo do banco em produção;
em caso de incompatibilidade, interrompa o tráfego/mutações, aplique uma
migration corretiva revisada e restaure a versão de aplicação compatível. Um
restore só pode ocorrer em projeto Supabase isolado e após decisão explícita de
incidente.
