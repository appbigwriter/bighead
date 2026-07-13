# BH-S3-03 - Orquestracao, agentes, skills, workflows e workers

**Dominio:** Backend/Worker/Database/IA  
**Depende de:** BH-S3-01, BH-S3-02  
**Estimativa:** 34 pontos

## Historia

Como operador, quero que tarefas sejam roteadas e executadas por agentes/skills com custo, justificativa e recuperacao controlados.

## Escopo de dados

`model_providers`, `models`, `agents`, `agent_versions`, `skills`, `agent_version_skills`, `workflows`, `workflow_versions`, `playbooks`, `runs`, `run_steps`, `tool_calls`, `cost_events`.

## Escopo funcional

- CRUD/versionamento/publicacao/rollback de agentes, prompts, modelos, preços, skills, workflows e playbooks.
- Validador de grafo e schemas; simulador sem side effects; analise de impacto.
- Orquestrador: intenção, domínio, risco, custo, urgencia, agente/workflow e justificativa persistida.
- ARQ/Redis workers com idempotency key, lease, heartbeat, backoff, dead-letter e cancelamento cooperativo.
- Gateway de providers com timeout, circuit breaker, fallback e Structured Output validado.
- Execução de skills por allowlist, secret reference e aprovação prévia quando exigida.
- Custos append-only com preço vigente no instante do evento.

## APIs e eventos

Implementar T25-T34 e T17-T18; `task.created`, `run.step.requested`, `run.step.completed`, `run.failed`, `approval.required`. Usar outbox para publicar somente após commit.

## Criterios de aceite

- [x] Mocks T25-T34 são substituídos sem quebra contratual.
- [x] Workflow publicado e imutavel; run preserva versao original.
- [ ] Job entregue duas vezes produz um unico efeito externo.
- [x] Worker morto perde lease e job e retomado com tentativa registrada.
- [x] Timeout/retry respeita politica da skill e termina em dead-letter.
- [x] Custo total reconcilia eventos de provider e tarefa.
- [x] Nenhum secret aparece em DB, logs ou payload de UI.

## Casos de borda

Provider fora, fallback incompatível, resposta estruturada inválida, cancelamento durante tool call, preço alterado no meio do run, grafo com ciclo, skill desativada depois da fila.

Evidencia registrada em 2026-07-13: `012_run_worker_hardening.sql` passou 22/22,
incluindo claim concorrente, retomada de lease com incremento de tentativa, esgotamento em
dead-letter, conflito de fingerprint, dedupe de `provider_event_id` e reconciliacao de
custo. O dispatcher unitario comprova chave estavel em replay, mas o criterio de efeito
externo permanece aberto ate o provider real comprovar idempotencia. Retry/backoff generico
esta comprovado. A fila agora resolve `timeout_seconds` e `max_retries` das skills
referenciadas pela versao imutavel do workflow ao criar o run, persiste a politica efetiva
em `policy_snapshot` e mantem o snapshot nos retries manuais. O dispatcher aplica o timeout
capturado e falha fechado quando `maxAttempts`/backoff divergem das colunas que governam o
retry no banco. Testes unitarios cobrem lookup multi-skill, skill ausente/desabilitada,
timeout real por cancelamento e drift da politica. O teste opt-in
`test_run_policy_integration.py` passou no Supabase local e comprova que `max_retries=1`
produz duas tentativas, backoff positivo e `dead_letter`. A migration
`20260713174105_emit_run_failed_outbox.sql` publica `run.failed` atomicamente e uma unica
vez tanto no esgotamento normal quanto na recuperacao de lease; o retry manual grava run,
outbox e auditoria na mesma transacao. A revisao independente final foi `PASS` para a
politica de retry. A comprovacao de idempotencia no provider externo continua
dependente das credenciais e do adapter homologado.
O smoke opt-in `test_runs_integration.py` passou via PostgREST/RPC real, com claim,
reserva do efeito, executor deterministico restrito ao teste, completion e custo. Em runtime,
o cron e o `HttpRunExecutor` estao ligados; sem URL/chave reais, o job falha antes do claim.

## Fora de escopo

- Regra de aprovação e RAG, tratadas nas stories seguintes.
