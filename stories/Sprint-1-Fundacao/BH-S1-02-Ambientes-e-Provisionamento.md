# BH-S1-02 - Ambientes, `.env.example` e provisionamento

**Dominio:** Infra/Security  
**Prioridade:** bloqueadora  
**Depende de:** BH-S1-01  
**Estimativa:** 8 pontos

## Historia

Como owner técnico, quero todas as integracoes e variaveis catalogadas para provisionar desenvolvimento, homologacao e producao sem descobrir dependencias durante a implementacao.

## Escopo

- Criar `.env.example` raiz e exemplos específicos por app, sem valores reais.
- Criar `docs/PROVISIONAMENTO.md` com finalidade, origem, formato, ambiente e responsavel de cada chave.
- Criar Docker Compose para Redis e componentes locais suportados; usar Supabase CLI para stack local.
- Separar `development`, `test`, `staging` e `production`; definir validacao de startup com Pydantic/Zod.

## Variaveis obrigatorias

| Grupo | Variaveis minimas |
|---|---|
| Aplicacao | `APP_ENV`, `APP_URL`, `API_URL`, `CORS_ORIGINS`, `LOG_LEVEL` |
| Supabase | `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `DATABASE_URL`, `DIRECT_DATABASE_URL`, `STORAGE_BUCKET` |
| Redis | `REDIS_URL`, `QUEUE_NAME`, `JOB_LEASE_SECONDS` |
| Auth | providers OAuth escolhidos, URLs de callback e SMTP transacional |
| IA | chaves por provider aprovado, modelo default/fallback, embedding model/dimension, budgets |
| Integracoes | CRM, enriquecimento, email, social/publishing, webhook signing |
| Observabilidade | `SENTRY_DSN`, OTLP endpoint/headers, service names |
| Seguranca | encryption key, webhook secret, portal token pepper, signed URL TTL |

Variaveis de providers ainda nao escolhidos devem existir comentadas e marcadas `OPTIONAL_UNTIL_PROVIDER_SELECTED`; nao inventar nomes de APIs comerciais.

## Criterios de aceite

- [ ] Cada uso futuro descrito no PRD possui variavel ou decisao documentada.
- [ ] Startup falha com lista de variaveis obrigatorias ausentes, sem imprimir secrets.
- [ ] `.env.example` contem placeholders seguros e pode ser copiado para ambiente local.
- [ ] Runbook explica como criar projeto Supabase, buckets, OAuth, Redis e observabilidade.
- [ ] Rotacao e ownership de secrets estao documentados.
- [ ] Scanner confirma zero segredo real no Git.

## Casos de borda

- [ ] Chave vazia e tratada como ausente.
- [ ] URL invalida e rejeitada antes do startup.
- [ ] Ambiente de teste nao pode apontar acidentalmente para banco de producao.

## Fora de escopo

- Comprar planos, provisionar contas externas ou escolher unilateralmente providers pendentes.
