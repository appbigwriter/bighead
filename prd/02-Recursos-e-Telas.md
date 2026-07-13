# Recursos e telas - BigHead V3

**Status:** baseline detalhada para revisao  
**Fonte:** `ConceitoGeralv3.md` e `01-PRD-BigHead.md`  
**Cobertura:** 15 modulos, 56 telas/jornadas

## 1. Regras transversais de UX

Toda tela deve implementar: carregamento com skeleton; estado vazio com proxima acao; erro recuperavel com `trace_id`; offline; acesso negado sem vazar existencia do recurso; item removido; sucesso; responsividade; teclado e leitor de tela. Acoes irreversiveis, financeiras, publicas ou de alto risco exigem resumo de impacto, confirmacao e auditoria. Saidas de IA exibem agente, modelo, fontes, confianca, custo e status de aprovacao quando aplicavel.

## 2. Navegacao principal

| Area | Recursos |
|---|---|
| Acesso | autenticacao, convite, onboarding, organizacoes |
| Operacao | inicio, busca, salas, mensagens, tarefas, execucoes |
| Governanca | aprovacoes, Sentinel QA, portal externo, auditoria |
| Automacao | agentes, modelos, prompts, skills, workflows, playbooks |
| Conhecimento | documentos, ingestao, memoria, busca semantica |
| Comercial | contas, contatos, leads, pipeline, campanhas, conteudo |
| Aprendizado | experimentos, analytics, custos, qualidade |
| Administracao | membros, papeis, politicas, integracoes, privacidade |

## 3. Acesso e identidade

### T01 - Login

**Objetivo:** autenticar por email/senha, magic link ou provedor autorizado.  
**Componentes:** formulario, SSO, recuperar acesso, termos e privacidade.  
**Regras:** resposta nao revela se email existe; rate limit; sessao redireciona para organizacao valida.  
**Aceite:** usuario autenticado sem membership acessa onboarding; usuario suspenso nao acessa dados.

### T02 - Recuperacao e redefinicao

Solicita link, valida token e redefine credencial. Trata token expirado, usado e senha fraca. Todas as sessoes podem ser revogadas apos redefinicao.

### T03 - Aceite de convite

Exibe organizacao, remetente, papel, email e validade. Permite aceitar ou recusar. Token expirado/revogado/usado nao cria membership. Aceite e idempotente.

### T04 - Onboarding

Wizard para perfil, organizacao, segmento, timezone, objetivos, politica inicial e convite da equipe. Salva progresso. Conclusao cria owner e configuracao default atomicamente.

### T05 - Seletor de organizacao

Lista memberships ativas e troca tenant. A troca encerra subscriptions, invalida caches e limpa estado local do tenant anterior.

## 4. Shell e produtividade

### T06 - Home operacional

Cards de tarefas, SLA, aprovacoes, falhas, custo e resultados. Filtros por periodo, equipe, projeto e cliente. Cada indicador permite drill-down para os registros que o compoem.

### T07 - Busca global e command palette

Busca salas, mensagens, tarefas, leads, artefatos e conhecimento; atalhos criam tarefa, sala ou playbook. Resultados e contagens respeitam RLS e escopo.

### T08 - Notificacoes

Mencoes, atribuicoes, aprovacoes, SLA, falhas e conclusoes. Marcar lida, agrupar e abrir contexto. Preferencias por evento e canal.

### T09 - Perfil e sessoes

Nome, avatar, idioma, timezone, acessibilidade e sessoes ativas. Permite encerrar sessao/dispositivo e alterar preferencias.

## 5. Salas e mensagens

### T10 - Lista de salas

Favoritas, recentes, nao lidas, privadas e arquivadas. Criar sala define nome, finalidade, visibilidade e membros. Exibe ultima atividade, tarefas abertas e nao lidas.

### T11 - Sala conversacional

Timeline virtualizada; composer de texto, audio e arquivos; mencoes; threads; reacoes; edicao auditada; transformar mensagem em tarefa. Painel lateral mostra contexto, membros, anexos e tarefas. Falha de envio oferece retry idempotente.

### T12 - Informacoes e membros da sala

Edita nome, descricao, privacidade e membros conforme papel. Impede remover o ultimo administrador de uma sala privada quando isso a tornaria inacessivel.

### T13 - Arquivos da sala

Lista/preview com autor, versao, tarefa, tipo e classificacao. Downloads usam URL assinada. Arquivo em quarentena nao pode ser aberto.

## 6. Tarefas e execucoes

### T14 - Inbox de tarefas

Tabela e kanban por estado, prioridade, agente, responsavel, risco, SLA, cliente e workflow. Views salvas, paginacao por cursor e acoes em lote autorizadas.

### T15 - Criacao de tarefa

Objetivo, contexto, prioridade, prazo, SLA, responsavel, agente/workflow, risco, dependencias e anexos. Sugestao de roteamento inclui justificativa. Dependencia circular e recusada.

