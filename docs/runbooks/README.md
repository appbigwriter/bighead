# Runbooks operacionais do BigHead

Estes runbooks descrevem o processo mínimo para validar staging e, somente
depois de aprovação formal, operar produção. Eles não registram staging como
provisionado e não autorizam go-live.

## Índice

- [Staging e produção](STAGING-PRODUCTION.md)
- [Release, rollback e forward-fix](RELEASE-ROLLBACK-FORWARD-FIX.md)
- [Resposta a incidentes](INCIDENT-RESPONSE.md)
- [Backup, restore, RPO e RTO](BACKUP-RESTORE.md)
- [Observabilidade, SLOs e alertas](OBSERVABILITY-SLOS.md)
- [Handoff de APIs e providers externos](EXTERNAL-APIS-HANDOFF.md)
- [Readiness operacional](READINESS-CHECKLIST.md)

## Regras comuns

1. Um operador nomeado conduz a mudança; outro revisa migrations, escopo e
   evidências.
2. Secrets são lidos do secret manager. Nunca aparecem em terminal gravado,
   ticket, log, commit ou variável `NEXT_PUBLIC_*`.
3. Mudanças de schema passam somente por migrations versionadas. Não alterar
   migrations aplicadas nem editar schema remoto pelo Dashboard.
4. Antes de qualquer escrita remota, registrar ambiente, commit, janela,
   operador, aprovadores, backup/restore point e critério de abortar.
5. Staging e produção usam projetos, Redis, buckets, providers e secrets
   separados.
6. `supabase db push --dry-run` é inspeção; `supabase db push` altera o banco e
   exige aprovação da janela.
7. Falha sem rollback seguro exige forward-fix. `migration repair` corrige
   histórico conhecido; não desfaz SQL e não é procedimento normal de release.

## Evidência atualmente disponível

Os números locais vigentes estão em [SPRINT-3-STATUS.md](../SPRINT-3-STATUS.md).
Eles comprovam reset, pgTAP, lint/advisors, integrações, restore lógico e carga
locais. Não comprovam staging, providers externos, backups gerenciados, PITR,
Storage blobs remotos, alertas ou disponibilidade mensal.

## Referências operacionais oficiais

- [Supabase: deployment e branching](https://supabase.com/docs/guides/deployment)
- [Supabase: migrations](https://supabase.com/docs/guides/deployment/database-migrations)
- [Supabase: production checklist](https://supabase.com/docs/guides/deployment/going-into-prod)
- [Supabase: database backups](https://supabase.com/docs/guides/platform/backups)
- [Supabase: logs](https://supabase.com/docs/guides/telemetry/logs)
- [Supabase: Metrics API](https://supabase.com/docs/guides/telemetry/metrics)
