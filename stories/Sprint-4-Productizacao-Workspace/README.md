# Sprint 4 - BigHead vira produto

## Objetivo

Substituir moldura de catalogo pelo nucleo operacional do BigHead. Usuario deve entrar, localizar trabalho, conversar, criar tarefa, obter aprovacao e continuar execucao sem ver T-codes, endpoints, fixtures ou texto de QA.

**Duracao:** 15 dias uteis  
**Capacidade planejada:** 30 pessoa-dias de implementacao (2 lanes x 15 dias) + QA/revisao independente  
**WIP:** maximo 2 stories em implementacao  
**Login:** congelado  

**Orcamento:** 24 pessoa-dias planejados + 6 pessoa-dias de buffer. Escopo integral; sem corte silencioso.

## Escopo fechado

Rotas productizadas nesta sprint:

- `/operacao/home`
- `/operacao/busca-global`
- `/operacao/notificacoes`
- `/acesso/organizacoes`
- `/colaboracao/salas`
- `/colaboracao/sala`
- `/tarefas/inbox`
- `/tarefas/criar`
- `/tarefas/detalhe`
- `/governanca/aprovacoes`
- `/governanca/aprovacao-detalhe`
- `/comercial/leads`
- `/comercial/lead-detalhe`
- `/comercial/pipeline`

Rotas restantes continuam funcionais, mas saem da navegacao primaria e recebem classificacao no mapa de migracao. Productizacao delas fica para Sprints 5-7.

## Fora de escopo

- Mudar `/login`.
- Criar endpoint, tabela ou campo nao previsto nos contratos vigentes.
- Redesenhar automacoes, conhecimento, analytics ou administracao nesta sprint.
- Trocar backend, Auth, RLS ou modelo multi-tenant.
- Usar pagina generica como entrega final.

## Direcao

**Tese visual:** workspace operacional calmo; navegacao curta; trabalho domina viewport; contexto fica em inspector; um accent teal.  
**Tese de conteudo:** usuario ve estado, responsavel, prazo, risco e proxima acao; nunca documentacao tecnica.  
**Tese de interacao:** drawers preservam contexto; Realtime atualiza sem interromper; toda mutacao tem pending, sucesso, conflito e retry seguro.

## Invariantes

- T-code, endpoint, fixture, Sprint, “estados previstos”, OpenAPI e handoff proibidos nas 14 rotas do escopo.
- `ScreenExperience` generico proibido nas 14 rotas do escopo.
- Tenant deriva da sessao/cookie confiavel.
- Modo real usa BFF/API; MSW proibido.
- Acao principal sempre produz efeito persistido observavel.
- Estado vazio sempre oferece acao valida.
- WCAG AA; teclado; zero Axe critical/serious.
- Desktop 1366x768 e mobile 390x844 sem overflow.

## Personas e cenarios de aceite

### Cenario A - Operador resolve prioridade

Atlas Owner abre Home, identifica tarefa em risco, abre contexto, conversa na sala, transforma mensagem em tarefa e move tarefa de `new` para `triaged`.

**Resultado binario:** tarefa persiste com `roomId` e `sourceMessageId`; timeline e inbox mostram `triaged` após reload.

### Cenario B - Gestor decide risco

Atlas Manager abre notificacao de aprovacao, revisa solicitante/evidencias e registra decisao permitida.

**Resultado binario:** decisao persiste; tarefa sai de espera; historico de decisao retornado pelo contrato mostra ator e timestamp; autoaprovacao proibida retorna 403/estado bloqueado.

### Cenario C - Comercial cria proxima acao

Atlas Owner localiza lead, move oportunidade no pipeline e cria follow-up vinculado.

**Resultado binario:** etapa e follow-up persistem após reload; timeline do lead registra mudanca.

## DAG unico

