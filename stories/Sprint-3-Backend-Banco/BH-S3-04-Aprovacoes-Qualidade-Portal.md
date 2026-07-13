# BH-S3-04 - Aprovacoes, Sentinel QA e portal externo

**Dominio:** Backend/Database/Security  
**Depende de:** BH-S3-02, BH-S3-03  
**Estimativa:** 21 pontos

## Historia

Como revisor, quero avaliar e decidir entregas com regras proporcionais ao risco, impedindo execução protegida antes da autorização.

## Escopo

- Implementar `approval_requests`, `approval_decisions`, `external_approval_links`, `qa_scorecards`, `qa_evaluations`.
- Motor versionado de política: risco, tipo, canal, valor, quorum, ordem, segregacao e expiração.
- Sentinel executa checklist e persiste evidencias; override exige papel e justificativa.
- Decisão humana imutável e idempotente; nova rodada cria novo request.
- Portal por token aleatório armazenado somente como hash, TTL, revogacao, limite de usos e rate limit.
- Integrar workflow: passo protegido permanece `waiting_human`; decisão válida emite evento de continuação.

## Criterios de aceite

- [x] APIs T20-T24 substituem mocks.
- [x] Autoaprovacao e recusada quando segregacao esta ativa.
- [x] Duas decisoes concorrentes nao sobrescrevem a primeira.
- [x] Link expirado/revogado/esgotado nao revela recurso.
- [x] Token bruto nao é persistido nem logado.
- [x] Run nao avanca antes da aprovação aplicável.
- [x] Scorecard e avaliação preservam versão histórica.

Evidencia: a migration `20260713140542_preserve_published_scorecard_versions.sql`
torna versoes publicadas e avaliacoes historicas imutaveis para update/delete e
impede avaliar contra scorecard draft. Nove assercoes pgTAP comprovam bloqueios,
criacao de nova versao, coexistencia e interpretacao pela versao original apos
reset integral das migrations.

## Fora de escopo

- Publicacao em redes/CRM e dashboards agregados.
