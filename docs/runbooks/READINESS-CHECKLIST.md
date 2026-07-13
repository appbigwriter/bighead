# Checklist de readiness operacional

Atualizado em 2026-07-13. Marcação significa evidência registrada no repositório;
itens remotos permanecem abertos.

## Comprovado localmente

- [x] Migrations reproduzíveis por reset completo.
- [x] Seed determinista e pgTAP/RLS.
- [x] DB lint e advisors sem bloqueador na execução registrada.
- [x] Suites API, worker, web e contratos executadas.
- [x] Integrações locais Supabase e outbox/Redis executadas.
- [x] E2E representativo desktop/mobile sem MSW executado.
- [x] Restore lógico local com comparação de dados e catálogo.
- [x] Performance Postgres/RLS local abaixo do orçamento registrado.
- [x] Runbooks operacionais documentados.

## Staging — não comprovado

- [ ] Projeto/infra de staging provisionados e inventariados.
- [ ] Migrations aplicadas por pipeline/operador único e `dry-run` arquivado.
- [ ] Deploy de web/API/worker documentado e executado.
- [ ] E2E sem MSW contra staging.
- [ ] Providers externos com round-trip e falhas exercitadas.
- [ ] Realtime reconnect/ordenação/deduplicação ponta a ponta.
- [ ] Carga representativa incluindo API, pooler e rede.
- [ ] Restore de backup gerenciado/PITR com blobs de Storage.
- [ ] RPO <= 24 h e RTO <= 8 h medidos.
- [ ] OTLP/Sentry, dashboards e alertas testados.
- [ ] Game day de incidente e rotação de secret executados.

## Inputs necessários para iniciar staging

- [ ] Domínios públicos de web e API e provedor de hosting/container.
- [ ] Projeto Supabase Cloud: URL, publishable key, secret key, DSNs pooler,
  service e direto; nenhum valor deve ser commitado.
- [ ] Redis TLS gerenciado.
- [ ] SMTP transacional configurado no Supabase Auth, Site URL e redirect URLs.
- [ ] Scanner antimalware HTTPS e credencial server-only.
- [ ] Endpoint/credencial de pelo menos um CRM e nomes dos providers aprovados.
- [ ] Chaves OpenAI, Anthropic e Google, modelos principal/fallback, dimensao de
  embeddings, budget e politica de retencao/regiao.
- [ ] Sentry/OTLP e secret manager escolhidos.
- [ ] Owners de Produto, Engenharia/Plataforma e Seguranca para o aceite.

## Produção/go-live — não aprovado

- [ ] Plataforma e comandos de deploy/rollback definidos.
- [ ] Backup/PITR, retenção e monitoramento ativos.
- [ ] Error budget/SLOs aprovados e instrumentados.
- [ ] Capacidade e rate limits aprovados para volume esperado.
- [ ] Owners e plantão definidos para todos os providers.
- [ ] Threat model e checklist de segurança aprovados.
- [ ] Plano de release/forward-fix ensaiado em staging.
- [ ] Aprovação formal de Produto.
- [ ] Aprovação formal de Engenharia/Plataforma.
- [ ] Aprovação formal de Segurança/Privacidade.

**Estado:** não pronto para declarar staging validado ou go-live.
