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

Evidencia local registrada em 2026-07-13: 69 assercoes pgTAP antes da migration
posterior, 18/18 execucoes E2E sem MSW em desktop/mobile, performance local e
restore local com veredito independente PASS. O restore local nao comprova RPO
nem backup gerenciado de staging; por isso os criterios de staging, restore
para readiness de producao, 56/56 telas e go-live permanecem desmarcados.

## Fora de escopo

- Novos recursos, redesign ou expansão de providers durante estabilização.
