# BH-S2-01 - Design system, shell e componentes transversais

**Dominio:** Frontend/UX  
**Depende de:** Sprint 1  
**Estimativa:** 13 pontos

## Historia

Como usuario, quero uma interface coerente, rápida e acessível para compreender estado, risco e proxima acao em qualquer modulo.

## Escopo

- Definir direcao visual própria do BigHead, tokens de cor, tipografia, espacamento, radius, sombra, motion e breakpoints.
- Implementar light/dark, shell responsiva, sidebar, topbar, breadcrumbs, command palette, busca, seletor de organizacao, ajuda e notificacoes.
- Criar biblioteca: botao, input, select, combobox, dialog, drawer, tabs, table, kanban, badge, avatar, tooltip, toast, skeleton, empty/error/permission/offline states.
- Criar componentes de dominio: `RiskBadge`, `CostBadge`, `AgentIdentity`, `SourceCitation`, `StatusTimeline`, `ArtifactPreview`, `DiffViewer`, `PermissionGuard`, `DestructiveActionDialog`, uploader e filtros/views salvas.
- Documentar Storybook/catalogo, variantes, props e acessibilidade.

## Regras

- Foco visivel, navegacao por teclado, contraste AA e reduced motion.
- Mobile prioriza inbox, chat, tarefas e aprovacoes.
- Nenhuma cor isolada comunica status sem texto/icone.
- Atualizacao otimista somente para acao reversivel.

## Contrato backend a documentar

`GET /me/context`, `GET /organizations`, `GET/PATCH /preferences`, `GET/PATCH /notifications`, busca global e contadores da shell; incluir cache, paginação e eventos realtime.

## Criterios de aceite

- [x] Componentes transversais possuem exemplos de todos os estados.
- [x] Shell funciona em 360, 768, 1280 e 1920 px sem scroll horizontal indevido.
- [ ] Tema e preferencias persistem sem flash visual.
- [ ] Axe e navegacao manual por teclado passam.
- [ ] Nenhuma tela futura precisa criar botão, modal ou estado de erro ad hoc.

## Evidencia

O catalogo demonstra Loading com skeleton/`aria-busy`, Vazio com CTA, Erro com `alert`/retry, Sem permissao sem acao, Offline com reconnect e Sucesso com proxima acao; teste semantico cobre papeis e controles. O E2E mede `scrollWidth <= clientWidth + 1` em 360, 768, 1280 e 1920 px nos projetos desktop/mobile, com 8/8 casos aprovados. A suite existente cobre teclado automatizado, reduced motion e Axe sem violacao critica/seria. Persistencia sem flash, navegacao manual completa e prova de que nenhuma tela futura criara componente ad hoc permanecem abertas.

## Fora de escopo

- Identidade visual de campanhas de clientes e dados reais.
