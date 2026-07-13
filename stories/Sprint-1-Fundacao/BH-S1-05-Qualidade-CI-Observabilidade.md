# BH-S1-05 - Qualidade, CI e observabilidade base

**Dominio:** QA/DevEx/Infra  
**Depende de:** BH-S1-01, BH-S1-03, BH-S1-04  
**Estimativa:** 8 pontos

## Historia

Como equipe, queremos gates automatizados e telemetria desde o primeiro commit para impedir regressao silenciosa e diagnosticar falhas entre web, API e worker.

## Escopo

- Frontend: ESLint, formatter, typecheck, Vitest, Testing Library, Playwright e axe.
- Backend: Ruff, mypy, Pytest, coverage, Bandit e pip-audit.
- Banco: SQLFluff, Supabase lint/advisors quando disponivel e pgTAP.
- CI: install congelado, lint, typecheck, testes, build, auditoria e artifacts.
- Observabilidade: JSON logs, `trace_id`, request ID, OpenTelemetry e captura de erros sem dados sensiveis.
- Definir budgets: cobertura por dominio, bundle, latencia de mocks e acessibilidade.

## Criterios de aceite

- [ ] Pull request nao pode mergear com gate obrigatório falhando.
- [ ] Trace iniciado no frontend aparece correlacionado em API e worker de exemplo.
- [ ] Logs mascaram secrets, tokens, conteudo sensivel e PII configurada.
- [ ] Teste E2E smoke navega login mock -> home -> tarefa.
- [ ] Axe nao encontra violacao critica na shell inicial.
- [ ] README explica como reproduzir cada gate localmente.

## Fora de escopo

- Dashboards de negocio e alertas de producao definitivos.
