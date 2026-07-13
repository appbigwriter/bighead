# BH-S2-02 - Acesso, onboarding, home e produtividade

**Telas:** T01-T09  
**Depende de:** BH-S2-01  
**Estimativa:** 13 pontos

## Historia

Como membro, quero entrar, escolher meu contexto e visualizar prioridades para iniciar o trabalho com segurança.

## Escopo funcional

- Login, provedores, magic link/senha, recuperacao e redefinicao.
- Aceite/recusa de convite com expiracao, revogacao e idempotencia.
- Onboarding de perfil/organizacao e convite inicial.
- Seletor de organizacao com limpeza de cache/subscriptions.
- Home com tarefas, SLA, aprovacoes, falhas, custos e resultados.
- Busca global/command palette; central de notificacoes; perfil e sessoes.

## Estados e casos de borda

Usuario sem membership, suspenso, convite de outro email, token usado, organizacao removida, sessao expirada no meio do wizard, home parcial, busca sem resultado e notificacao de recurso removido.

## Contratos backend

Documentar request/response e erros de auth, profiles, organizations, memberships, invites, dashboard summary, global search, notifications e sessions. Marcar queries paralelas, chaves de cache e eventos de invalidação.

## Criterios de aceite

- [x] T01-T09 possuem rotas, estados e testes de componente.
- [x] Resposta de login nao permite enumerar email.
- [x] Troca de tenant remove dados visuais do tenant anterior antes da nova renderizacao.
- [x] Home permite drill-down preservando filtros.
- [x] Atalhos de command palette sao acessiveis por teclado.
- [x] Documento `acesso-organizacoes.md` permite implementar APIs sem inferir campos.

## Evidencia

Matriz/playbooks T01-T09 e suite web aprovados; testes da fronteira comprovam isolamento concorrente de tenant, header e `AbortSignal` por request. Todo erro do provider de login e normalizado para `invalid_credentials` e quatro classes de falha compartilham o mesmo teste. T06 incorpora `period` e `risk` na URL de cada drill-down. T07 move foco com ArrowDown e executa Alt+1..9 por handler global com cleanup. `acesso-organizacoes.md` explicita requests, responses, erros, cache e eventos; `pnpm sprint2:access-check` compara propriedades, tipos, required, parametros e status com o OpenAPI canonico, inclusive `AnalyticsSummaryResponse` tipado.

## Fora de escopo

- Auth, email e dados reais; permanecem mockados nesta Sprint.
