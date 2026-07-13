# PRD - BigHead V3

**Status:** Draft para revisao  
**Fonte:** `ConceitoGeralv3.md`  
**Versao:** 0.1  
**Owner proposto:** Produto/Operacoes

## 1. Premissas a validar

Os arquivos canonicos `fbr-arquitetura.md`, `securitycoderules.md` e `DESIGN_STANDARDS.md` nao estavam presentes. Esta versao adota como baseline: Next.js App Router e TypeScript; FastAPI e workers Python; Redis; Supabase Auth, PostgreSQL, Storage e Realtime; `pgvector`; tenancy por organizacao; RBAC e ABAC; LGPD; aprovacao humana para acoes externas, financeiras, destrutivas ou de alto risco.

## 2. Definicao do produto

**Sistema:** BigHead  
**Proposito:** transformar conversas empresariais em trabalho executavel, governado, auditavel e mensuravel.  
**Tipo:** Hub central  
**Unidade operacional:** tarefa  
**Diferencial:** conectar solicitacao, agentes, skills, aprovacao, artefatos, custo e resultado em uma unica trilha.

## 3. Problema e oportunidade

Equipes distribuem contexto entre chats, documentos, CRMs e ferramentas de IA sem ownership, estado ou medida de resultado. Isso gera retrabalho, perda de contexto, automacoes inseguras e dificuldade para provar ROI. O BigHead converte mensagens em tarefas com estado explicito, seleciona agentes e workflows, aplica politicas de risco, registra evidencias e liga entregas a leads, receita e aprendizado operacional.

## 4. Objetivos e nao objetivos

### Objetivos

- Reduzir o tempo entre solicitacao e primeira entrega util.
- Aumentar aprovacoes na primeira rodada e reduzir retrabalho.
- Permitir automacao progressiva conforme confianca de agente e skill.
- Garantir isolamento, rastreabilidade e aprovacao proporcional ao risco.
- Medir custo, qualidade, conversao e receita influenciada por fluxo.
- Transformar entregas aprovadas em memoria, templates e playbooks reutilizaveis.

### Nao objetivos iniciais

- Substituir ERP, CRM ou gerenciador de arquivos corporativo.
- Permitir execucao autonoma irrestrita.
- Treinar modelos fundacionais.
- Oferecer marketplace publico de skills no MVP.
- Ser sistema contabil, financeiro ou juridico de registro.

## 5. Personas e papeis

| Persona | Necessidade | Papel base |
|---|---|---|
| Owner | governanca, custo e configuracao global | owner |
| Administrador | usuarios, integracoes, agentes e politicas | admin |
| Gestor | fila, SLA, aprovacoes e desempenho | manager |
| Operador | conversar, criar e executar tarefas | member |
| Revisor | avaliar artefatos e aprovar etapas | reviewer |
| Analista | consultar funil, experimentos e ROI | analyst |
| Cliente externo | aprovar ou comentar entregas por link | guest |
| Agente | executar apenas capacidades declaradas | service principal |

## 6. Escopo funcional

### RF-01 Identidade e organizacoes

Autenticacao por Supabase Auth, onboarding, perfil, organizacoes, convites e membership. Cada registro operacional pertence a uma organizacao. Owner e admin administram membros; nenhuma autorizacao usa `user_metadata` editavel.

**Aceite:** usuario de uma organizacao nao consegue listar, ler ou alterar dados de outra, inclusive via Data API.

### RF-02 Salas, mensagens e anexos

Salas publicas da organizacao, privadas ou vinculadas a projeto/cliente. Mensagens suportam texto, mencoes, anexos, respostas, edicao auditada e eventos em tempo real. Uma mensagem pode originar uma tarefa.

**Aceite:** participantes autorizados recebem novas mensagens; anexos privados usam caminho por organizacao e URL assinada.

### RF-03 Tarefas e state machine

Estados: `new`, `triaged`, `in_progress`, `waiting_tool`, `waiting_human`, `ready_for_review`, `approved`, `failed`, `done`, `canceled`. A tarefa guarda objetivo, prioridade, SLA, responsavel, agente, custo, risco, artefatos, dependencias e historico de transicoes.

**Aceite:** transicao invalida e recusada; toda mudanca registra ator, origem, motivo e timestamp; apenas um lease de execucao ativo por tarefa.

### RF-04 Orquestracao

Classificar intencao, dominio, risco, urgencia e custo; selecionar workflow/agente/modelo; explicar o roteamento; criar plano de execucao e aplicar limite de tentativas. Idempotencia por evento e chave de execucao.

