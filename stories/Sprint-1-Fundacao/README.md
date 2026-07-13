# Sprint 1 - Fundacao do projeto

## Objetivo

Entregar um workspace instalavel e executavel, com configuracao de ambiente completa, dependencias fixadas, infraestrutura local, contratos compartilhados e gates de qualidade. Esta Sprint nao implementa regras de negocio nem telas finais.

## Ordem

1. `BH-S1-01` scaffold do monorepo.
2. `BH-S1-02` ambiente e provisionamento.
3. `BH-S1-03` dependencias.
4. `BH-S1-04` contratos e mocks.
5. `BH-S1-05` CI, testes e observabilidade base.

## Entregaveis

| Story | Resultado |
|---|---|
| [BH-S1-01](BH-S1-01-Scaffold-Monorepo.md) | estrutura Next.js, FastAPI, worker e packages |
| [BH-S1-02](BH-S1-02-Ambientes-e-Provisionamento.md) | `.env.example`, Docker e runbook de APIs |
| [BH-S1-03](BH-S1-03-Dependencias.md) | lockfiles e bibliotecas instaladas |
| [BH-S1-04](BH-S1-04-Contratos-e-Mocks.md) | OpenAPI, schemas e mock server |
| [BH-S1-05](BH-S1-05-Qualidade-CI-Observabilidade.md) | lint, testes, CI e telemetria base |

## Done da Sprint

- [ ] Clone limpo sobe frontend, API, worker, Postgres/Supabase local e Redis seguindo o README.
- [ ] `.env.example` cobre todas as variaveis e indica onde provisionar cada uma.
- [ ] Instalar dependencias e rodar gates nao exige conhecimento nao documentado.
- [ ] Frontend consome mocks tipados equivalentes ao contrato OpenAPI.