### T16 - Detalhe da tarefa

Cabecalho com estado, SLA, owner, agente, risco e custo. Abas: resumo, timeline, plano, artefatos, aprovacoes, execucoes, custos e auditoria. Transicoes exibem apenas destinos validos e pedem motivo quando obrigatorio.

### T17 - Monitor de execucao

Passos, tentativas, heartbeat, entrada/saida resumida, tokens, latencia, custo e erro. Permite cancelar ou repetir passo elegivel. Payload sensivel e mascarado.

### T18 - Fila de falhas

Agrupa por modelo, skill, permissao, dados, timeout e integracao. Exibe impacto, recorrencia e runbook. Retry cria nova tentativa, sem apagar historico.

### T19 - Calendario e SLA

Visao por data, responsavel e workflow; destaca vencidas e em risco. Reagendamento exige permissao e registra justificativa.

## 7. Aprovacoes e qualidade

### T20 - Inbox de aprovacoes

Fila por prazo, risco, cliente, solicitante e tipo. Preview e filtros. Segregacao impede autoaprovacao quando exigida.

### T21 - Detalhe da aprovacao

Compara versoes; mostra artefato, contexto, checklist, Sentinel, comentarios e impacto. Aprovar, rejeitar ou pedir alteracao. Decisao e imutavel; nova rodada cria nova solicitacao.

### T22 - Scorecards Sentinel QA

Cadastro versionado de criterios, pesos, limiar e aplicabilidade. Resultado mostra evidencia por criterio, score e bloqueios. Override humano exige justificativa.

### T23 - Politicas de aprovacao

Regras por risco, skill, canal, valor e tipo de acao; cadeia de aprovadores, quorum, segregacao e expiracao. Simulador mostra a rota resultante antes da publicacao.

### T24 - Portal externo

Pagina isolada por token opaco para visualizar, comentar e decidir. Trata expiracao, revogacao e limite de uso. Nao revela navegacao, IDs correlacionaveis ou dados internos.

## 8. Agentes, modelos e skills

### T25 - Catalogo de agentes

Status, owner, dominio, confianca, custo, sucesso e versao. Filtros, duplicacao e criacao assistida.

### T26 - Configuracao do agente

Abas perfil, prompt, modelo, skills, politica, testes, versoes e metricas. Test bench nao publica. Publicacao cria versao imutavel; rollback afeta somente novas execucoes.

### T27 - Catalogo de skills

Finalidade, integracao, risco, saude, latencia, falhas e consumidores. Desabilitar exibe impacto em agentes e workflows.

### T28 - Configuracao/teste da skill

Schemas JSON de entrada/saida, adaptador, referencia de credencial, timeout, retry, idempotencia, risco e aprovacao. Teste usa sandbox. Secret nunca reaparece apos gravacao.

### T29 - Provedores e modelos

Provider, modelos autorizados, capacidades, limites, regioes e preco com vigencia. Healthcheck, fallback e desativacao com analise de impacto.

### T30 - Biblioteca e versoes de prompts

Prompts por finalidade, variaveis, autor, status e diff. Publicacao congela conteudo; execucao referencia a versao exata.

## 9. Workflows e playbooks

### T31 - Lista de workflows

Draft/publicado/arquivado, owner, versao, sucesso, custo e dependencias. Permite duplicar e comparar.

### T32 - Editor visual de workflow

Canvas com agente, skill, condicao, aprovacao, espera e fim; painel de propriedades; validacao de schemas, nos inacessiveis e ciclos indevidos; simulacao. Publicar cria snapshot imutavel.

### T33 - Historico de versoes

Diff do grafo, prompts, politicas e schemas. Lista execucoes por versao. Rollback seleciona uma versao para futuras execucoes.

### T34 - Biblioteca de playbooks

Templates por objetivo, dominio e risco. Detalhe informa entradas, entregas, custo estimado e aprovacoes. Iniciar instancia workflow e tarefa.

## 10. Conhecimento e memoria

### T35 - Biblioteca de conhecimento

Pastas/taxonomia, documentos, fonte, confidencialidade, validade, owner e status de ingestao. Upload, URL ou texto. Arquivar e solicitar revisao.

### T36 - Documento e ingestao

Preview, metadados, versoes, chunks, erros e usos. Reprocessar cria nova versao. Conteudo contestado deixa de ser recuperado.

### T37 - Memoria operacional

Itens por tarefa, sala, conta e organizacao; fato, inferencia ou decisao; fonte, confianca, validade e aprovacao. Corrigir, contestar, aprovar e expirar com auditoria.

### T38 - Busca semantica/debug RAG

Consulta com filtros e resultados por similaridade; trecho, fonte, metadata e motivo. Debug restrito mostra score e filtros. O tenant sempre e filtro obrigatorio no servidor e no SQL.

## 11. Comercial e conteudo

### T39 - Contas e contatos