### RF-05 Agentes, modelos, prompts e skills

Cadastro versionado com status, owner, modelo, prompt, limites, score de confianca e skills permitidas. Skills declaram schema de entrada/saida, risco, timeout, retries e necessidade de aprovacao. Segredos ficam em cofre do ambiente, nunca no banco em texto puro.

### RF-06 Workflows e playbooks

Editor versionado de workflows com passos de agente, skill, decisao, espera, revisao e aprovacao. Publicacao cria versao imutavel; execucoes antigas continuam ligadas a versao original. Playbooks instanciam workflows com configuracoes e templates.

### RF-07 Execucao, filas e artefatos

Workers executam passos assincronos, renovam lease, registram heartbeat, uso de tokens, latencia, custo, erros e artefatos. Retries usam backoff e dead-letter. Cancelamento deve ser cooperativo.

### RF-08 Aprovacoes e Sentinel QA

Politicas determinam revisao automatica e humana por risco. O Sentinel aplica scorecards; aprovadores podem aprovar, rejeitar ou solicitar alteracao. Acoes de alto risco permanecem bloqueadas ate aprovacao valida.

### RF-09 Portal externo

Link de acesso com token opaco, expiracao, escopo e limite de uso para visualizar, comentar e decidir sobre uma entrega. O token nao concede acesso ao workspace.

### RF-10 Memoria e conhecimento

Memoria curta, de trabalho e corporativa. Itens distinguem fato, inferencia e decisao; possuem fonte, validade, confidencialidade e status de revisao. Ingestao divide documentos, gera embeddings e permite busca semantica filtrada por tenant.

### RF-11 Lead intelligence e funil

Contas, contatos, leads, sinais, score ICP, estagios e proximas acoes. Importacao e enriquecimento devem registrar fonte e consentimento/base legal quando aplicavel.

### RF-12 Conteudo, campanhas e distribuicao

Briefings, ativos, variantes, canais, publicacoes e metricas. Entregas externas exigem aprovacao conforme politica. Eventos de desempenho ligam conteudo a leads e oportunidades.

### RF-13 Experimentos

Experimentos com hipotese, variantes, metrica primaria, janela, alocacao e resultado. Uma variante nao pode ser alterada depois do inicio; conclusoes preservam amostra e criterio.

### RF-14 Analytics de ciclo fechado

Dashboards de operacao, agentes, skills, custos, qualidade e funil. Eventos de atribuicao conectam campanha, conteudo, lead, oportunidade e receita, com modelo de atribuicao declarado.

### RF-15 Notificacoes e auditoria

Notificacoes in-app e conectores futuros; preferencias por usuario. Auditoria append-only para mudancas de seguranca, publicacao, aprovacao, execucao e acesso externo.

## 7. Backend

### 7.1 Componentes

- **API FastAPI:** contratos HTTP, autenticacao, autorizacao, comandos e consultas.
- **Orchestrator:** classificacao, roteamento, politica de risco e criacao de execucoes.
- **Worker:** passos assincronos, LLMs, skills, retries e heartbeats.
- **Scheduler:** SLA, expiracoes, tarefas recorrentes e consolidacao de metricas.
- **Event bus Redis:** fila, pub/sub, locks curtos e invalidacao; PostgreSQL permanece fonte de verdade.
- **Supabase:** Auth, dados transacionais, RLS, Storage e Realtime.
- **Provider gateway:** adaptadores de LLM e ferramentas com timeout, circuit breaker e telemetria comum.

### 7.2 Modulos de dominio

`identity`, `organizations`, `collaboration`, `tasks`, `orchestration`, `agents`, `skills`, `workflows`, `approvals`, `artifacts`, `memory`, `crm`, `content`, `experiments`, `analytics`, `notifications`, `audit`.

### 7.3 Contratos principais

| Metodo/Evento | Contrato | Regra |
|---|---|---|
| POST `/v1/tasks` | cria tarefa | `Idempotency-Key` obrigatoria para integracoes |
| POST `/v1/tasks/{id}/transition` | muda estado | valida state machine e permissao |
| POST `/v1/tasks/{id}/execute` | inicia execucao | cria lease e evento |
| POST `/v1/approvals/{id}/decision` | registra decisao | decisao imutavel; exige escopo |
| POST `/v1/knowledge/ingest` | agenda ingestao | arquivo e tenant validados |
| POST `/v1/search/semantic` | busca memoria | filtros de tenant obrigatorios |
| `task.created` | inicia triagem | idempotente por `event_id` |
| `run.step.requested` | aciona worker | retry com backoff |
| `approval.required` | bloqueia fluxo | nenhuma acao protegida antes da decisao |
| `artifact.published` | registra saida | emite atribuicao e auditoria |

