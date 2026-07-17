# BH-S3-08 - Verificacao independente, seguranca e readiness de producao

**Dominio:** QA/Security/Infra  
**Depende de:** BH-S3-01 a BH-S3-07  
**Estimativa:** 21 pontos

## Historia

Como owner, quero evidência independente de segurança, consistência e operação para decidir o go-live sem aceitar a implementação pela palavra dos autores.

## Escopo

- Revisar migrations, 46 tabelas, funções, grants, RLS, Storage e funções privileged.
- Executar `supabase db advisors`, SQL lint e pgTAP; corrigir findings critical/high.
- Testes adversariais cross-tenant e por papel para leitura, insert, update, delete, RPC, Realtime e Storage.
- Contract tests removendo MSW; E2E das nove jornadas da Sprint 2.
- Testes de concorrência: transition, lease, approval, outbox, webhook e experiment start.
- Performance p95, índices, EXPLAIN, filas, pool e budgets de custo.
- Observabilidade, alertas, dashboards operacionais, runbooks e incident response.
- Backup/restore, RPO/RTO, migração staging, rollback/forward-fix e checklist de release.
- Threat model: auth, BOLA/IDOR, upload, SSRF, webhook, prompt injection, secrets e portal token.

## Evidencias obrigatorias

- Relatório RLS por tabela/operação/papel.
- Relatório E2E T01-T56 e RF-01-RF-15.
- Resultado de advisors, SAST, dependency audit e secret scan.
- Resultado de load/concurrency e restore test.
- Matriz de riscos residuais com owner e prazo.

## Criterios de aceite

- [x] 46/46 tabelas com RLS verificada; zero acesso cross-tenant.
- [ ] 56/56 telas conectadas e contratos sem drift.
- [ ] 15/15 requisitos funcionais com evidência.
- [ ] Zero finding critical/high aberto sem aceite formal.
- [ ] p95 e disponibilidade atendem RNF definidos no PRD em staging.
- [ ] Restore test atende RPO/RTO.
- [ ] Go-live checklist possui aprovação de Produto, Engenharia e Segurança.

Evidencia local atualizada em 2026-07-15: reset e 43 migrations passaram com 21
arquivos/306 assercoes pgTAP; lint/advisors de banco passaram; E2E mock passou
34/34 e E2E real sem MSW passou 20/20, ambos em desktop/mobile com Axe. Restore
local passou em 63,23 s, preservando catalogo/hash de 55 tabelas publicas e
quatro schemas. Os p95 locais de busca vetorial, notificacoes, salas e tarefas
ficaram abaixo de 500 ms. Alertas, deploy, providers, backup/restore e carga em
staging nao foram executados; por isso os criterios de staging, restore para
readiness de producao, 56/56 telas e go-live permanecem desmarcados.

### Auditoria dos criterios abertos (2026-07-14)

| Criterio | Evidencia local | Lacuna para aceite |
|---|---|---|
| 56/56 telas conectadas e contratos sem drift | `verify-screen-contracts` passa com 56 telas mapeadas, `contracts:check` passa e o fixture guard nao encontra import direto fora da fronteira de mocks | falta relatorio individual de 56 jornadas contra backend real; a suite real cobre jornadas representativas |
| 15/15 requisitos funcionais | RF-01 a RF-15 possuem stories e rastreabilidade; APIs, migrations, testes e E2E real cobrem jornadas representativas | efeitos externos de RF-04/RF-07 e outros fluxos dependem de providers homologados; exactly-once externo nao foi comprovado |
| Zero finding critical/high aberto | secret scan e `pip-audit` nao apontaram vulnerabilidade conhecida nas dependencias auditaveis | `npm audit` ficou inconclusivo por HTTP 410 do registry e pacotes Python locais nao foram auditaveis; tambem falta aceite independente consolidado |
| p95 e disponibilidade em staging | a medicao Postgres/RLS local registrada fica abaixo de 500 ms | nao ha carga ponta a ponta nem janela de disponibilidade medida em staging |
| Restore atende RPO/RTO | restore logico local atende amplamente o RTO de oito horas e compara dados/catalogo | nao mede RPO, blobs de Storage, backup gerenciado, banda ou volume de staging |
| Aprovacao de go-live | checklist e runbooks existem | faltam evidencias de staging e aprovacoes formais de Produto, Engenharia e Seguranca |

Os checks locais desta auditoria tambem passaram para handoff T01-T56, UI
primitives, contratos de tela e segredo obvio. A auditoria npm nao passou nem
falhou por vulnerabilidade: o registry respondeu HTTP 410. Esses
resultados reduzem risco local, mas nao promovem os criterios externos acima.

## Fora de escopo

- Novos recursos, redesign ou expansão de providers durante estabilização.