Lista de empresas e pessoas, owner, origem, segmento, dados de contato, consentimento e relacionamentos. Importacao valida duplicatas e origem.

### T40 - Leads

Score ICP, estagio, owner, fonte, sinais, proxima acao e SLA. Importar, atribuir, qualificar e iniciar playbook.

### T41 - Detalhe do lead

Resumo, conta/contatos, timeline, sinais, tarefas, campanhas, oportunidades e recomendacao explicada. Alteracoes de score preservam fatores e versao.

### T42 - Pipeline e oportunidades

Kanban e forecast. Mover estagio valida campos obrigatorios. Ganho/perda registra valor, data e motivo.

### T43 - Campanhas

Objetivo, audiencia, canais, budget, ativos, tarefas, status e metricas. Lancamento valida aprovacoes, datas e integracoes.

### T44 - Estudio de conteudo

Briefing, editor rico, variantes, SEO/brand score, comentarios, artefatos e canais. Estados: draft, review, approved, scheduled, published, archived.

### T45 - Calendario editorial/publicacoes

Calendario por canal e campanha, preview e status. Reagendar/cancelar. Falha de publicacao preserva payload e abre evento operacional.

## 12. Experimentos e analytics

### T46 - Lista de experimentos

Status, hipotese, metrica, janela e resultado. Filtros por campanha/canal. Nao apresenta vencedor sem criterio minimo definido.

### T47 - Configuracao e resultado do experimento

Variantes, audiencia, alocacao, metrica primaria e criterio de parada. Apos inicio, configuracao central fica imutavel. Resultado mostra amostra, intervalo, limitacoes e decisao.

### T48 - Dashboard executivo

Receita influenciada, leads, conversao, custo de IA, tempo economizado e qualidade. Todo indicador declara periodo, fonte e modelo de atribuicao.

### T49 - Operacoes e SLA

Volume, throughput, aging, gargalos, retrabalho, escalacoes e falhas por workflow/equipe. Drill-down abre os registros componentes.

### T50 - Performance de agentes/skills

Sucesso, score, latencia, custo, retries e falhas por versao. Comparacoes nao misturam versoes silenciosamente.

### T51 - Custos, budgets e quotas

Custo por tenant, projeto, tarefa, agente, modelo e provider; budget e alertas. Precos preservam vigencia historica.

### T52 - Funil e atribuicao

Campanha/conteudo -> lead -> oportunidade -> receita. Seletor de modelo e janela de atribuicao. Eventos sem ligacao aparecem como nao atribuidos.

## 13. Administracao e compliance

### T53 - Organizacao e branding

Nome, slug, timezone, locale, identidade do portal e limites. Alteracao de slug e exclusao exigem confirmacao reforcada.

### T54 - Membros, convites e papeis

Memberships, status, equipes e ultimo acesso. Convidar, suspender, trocar papel e remover. Impede remover/rebaixar o ultimo owner.

### T55 - Integracoes e webhooks

Conectores, escopos, saude, ultima sincronizacao e logs. Webhooks mostram eventos, retries e endpoint; secret aparece somente na criacao/rotacao.

### T56 - Privacidade, retencao e auditoria

Politicas por classe, legal hold, exportacao, pedidos LGPD e exclusao. Auditoria append-only por ator, acao, recurso, IP, risco e trace; dados sensiveis redigidos.

## 14. Componentes reutilizaveis obrigatorios

Breadcrumbs; filtros persistentes; views salvas; paginacao por cursor; timeline; diff; preview de artefato; badges de risco/custo/agente; citacoes; guard de permissao; confirmacao destrutiva; toast com `trace_id`; tabela acessivel; uploader com progresso; comentario contextual; seletor de organizacao; empty state; error boundary.

## 15. Matriz de papel por modulo

| Modulo | Owner/Admin | Manager | Member | Reviewer | Analyst | Guest |
|---|---|---|---|---|---|---|
| Salas/tarefas | administrar | gerir equipe | operar escopo | consultar contexto | leitura agregada | nao |
| Aprovacoes | configurar/decidir | decidir | solicitar | decidir | leitura agregada | token limitado |
| Agentes/skills | publicar | testar/usar | usar | consultar | metricas | nao |
| Workflows | publicar | criar/testar | executar | consultar | metricas | nao |
| Conhecimento | governar | editar | consultar/contribuir | revisar | consultar | nao |
| Leads/conteudo | governar | gerir | operar | aprovar | analisar | aprovacao limitada |
| Auditoria/politicas | total | leitura restrita | proprio escopo | proprio escopo | agregado | nao |

## 16. Definition of ready por tela

Uma tela somente entra em implementacao quando possuir wireframe responsivo, contrato de dados, papel/capacidade, estados transversais, eventos de analytics, auditoria, criterio de aceite binario e casos de borda. `DESIGN_STANDARDS.md` deve ser criado e aprovado antes da fase visual definitiva.
