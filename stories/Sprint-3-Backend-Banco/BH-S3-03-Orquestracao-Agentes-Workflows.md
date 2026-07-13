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

- [ ] Mocks T25-T34 são substituídos sem quebra contratual.
- [ ] Workflow publicado e imutavel; run preserva versao original.
- [ ] Job entregue duas vezes produz um unico efeito externo.
- [ ] Worker morto perde lease e job e retomado com tentativa registrada.
- [ ] Timeout/retry respeita politica da skill e termina em dead-letter.
- [ ] Custo total reconcilia eventos de provider e tarefa.
- [ ] Nenhum secret aparece em DB, logs ou payload de UI.

## Casos de borda

Provider fora, fallback incompatível, resposta estruturada inválida, cancelamento durante tool call, preço alterado no meio do run, grafo com ciclo, skill desativada depois da fila.

## Fora de escopo

- Regra de aprovação e RAG, tratadas nas stories seguintes.
