# BH-S1-04 - Contratos compartilhados e mock server

**Dominio:** Arquitetura/API/Frontend  
**Depende de:** BH-S1-01  
**Estimativa:** 8 pontos

## Historia

Como equipes de frontend e backend, queremos contratos versionados e mocks deterministas para desenvolver em paralelo sem divergir em payloads, estados ou erros.

## Escopo

- Definir OpenAPI inicial para RF-01 a RF-15, paginação por cursor e `application/problem+json`.
- Gerar tipos TypeScript; criar schemas Zod de fronteira e Pydantic no backend.
- Definir eventos realtime/outbox, estados de tarefa, run, aprovação, conteudo e experimento.
- Criar MSW com cenarios: sucesso, vazio, loading lento, 401, 403, 404, 409, 422, 429 e 500.
- Criar fixtures multi-tenant para todos os papeis e dados das 56 telas.
- Definir endpoint/acao esperado por tela em `docs/CONTRATOS-DE-TELA.md`.

## Contratos minimos

Identidade/organizacao; salas/mensagens/anexos; tarefas/transicoes/runs; aprovacoes/portal; agentes/modelos/skills; workflows/playbooks; conhecimento/memoria/busca; contas/contatos/leads/oportunidades; campanhas/conteudo/publicacoes; experimentos; dashboards/custos; notificacoes; integracoes; auditoria/LGPD.

## Criterios de aceite

- [ ] T01-T56 possuem query/command/evento ou indicacao explicita de tela local.
- [ ] Tipos gerados nao usam `any`.
- [ ] IDs, datas, dinheiro, enums e erros usam representacao consistente.
- [ ] Mocks reproduzem state machines e nao permitem transicoes invalidas.
- [ ] Contract tests detectam quebra entre OpenAPI, Pydantic, tipos TS e fixtures.
- [ ] Exemplos nao contem PII real.

## Fora de escopo

- Persistencia, autenticação real, filas e integracoes reais.
