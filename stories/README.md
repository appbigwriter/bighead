# Backlog de implementacao - BigHead V3

Este backlog transforma os documentos em `prd/` em stories executaveis. A ordem de implementacao e: Sprint 1 -> Sprint 2 -> Sprint 3. A Sprint 2 entrega o frontend completo com contratos mockados; a Sprint 3 substitui os mocks por APIs, workers e persistencia reais.

## Convencoes

- IDs: `BH-S1-NN`, `BH-S2-NN`, `BH-S3-NN`.
- Done significa comportamento verificavel, nao apenas arquivo criado.
- Cada story declara dependencias, fora de escopo, casos de borda e evidencias.
- Contratos frontend/backend ficam em `packages/contracts` e devem permanecer retrocompativeis dentro da Sprint.
- Os documentos desatualizados `fbr-arquitetura.md`, `DESIGN_STANDARDS.md` e `securitycoderules.md` nao sao fontes deste backlog.

## Sprints

| Sprint | Objetivo | Stories |
|---|---|---:|
| [Sprint 1](Sprint-1-Fundacao/README.md) | scaffold, ambientes, dependencias, contratos e qualidade | 5 |
| [Sprint 2](Sprint-2-Frontend/README.md) | todas as 56 telas, componentes, estados e mocks documentados | 8 |
| [Sprint 3](Sprint-3-Backend-Banco/README.md) | APIs, workers, Supabase, RLS, integrações e observabilidade | 8 |

## Gate global

- [ ] Nenhum requisito RF-01 a RF-15 sem story.
- [ ] Nenhuma tela T01 a T56 sem story frontend e contrato de backend.
- [ ] Nenhuma tabela do schema sem owner de implementacao e teste.
- [ ] Testes unitarios, integracao, RLS e E2E das jornadas criticas passam.
- [ ] Secrets nao estao versionados e `.env.example` nao contem valores reais.

## Rastreabilidade dos requisitos

| Requisito | Frontend | Backend/Banco |
|---|---|---|
| RF-01 Identidade/organizacoes | BH-S2-02 | BH-S3-01 |
| RF-02 Salas/mensagens/anexos | BH-S2-03 | BH-S3-02 |
| RF-03 Tarefas/state machine | BH-S2-04 | BH-S3-02 |
| RF-04 Orquestracao | BH-S2-04, BH-S2-05 | BH-S3-03 |
| RF-05 Agentes/modelos/prompts/skills | BH-S2-05 | BH-S3-03 |
| RF-06 Workflows/playbooks | BH-S2-05 | BH-S3-03 |
| RF-07 Execucao/filas/artefatos | BH-S2-04 | BH-S3-02, BH-S3-03 |
| RF-08 Aprovacoes/Sentinel | BH-S2-05 | BH-S3-04 |
| RF-09 Portal externo | BH-S2-05 | BH-S3-04 |
| RF-10 Memoria/conhecimento | BH-S2-06 | BH-S3-05 |
| RF-11 Lead intelligence/funil | BH-S2-06 | BH-S3-06 |
| RF-12 Conteudo/campanhas | BH-S2-06 | BH-S3-06 |
| RF-13 Experimentos | BH-S2-07 | BH-S3-06 |
| RF-14 Analytics fechado | BH-S2-07 | BH-S3-07 |
| RF-15 Notificacoes/auditoria | BH-S2-01, BH-S2-07 | BH-S3-07 |