```text
S4-00 Contratos e mapa de rotas
  -> S4-01 Shell
    -> S4-02 Home, busca e notificacoes
    -> S4-03 Conversas
      -> S4-04 Tarefas
        -> S4-05 Aprovacoes
    -> S4-06 Comercial
S4-02 + S4-03 + S4-04 + S4-05 + S4-06
  -> S4-07 QA e cutover
```

## Stories

### S4-00 - Gate de contratos e mapa das 56 rotas

**Dias:** 1  
**Estimativa/owner:** 2 pessoa-dias; Lanes A+B (1 dia) + Backend reviewer  
**Dominio:** Produto/Frontend/Backend  
**Output:** `docs/frontend-route-migration.md` e matriz rota -> API -> estados -> owner.  
**Nao fazer:** inventar contrato para liberar UI.

- [x] Todas 56 rotas classificadas: `productize_s4`, `productize_later`, `redirect`, `catalog_only` ou `remove`.
- [x] Deep link destino definido para todo `redirect/remove`.
- [x] Cada rota S4 possui GET/mutacoes, payload, erros e permissao confirmados no OpenAPI.
- [x] `roomId`, `sourceMessageId`, `new -> triaged`, expected-version/409, decisao/historico e bloqueio de autoaprovacao existem no contrato e teste de integracao; ausencia marca Sprint 4 `BLOCKED` e exige replanejamento.
- [ ] Antes de qualquer mudanca S4, Produto aprova screenshots desktop/mobile do login e registra commit/hash imutavel em `docs/baselines/login/manifest.json`; threshold posterior <= 0,5%.

### S4-01 - Shell operacional

**Dias:** 2-3  
**Estimativa/owner:** 4 pessoa-dias; Lanes A+B (2 dias)  
**Depende de:** S4-00  
**Output:** navegacao, topbar, tenant, command palette, notificacoes, perfil e inspector.  
**Nao fazer:** listar 56 rotas na sidebar.

- [x] Sidebar tem sete grupos ou menos.
- [x] Somente rotas S4 aparecem primariamente; demais ficam em “Mais” sem prefetch.
- [x] Troca de tenant atualiza contexto e invalida dados anteriores.
- [x] Sessao expirada redireciona `/login` sem loop.
- [x] Permission denied mostra recurso negado e CTA `Voltar ao inicio` para `/operacao/home`.
- [x] Tenant vazio mostra CTA `Criar organizacao` para `/acesso/onboarding`.
- [x] Busca seleciona ID retornado pela API e abre rota de detalhe desse ID; notificacao abre entidade ligada pelo ID da API.

### S4-02 - Home orientada a decisao

**Dias:** 4-6  
**Estimativa/owner:** 3 pessoa-dias; Lane A  
**Depende de:** S4-01  
**Output:** prioridades, minhas tarefas, aprovacoes, falhas/SLA, custo e atividade.  
**Nao fazer:** mosaico de cards decorativos.

- [x] Indicadores usam resposta API; zero valor fixture no modo real.
- [x] Cada indicador abre lista filtrada correspondente.
- [x] Prioridade exibe owner, prazo, risco e proxima acao.
- [ ] Cenario A inicia pela Home sem URL digitada.

### S4-03 - Conversas como superficie principal

**Dias:** 4-7  
**Estimativa/owner:** 4 pessoa-dias; Lane B  
**Depende de:** S4-01  
**Output:** salas, timeline, composer e inspector.  
**Nao fazer:** mostrar contrato, estado QA ou metrica sem acao.

- [x] Sala mostra mensagens reais, autor humano/agente/sistema, horario e status.
- [x] Envio idempotente persiste e reconcilia Realtime sem duplicar.
- [x] Composer suporta mencao, anexo e selecao de agente somente se contrato vigente suportar.
- [x] Inspector mostra membros, arquivos e tarefas da sala.
- [x] Offline preserva rascunho; online reconcilia sem remount destrutivo.

### S4-04 - Tarefas e execucao