Erros usam `application/problem+json`, `trace_id`, codigo estavel e mensagem segura. APIs recebem JWT do Supabase; chamadas internas usam identidade de servico e assinatura/segredo rotacionavel. Rate limits por usuario, organizacao e integracao.

### 7.4 Consistencia e concorrencia

- Transicoes usam transacao e lock otimista por `version`.
- Execucoes usam lease com `locked_by` e `locked_until`.
- Outbox transacional evita perda entre commit e publicacao de evento.
- Webhooks possuem assinatura, replay protection e inbox idempotente.
- Custos sao append-only e agregados de forma derivada.

### 7.5 Seguranca

RLS e grants explicitos; service role somente no backend; secrets em secret manager; criptografia em transito e repouso; sanitizacao de anexos; protecao contra prompt injection em conteudo recuperado; allowlist de ferramentas; logs sem prompts sensiveis por padrao; retencao e exclusao por politica; backup e teste de restauracao.

## 8. Frontend

### 8.1 Arquitetura

Next.js App Router, TypeScript e componentes acessiveis. Server Components para leitura inicial; Client Components apenas para interacao e realtime. Supabase SSR gerencia sessao; mutacoes sensiveis passam por backend. Cache deve incluir tenant na chave e nunca compartilhar dados entre organizacoes.

### 8.2 Shell

Navegacao global por organizacao com busca/comando, notificacoes, ajuda e perfil. Modulos: Inicio, Salas, Tarefas, Aprovacoes, Leads, Conteudo, Conhecimento, Playbooks, Analytics e Administracao.

### 8.3 UX obrigatoria

- Estados loading, vazio, erro, offline, sem permissao e parcial em todas as telas.
- Atualizacao otimista apenas em operacoes reversiveis.
- Confirmacao e resumo de impacto para acoes criticas.
- Indicacao de agente, custo, risco, fonte e confianca em saidas de IA.
- Acessibilidade WCAG 2.2 AA, teclado, foco visivel e leitores de tela.
- Layout responsivo; mobile prioriza inbox, chat, tarefas e aprovacoes.

## 9. Requisitos nao funcionais

| ID | Requisito | Meta inicial |
|---|---|---|
| RNF-01 | disponibilidade API | 99,5% mensal no MVP |
| RNF-02 | latencia de leitura | p95 < 500 ms sem chamada de IA |
| RNF-03 | feedback de comando | confirmacao < 1 s; processamento assincrono |
| RNF-04 | isolamento | zero acesso cross-tenant em testes RLS |
| RNF-05 | recuperacao | RPO <= 24 h; RTO <= 8 h no MVP |
| RNF-06 | auditoria | 100% das acoes criticas com ator e trace |
| RNF-07 | acessibilidade | WCAG 2.2 AA nas jornadas criticas |
| RNF-08 | observabilidade | logs, metricas e traces correlacionados |
| RNF-09 | retencao | configuravel por classe de dado |
| RNF-10 | portabilidade | exportacao de dados estruturados e artefatos |

## 10. KPIs

Tempo para primeira entrega util; tarefas concluidas sem retrabalho; aprovacao na primeira rodada; escalacao humana; falha e latencia por skill; custo por tarefa/agente/cliente; SLA; leads e oportunidades influenciados; conversao; receita atribuida; precisao do roteamento; memoria aceita versus contestada.

## 11. Fases

1. **Fundacao:** identidade, tenancy, salas, mensagens, tarefas, agentes, skills, execucao, logs e aprovacao.
2. **Qualidade:** Sentinel, scorecards, workflows versionados, memoria de trabalho e observabilidade.
3. **Comercial:** leads, conteudo, campanhas, portal externo e analytics de funil.
4. **Aprendizado:** RAG corporativo, experimentos, recomendacoes e automacao progressiva.

## 12. Gate para implementacao

- Validar stack e padroes ausentes.
- Aprovar matriz de papeis, risco e retencao.
- Definir provedores de LLM, CRM, publicacao e notificacao.
- Definir dimensao de embedding antes de aplicar a migration.
- Executar threat model, testes pgTAP/RLS e estimativa de custo.
- Converter este PRD em batches e tasks com done binario apos revisao.
