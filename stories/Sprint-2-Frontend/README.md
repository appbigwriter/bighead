# Sprint 2 - Frontend completo e contratos de backend

## Objetivo

Implementar toda a experiência visual T01-T56 sobre mocks contratuais, responsiva e acessível. Cada jornada deve produzir documentação suficiente para o backend substituir MSW sem alterar componentes.

## Stories e cobertura

| Story | Telas | Dominio |
|---|---|---|
| [BH-S2-01](BH-S2-01-Design-System-Shell.md) | componentes transversais | design system e shell |
| [BH-S2-02](BH-S2-02-Acesso-Organizacoes.md) | T01-T09 | identidade e produtividade |
| [BH-S2-03](BH-S2-03-Salas-Mensagens.md) | T10-T13 | colaboracao |
| [BH-S2-04](BH-S2-04-Tarefas-Execucoes.md) | T14-T19 | operacao |
| [BH-S2-05](BH-S2-05-Aprovacoes-Automacao.md) | T20-T34 | governanca e automacao |
| [BH-S2-06](BH-S2-06-Conhecimento-Comercial.md) | T35-T45 | conhecimento, CRM e conteudo |
| [BH-S2-07](BH-S2-07-Analytics-Administracao.md) | T46-T56 | experimentos, analytics e admin |
| [BH-S2-08](BH-S2-08-E2E-Acessibilidade-Documentacao.md) | T01-T56 | verificacao e handoff |

## Done da Sprint

- [x] As 56 telas existem e usam exclusivamente contratos/mocks de `BH-S1-04`.
- [ ] Desktop e mobile cobrem loading, vazio, erro, offline e sem permissao.
- [ ] Storybook/catalogo documenta componentes e estados.
- [x] `docs/frontend-backend/` descreve dados, comandos, eventos e erros por jornada.
- [x] E2E e acessibilidade passam nas jornadas criticas.

## Evidencias verificadas

- Gates: lint, typecheck, testes raiz, build e guards aprovados.
- Testes web: 141 aprovados.
- E2E: 20/20 execucoes aprovadas (10 cenarios em desktop e mobile), com Axe sem violacao critica/seria.
- Fronteira de dados: transporte assincrono compativel com HTTP e contexto de tenant isolado por request, cobertos por testes.
- Revisao independente: veredito `PASS` apos a ultima rodada de correcoes.

Os itens ainda abertos acima nao possuem evidencia suficiente nesta rodada para serem declarados concluidos.