**Dias:** 8-11  
**Estimativa/owner:** 4 pessoa-dias; Lane B  
**Depende de:** S4-03  
**Output:** inbox, criacao e detalhe operacional.  
**Nao fazer:** transicao otimista sem versao esperada.

- [x] Mensagem cria tarefa com contexto permitido pelo contrato.
- [x] Inbox filtra por estado, owner, risco e SLA.
- [ ] Detalhe mostra objetivo, contexto, dependencias, timeline, artefatos e custo disponíveis.
- [x] Transicao persiste; conflito 409 preserva motivo e oferece recarregar.
- [x] Cenario A termina após reload com estado `triaged`.

### S4-05 - Aprovacoes contextuais

**Dias:** 12-13  
**Estimativa/owner:** 2 pessoa-dias; Lane B  
**Depende de:** S4-04  
**Output:** inbox e detalhe de aprovacao.  
**Nao fazer:** decisao sem evidencias ou segregacao.

- [x] Inbox separa pendentes, vencidas e decididas.
- [x] Detalhe mostra solicitante, risco, evidencias e impacto.
- [x] Decisao valida persiste e atualiza tarefa.
- [x] Autoaprovacao bloqueada possui teste UI/API.
- [ ] Cenario B passa desktop/mobile.

### S4-06 - Lead e pipeline operacional

**Dias:** 7-9  
**Estimativa/owner:** 3 pessoa-dias; Lane A  
**Depende de:** S4-01 e S4-00  
**Output:** lista de leads, detalhe e pipeline.  
**Nao fazer:** CRM generico, sync falso ou numero fixture.

- [x] Lead mostra origem, score, owner, timeline e proxima acao previstos no contrato.
- [x] Mudanca de etapa persiste e aparece após reload.
- [x] Follow-up vinculado persiste e aparece na timeline.
- [x] Provider indisponivel preserva formulario e mostra CTA `Tentar novamente`; retry idempotente nao duplica follow-up.
- [ ] Cenario C passa desktop/mobile.

### S4-07 - QA, corte e limpeza

**Dias:** 14-15  
**Estimativa/owner:** 2 pessoa-dias de correcao + QA/revisao independente  
**Depende de:** S4-02..S4-06  
**Output:** produto aprovado em staging e codigo generico removido do escopo.  
**Nao fazer:** marcar Done por componente existir.

- [x] Lint, typecheck, unit, contracts e build PASS.
- [ ] Cenarios A/B/C E2E reais desktop/mobile PASS sem retry e sem MSW.
- [ ] Tenant switch, session expiry, permission denied, tenant vazio, busca e notificacao E2E PASS.
- [ ] Axe zero critical/serious nas 14 rotas.
- [x] Fixture guard prova zero fixture nas 14 rotas em modo real.
- [ ] Scan de DOM/copy visivel prova zero T-code, endpoint e copy QA nas 14 rotas; URLs de rede e codigo interno ficam fora do scan.
- [ ] Login visual diff <= 0,5% desktop/mobile.
- [ ] Performance em staging, Chromium desktop, 3 runs/mediana: LCP <= 2,5s; INP <= 200ms; JS inicial <= 300KB gzip nas rotas Home/Sala/Tarefa.
- [x] Revisao independente PASS sem P0/P1/P2.

## Roadmap seguinte

- **Sprint 5:** agentes, skills, modelos, prompts e workflows.
- **Sprint 6:** conhecimento, memoria, RAG, campanhas e conteudo.
- **Sprint 7:** analytics, custos, administracao, integracoes e auditoria; productizacao das rotas restantes.

## Gate final

Sprint 4 termina somente quando:

- [ ] Cenarios A/B/C passam integralmente.
- [ ] Usuario nao encontra metadado tecnico nas 14 rotas.
- [ ] Login permanece dentro do baseline.
- [ ] Rotas restantes possuem destino explicito, nao somem silenciosamente.
- [ ] S4-07 inteiro passa.
