export type ScreenCode =
  | "T01"
  | "T02"
  | "T03"
  | "T04"
  | "T05"
  | "T06"
  | "T07"
  | "T08"
  | "T09"
  | "T10"
  | "T11"
  | "T12"
  | "T13"
  | "T14"
  | "T15"
  | "T16"
  | "T17"
  | "T18"
  | "T19"
  | "T20"
  | "T21"
  | "T22"
  | "T23"
  | "T24"
  | "T25"
  | "T26"
  | "T27"
  | "T28"
  | "T29"
  | "T30"
  | "T31"
  | "T32"
  | "T33"
  | "T34"
  | "T35"
  | "T36"
  | "T37"
  | "T38"
  | "T39"
  | "T40"
  | "T41"
  | "T42"
  | "T43"
  | "T44"
  | "T45"
  | "T46"
  | "T47"
  | "T48"
  | "T49"
  | "T50"
  | "T51"
  | "T52"
  | "T53"
  | "T54"
  | "T55"
  | "T56";

export type ScreenDefinition = {
  code: ScreenCode;
  title: string;
  slug: string[];
  area:
    | "Acesso"
    | "Operacao"
    | "Governanca"
    | "Automacao"
    | "Conhecimento"
    | "Comercial"
    | "Aprendizado"
    | "Administracao";
  module: string;
  summary: string;
  states: string[];
  endpoints: string[];
  metrics: { label: string; value: string; tone?: "risk" | "accent" | "neutral" }[];
  checklist: string[];
};

const definitions: ScreenDefinition[] = [
  {
    code: "T01",
    title: "Login",
    slug: ["acesso", "login"],
    area: "Acesso",
    module: "Identidade",
    summary: "Entrada por email, senha, magic link ou provedor com respostas anti-enumeracao.",
    states: ["default", "loading", "invalid_credentials", "magic_link_sent"],
    endpoints: ["POST /v1/auth/login"],
    metrics: [
      { label: "Tentativas bloqueadas", value: "3" },
      { label: "Provedores ativos", value: "2", tone: "accent" }
    ],
    checklist: ["Nao revela existencia do email", "Acesso por teclado", "Recuperacao acessivel"]
  },
  {
    code: "T02",
    title: "Recuperacao e redefinicao",
    slug: ["acesso", "recuperacao"],
    area: "Acesso",
    module: "Identidade",
    summary: "Fluxo de recuperar acesso, validar token e redefinir credenciais com revogacao de sessoes.",
    states: ["request_link", "token_expired", "success"],
    endpoints: ["POST /v1/auth/recovery", "POST /v1/auth/reset"],
    metrics: [
      { label: "Links ativos", value: "14" },
      { label: "Expiracao", value: "15 min", tone: "risk" }
    ],
    checklist: ["Token unico", "Senha forte", "Revoga sessoes abertas"]
  },
  {
    code: "T03",
    title: "Aceite de convite",
    slug: ["acesso", "convite"],
    area: "Acesso",
    module: "Organizacoes",
    summary: "Aceite ou recusa convites com validade, idempotencia e verificacao de email.",
    states: ["pending", "accepted", "expired", "revoked"],
    endpoints: ["GET /v1/invitations/{token}", "POST /v1/invitations/{token}/accept"],
    metrics: [
      { label: "Convites pendentes", value: "8" },
      { label: "Papeis ofertados", value: "5" }
    ],
    checklist: ["Confere email do convite", "Nao duplica membership", "Permite recusar"]
  },
  {
    code: "T04",
    title: "Onboarding",
    slug: ["acesso", "onboarding"],
    area: "Acesso",
    module: "Organizacoes",
    summary: "Wizard de perfil, organizacao, objetivos e politica inicial com progresso salvo.",
    states: ["step_profile", "step_org", "step_goals", "completed"],
    endpoints: ["POST /v1/onboarding"],
    metrics: [
      { label: "Passos", value: "4" },
      { label: "Conclusao media", value: "6 min", tone: "accent" }
    ],
    checklist: ["Salva progresso", "Retoma sessao expirada", "Cria owner atomico"]
  },
  {
    code: "T05",
    title: "Seletor de organizacao",
    slug: ["acesso", "organizacoes"],
    area: "Acesso",
    module: "Organizacoes",
    summary: "Troca de tenant com limpeza de cache, subscriptions e contexto visual anterior.",
    states: ["single_org", "multi_org", "org_removed"],
    endpoints: ["GET /v1/organizations", "POST /v1/context/switch"],
    metrics: [
      { label: "Memberships", value: "4" },
      { label: "Tenant atual", value: "Acme Growth", tone: "accent" }
    ],
    checklist: ["Invalida cache", "Fecha subscriptions", "Troca sem vazamento visual"]
  },
  {
    code: "T06",
    title: "Home operacional",
    slug: ["operacao", "home"],
    area: "Operacao",
    module: "Produtividade",
    summary: "Resumo de tarefas, SLA, aprovacoes, falhas, custos e resultados com drill-down.",
    states: ["full", "partial", "empty", "permission_denied"],
    endpoints: ["GET /v1/analytics/summary", "GET /v1/dashboard/home"],
    metrics: [
      { label: "SLA em risco", value: "6", tone: "risk" },
      { label: "Aprovacoes abertas", value: "7", tone: "accent" },
      { label: "Custo hoje", value: "R$ 184" }
    ],
    checklist: ["Drill-down preserva filtros", "Mostra freshness", "Agrupa falhas por impacto"]
  },
  {
    code: "T07",
    title: "Busca global e command palette",
    slug: ["operacao", "busca-global"],
    area: "Operacao",
    module: "Produtividade",
    summary: "Busca unificada por salas, tarefas, leads, conhecimento e atalhos operacionais.",
    states: ["idle", "results", "empty", "resource_removed"],
    endpoints: ["POST /v1/search/global"],
    metrics: [
      { label: "Atalhos", value: "12" },
      { label: "Escopo", value: "Tenant atual", tone: "accent" }
    ],
    checklist: ["Abre por teclado", "Nao mostra recurso sem acesso", "Agrupa por tipo"]
  },
  {
    code: "T08",
    title: "Notificacoes",
    slug: ["operacao", "notificacoes"],
    area: "Operacao",
    module: "Produtividade",
    summary: "Central de mencoes, atribuicoes, aprovacoes, SLA e falhas com preferencias por evento.",
    states: ["grouped", "unread", "empty", "removed_target"],
    endpoints: ["GET /v1/notifications", "PATCH /v1/notifications/preferences"],
    metrics: [
      { label: "Nao lidas", value: "11", tone: "risk" },
      { label: "Canais ativos", value: "3" }
    ],
    checklist: ["Agrupamento coerente", "Marca em lote", "Abre contexto relacionado"]
  },
  {
    code: "T09",
    title: "Perfil e sessoes",
    slug: ["operacao", "perfil"],
    area: "Operacao",
    module: "Produtividade",
    summary: "Preferencias pessoais, acessibilidade, timezone, idioma e gestao de sessoes ativas.",
    states: ["profile", "sessions", "save_success"],
    endpoints: ["GET /v1/profile", "PATCH /v1/preferences", "GET /v1/sessions"],
    metrics: [
      { label: "Sessoes ativas", value: "3" },
      { label: "Tema", value: "Aurora light", tone: "accent" }
    ],
    checklist: ["Persistencia sem flash", "Encerrar dispositivo", "Preferencias por tenant"]
  },
  {
    code: "T10",
    title: "Lista de salas",
    slug: ["colaboracao", "salas"],
    area: "Operacao",
    module: "Colaboracao",
    summary: "Inbox de salas com favoritas, recentes, privadas, arquivadas e contadores de nao lidas.",
    states: ["list", "favorited", "empty", "private_filtered"],
    endpoints: ["GET /v1/rooms", "POST /v1/rooms"],
    metrics: [
      { label: "Salas ativas", value: "18" },
      { label: "Nao lidas", value: "5", tone: "risk" }
    ],
    checklist: ["Filtro por visibilidade", "Favoritos persistem", "Nao expoe salas privadas"]
  },
  {
    code: "T11",
    title: "Sala conversacional",
    slug: ["colaboracao", "sala"],
    area: "Operacao",
    module: "Colaboracao",
    summary: "Timeline de mensagens humanas e de agentes, threads, mencoes, anexos e acao de virar tarefa.",
    states: ["realtime", "slow_loading", "upload_failed", "offline"],
    endpoints: ["GET /v1/rooms/{roomId}/messages", "POST /v1/messages", "POST /v1/messages/{id}/task"],
    metrics: [
      { label: "Mensagens hoje", value: "156" },
      { label: "Anexos", value: "24" },
      { label: "Custo IA", value: "R$ 42", tone: "accent" }
    ],
    checklist: ["ID temporario reconcilia", "Mostra fonte/custo do agente", "Recupera upload falho"]
  },
  {
    code: "T12",
    title: "Informacoes e membros da sala",
    slug: ["colaboracao", "membros"],
    area: "Operacao",
    module: "Colaboracao",
    summary: "Configuracao de privacidade, descricao e membros com regras para moderadores.",
    states: ["public", "private", "last_admin_guard"],
    endpoints: ["PATCH /v1/rooms/{roomId}", "GET /v1/rooms/{roomId}/members"],
    metrics: [
      { label: "Membros", value: "14" },
      { label: "Moderadores", value: "2", tone: "accent" }
    ],
    checklist: ["Impede ultimo moderador", "Mostra papeis", "Ajuste de privacidade auditado"]
  },
  {
    code: "T13",
    title: "Arquivos da sala",
    slug: ["colaboracao", "arquivos"],
    area: "Operacao",
    module: "Colaboracao",
    summary: "Gestao de anexos com preview, quarentena, metadados e URL assinada.",
    states: ["ready", "quarantine", "uploading", "expired_link"],
    endpoints: ["GET /v1/rooms/{roomId}/files", "POST /v1/uploads/sign"],
    metrics: [
      { label: "Arquivos", value: "63" },
      { label: "Quarentena", value: "2", tone: "risk" }
    ],
    checklist: ["Preview seguro", "Progresso/cancelamento", "Quarentena bloqueia abertura"]
  },
  {
    code: "T14",
    title: "Inbox de tarefas",
    slug: ["tarefas", "inbox"],
    area: "Operacao",
    module: "Tarefas",
    summary: "Tabela e kanban de tarefas com filtros, lotes, pagina por cursor e views salvas.",
    states: ["table", "kanban", "loading_more", "empty"],
    endpoints: ["GET /v1/tasks"],
    metrics: [
      { label: "Tarefas abertas", value: "24" },
      { label: "Em revisao", value: "4", tone: "accent" },
      { label: "Atrasadas", value: "3", tone: "risk" }
    ],
    checklist: ["Views persistem", "Lotes autorizados", "Cursor preservado no retorno"]
  },
  {
    code: "T15",
    title: "Criacao de tarefa",
    slug: ["tarefas", "criar"],
    area: "Operacao",
    module: "Tarefas",
    summary: "Formulario com objetivo, risco, agente, workflow, dependencias e SLA com roteamento explicado.",
    states: ["editing", "validation_error", "success"],
    endpoints: ["POST /v1/tasks", "POST /v1/tasks/route-preview"],
    metrics: [
      { label: "Templates", value: "9" },
      { label: "Risco medio", value: "Moderado", tone: "accent" }
    ],
    checklist: ["Motivo do roteamento", "Bloqueia dependencia circular", "Suporta anexos"]
  },
  {
    code: "T16",
    title: "Detalhe da tarefa",
    slug: ["tarefas", "detalhe"],
    area: "Operacao",
    module: "Tarefas",
    summary: "Visao completa da tarefa com resumo, timeline, artefatos, aprovacoes, execucoes e auditoria.",
    states: ["healthy", "waiting_human", "conflict_409", "done"],
    endpoints: ["GET /v1/tasks/{taskId}", "POST /v1/tasks/{taskId}/transition"],
    metrics: [
      { label: "Estado", value: "ready_for_review", tone: "accent" },
      { label: "SLA restante", value: "3h", tone: "risk" },
      { label: "Custo", value: "R$ 58" }
    ],
    checklist: ["So destinos validos", "Preserva texto em 409", "Timeline auditavel"]
  },
  {
    code: "T17",
    title: "Monitor de execucao",
    slug: ["tarefas", "execucao"],
    area: "Operacao",
    module: "Tarefas",
    summary: "Passos, tentativas, heartbeat, latencia, tokens, custo e logs mascarados por run.",
    states: ["running", "retryable", "failed", "canceled"],
    endpoints: ["GET /v1/runs", "POST /v1/runs/{runId}/retry", "POST /v1/runs/{runId}/cancel"],
    metrics: [
      { label: "Heartbeat", value: "22s" },
      { label: "Tentativas", value: "2", tone: "risk" },
      { label: "Tokens", value: "18k" }
    ],
    checklist: ["Mascara payload sensivel", "Cancela com confirmacao", "Retry cria nova tentativa"]
  },
  {
    code: "T18",
    title: "Fila de falhas",
    slug: ["tarefas", "falhas"],
    area: "Operacao",
    module: "Tarefas",
    summary: "Agrupamento de falhas por modelo, skill, permissao, timeout e integracao com impacto.",
    states: ["clustered", "retrying", "resolved"],
    endpoints: ["GET /v1/failures", "POST /v1/failures/{groupId}/retry"],
    metrics: [
      { label: "Grupos", value: "6", tone: "risk" },
      { label: "Impactadas", value: "14" }
    ],
    checklist: ["Mantem historico", "Prioriza por impacto", "Runbook visivel"]
  },
  {
    code: "T19",
    title: "Calendario e SLA",
    slug: ["tarefas", "sla"],
    area: "Operacao",
    module: "Tarefas",
    summary: "Calendario operacional por data, responsavel e workflow destacando vencidas e em risco.",
    states: ["calendar", "reschedule", "overdue"],
    endpoints: ["GET /v1/tasks/calendar", "POST /v1/tasks/{taskId}/reschedule"],
    metrics: [
      { label: "Hoje", value: "12" },
      { label: "Em risco", value: "5", tone: "risk" }
    ],
    checklist: ["Reagendamento com justificativa", "Filtro por owner", "Nao perde contexto da tarefa"]
  },
  {
    code: "T20",
    title: "Inbox de aprovacoes",
    slug: ["governanca", "aprovacoes"],
    area: "Governanca",
    module: "Aprovacoes",
    summary: "Fila de aprovacoes por prazo, risco, cliente e solicitante com preview rapido.",
    states: ["pending", "segregated", "empty"],
    endpoints: ["GET /v1/approvals"],
    metrics: [
      { label: "Pendentes", value: "7", tone: "risk" },
      { label: "Externas", value: "2" }
    ],
    checklist: ["Autoaprovacao bloqueada", "Preview rapido", "Ordena por risco e prazo"]
  },
  {
    code: "T21",
    title: "Detalhe da aprovacao",
    slug: ["governanca", "aprovacao-detalhe"],
    area: "Governanca",
    module: "Aprovacoes",
    summary: "Comparacao de versoes, contexto, checklist, comentarios e decisao imutavel.",
    states: ["approved", "rejected", "changes_requested", "concurrent_decision"],
    endpoints: ["GET /v1/approvals/{approvalId}", "POST /v1/approvals/{approvalId}/decision"],
    metrics: [
      { label: "Rodada", value: "2" },
      { label: "Risco", value: "Alto", tone: "risk" }
    ],
    checklist: ["Decisao imutavel", "Nova rodada apos changes", "Impacto visivel"]
  },
  {
    code: "T22",
    title: "Scorecards Sentinel QA",
    slug: ["governanca", "scorecards"],
    area: "Governanca",
    module: "Qualidade",
    summary: "Scorecards de qualidade e criterios por entrega, canal e politica de risco.",
    states: ["passing", "warning", "failing"],
    endpoints: ["GET /v1/approvals/{approvalId}/scorecard"],
    metrics: [
      { label: "Score medio", value: "84/100", tone: "accent" },
      { label: "Falhas criticas", value: "1", tone: "risk" }
    ],
    checklist: ["Explica criterios", "Relaciona politicas", "Mostra tendencia por rodada"]
  },
  {
    code: "T23",
    title: "Politicas de aprovacao",
    slug: ["governanca", "politicas"],
    area: "Governanca",
    module: "Qualidade",
    summary: "Configuracao de politicas com simulador por risco, tipo de acao e segregacao.",
    states: ["draft", "published", "simulating"],
    endpoints: ["GET /v1/policies/approvals", "PATCH /v1/policies/approvals"],
    metrics: [
      { label: "Politicas", value: "5" },
      { label: "Cobertura", value: "92%", tone: "accent" }
    ],
    checklist: ["Simula impacto", "Bloqueia lacunas", "Explica segregacao"]
  },
  {
    code: "T24",
    title: "Portal externo",
    slug: ["governanca", "portal-externo"],
    area: "Governanca",
    module: "Portal",
    summary: "Experiencia externa isolada para visualizar, comentar e decidir via token opaco.",
    states: ["valid", "expired", "revoked", "used"],
    endpoints: ["GET /v1/portal/items/{token}"],
    metrics: [
      { label: "Links ativos", value: "12" },
      { label: "Uso maximo", value: "3", tone: "risk" }
    ],
    checklist: ["Nao revela shell", "Branding dedicado", "Token opaco e escopado"]
  },
  {
    code: "T25",
    title: "Catalogo de agentes",
    slug: ["automacao", "agentes"],
    area: "Automacao",
    module: "Agentes",
    summary: "Catalogo versionado de agentes com owner, modelo, confianca e metricas.",
    states: ["active", "draft", "archived"],
    endpoints: ["GET /v1/agents"],
    metrics: [
      { label: "Ativos", value: "9" },
      { label: "Confianca media", value: "87%", tone: "accent" }
    ],
    checklist: ["Owner visivel", "Consumers rastreaveis", "Metricas por versao"]
  },
  {
    code: "T26",
    title: "Configuracao do agente",
    slug: ["automacao", "agente-config"],
    area: "Automacao",
    module: "Agentes",
    summary: "Edicao de prompt, limites, modelos permitidos, skills e score de confianca.",
    states: ["editing", "impact_analysis", "disabled"],
    endpoints: ["GET /v1/agents/{agentId}", "PATCH /v1/agents/{agentId}"],
    metrics: [
      { label: "Skills ligadas", value: "7" },
      { label: "Consumidores", value: "11", tone: "risk" }
    ],
    checklist: ["Mostra impacto", "Controla limites", "Versiona alteracoes"]
  },
  {
    code: "T27",
    title: "Catalogo de skills",
    slug: ["automacao", "skills"],
    area: "Automacao",
    module: "Skills",
    summary: "Lista de skills com schema, risco, timeout, retries e necessidade de aprovacao.",
    states: ["healthy", "degraded", "disabled"],
    endpoints: ["GET /v1/skills"],
    metrics: [
      { label: "Skills", value: "22" },
      { label: "Alto risco", value: "4", tone: "risk" }
    ],
    checklist: ["Schema visivel", "Risco textual", "Health por versao"]
  },
  {
    code: "T28",
    title: "Configuracao/teste da skill",
    slug: ["automacao", "skill-teste"],
    area: "Automacao",
    module: "Skills",
    summary: "Editor de contrato e simulador de execucao com timeout, retries e mascaramento.",
    states: ["ready", "timeout", "schema_error"],
    endpoints: ["GET /v1/skills/{skillId}", "POST /v1/skills/{skillId}/validate"],
    metrics: [
      { label: "Timeout", value: "30s", tone: "risk" },
      { label: "Retries", value: "2" }
    ],
    checklist: ["Mascara secrets", "Exibe schema", "Timeout reproduzivel"]
  },
  {
    code: "T29",
    title: "Provedores e modelos",
    slug: ["automacao", "modelos"],
    area: "Automacao",
    module: "Modelos",
    summary: "Cadastro de providers, modelos, pricing, fallback e vigencia de preco.",
    states: ["configured", "missing_pricing", "deprecated"],
    endpoints: ["GET /v1/models", "PATCH /v1/models/{modelId}"],
    metrics: [
      { label: "Modelos", value: "14" },
      { label: "Sem preco vigente", value: "1", tone: "risk" }
    ],
    checklist: ["Vigencia visivel", "Fallback documentado", "Preco nao some"]
  },
  {
    code: "T30",
    title: "Biblioteca e versoes de prompts",
    slug: ["automacao", "prompts"],
    area: "Automacao",
    module: "Prompts",
    summary: "Biblioteca de prompts com diff, owner, changelog e status de publicacao.",
    states: ["draft", "published", "rollback_preview"],
    endpoints: ["GET /v1/prompts", "GET /v1/prompts/{promptId}/versions"],
    metrics: [
      { label: "Prompts", value: "31" },
      { label: "Versao ativa", value: "v18", tone: "accent" }
    ],
    checklist: ["Diff legivel", "Owner claro", "Rollback previsivel"]
  },
  {
    code: "T31",
    title: "Lista de workflows",
    slug: ["automacao", "workflows"],
    area: "Automacao",
    module: "Workflows",
    summary: "Catalogo de workflows com filtros por dominio, status e risco operacional.",
    states: ["drafts", "published", "archived"],
    endpoints: ["GET /v1/workflows"],
    metrics: [
      { label: "Publicados", value: "12" },
      { label: "Rascunhos", value: "4" }
    ],
    checklist: ["Status explicito", "Impacto por dominio", "Busca por owner"]
  },
  {
    code: "T32",
    title: "Editor visual de workflow",
    slug: ["automacao", "workflow-editor"],
    area: "Automacao",
    module: "Workflows",
    summary: "Canvas visual para passos de agente, decisao, espera, revisao e aprovacao.",
    states: ["editing", "invalid_graph", "simulation"],
    endpoints: ["GET /v1/workflows/{workflowId}", "POST /v1/workflows/{workflowId}/validate"],
    metrics: [
      { label: "Nodes", value: "14" },
      { label: "Warnings", value: "2", tone: "risk" }
    ],
    checklist: ["Impede publicar grafo invalido", "Mostra schema do node", "Conexoes claras"]
  },
  {
    code: "T33",
    title: "Historico de versoes",
    slug: ["automacao", "workflow-versoes"],
    area: "Automacao",
    module: "Workflows",
    summary: "Historico de versoes, diff e rollback preservando execucoes antigas ligadas a origem.",
    states: ["timeline", "diff", "rollback_confirmation"],
    endpoints: ["GET /v1/workflows/{workflowId}/versions", "POST /v1/workflows/{workflowId}/rollback"],
    metrics: [
      { label: "Versoes", value: "8" },
      { label: "Execucoes legadas", value: "23" }
    ],
    checklist: ["Versao imutavel", "Rollback nao move runs antigos", "Diff compreensivel"]
  },
  {
    code: "T34",
    title: "Biblioteca de playbooks",
    slug: ["automacao", "playbooks"],
    area: "Automacao",
    module: "Playbooks",
    summary: "Playbooks parametrizados para iniciar workflows com contexto, owners e templates.",
    states: ["catalog", "instantiate", "missing_input"],
    endpoints: ["GET /v1/playbooks", "POST /v1/playbooks/{playbookId}/instantiate"],
    metrics: [
      { label: "Playbooks", value: "17" },
      { label: "Prontos para uso", value: "11", tone: "accent" }
    ],
    checklist: ["Parametros obrigatorios claros", "Mostra workflow de origem", "Instanciacao segura"]
  },
  {
    code: "T35",
    title: "Biblioteca de conhecimento",
    slug: ["conhecimento", "biblioteca"],
    area: "Conhecimento",
    module: "Conhecimento",
    summary: "Catalogo de documentos com status de ingestao, classificacao, owner e ultima revisao.",
    states: ["ready", "processing", "failed", "empty"],
    endpoints: ["GET /v1/knowledge/documents"],
    metrics: [
      { label: "Documentos", value: "142" },
      { label: "Falhas", value: "3", tone: "risk" }
    ],
    checklist: ["Filtra por tenant", "Status visivel", "Revisao rastreavel"]
  },
  {
    code: "T36",
    title: "Documento e ingestao",
    slug: ["conhecimento", "ingestao"],
    area: "Conhecimento",
    module: "Conhecimento",
    summary: "Upload de documento, status por chunk, erros de parse e reprocessamento assistido.",
    states: ["uploading", "chunk_errors", "reprocessing"],
    endpoints: ["POST /v1/knowledge/documents", "GET /v1/knowledge/documents/{id}/chunks"],
    metrics: [
      { label: "Chunks", value: "38" },
      { label: "Erros", value: "2", tone: "risk" }
    ],
    checklist: ["Mostra job lifecycle", "Erros por chunk", "Retry seguro"]
  },
  {
    code: "T37",
    title: "Memoria operacional",
    slug: ["conhecimento", "memoria"],
    area: "Conhecimento",
    module: "Memoria",
    summary: "Itens de memoria com fato, inferencia ou decisao, validade e contestacao.",
    states: ["approved", "contested", "expired"],
    endpoints: ["GET /v1/memory/items", "POST /v1/memory/items/{id}/contest"],
    metrics: [
      { label: "Itens ativos", value: "89" },
      { label: "Contestados", value: "6", tone: "risk" }
    ],
    checklist: ["Mostra fonte", "Validade explicita", "Contestacao auditavel"]
  },
  {
    code: "T38",
    title: "Busca semantica/debug RAG",
    slug: ["conhecimento", "busca-semantica"],
    area: "Conhecimento",
    module: "Memoria",
    summary: "Busca semantica com score, filtros, fonte, confidencialidade e debug de recuperação.",
    states: ["results", "filtered", "cross_tenant_blocked"],
    endpoints: ["POST /v1/search/semantic"],
    metrics: [
      { label: "Resultados", value: "12" },
      { label: "Score topo", value: "0.91", tone: "accent" }
    ],
    checklist: ["Nao expoe outro tenant", "Mostra score", "Fonte sempre clicavel"]
  },
  {
    code: "T39",
    title: "Contas e contatos",
    slug: ["comercial", "contas-contatos"],
    area: "Comercial",
    module: "CRM",
    summary: "Gestao de contas, contatos, importacao e deduplicacao com consentimento e origem.",
    states: ["catalog", "import_review", "dedupe_preview"],
    endpoints: ["GET /v1/crm/accounts", "GET /v1/crm/contacts", "POST /v1/crm/imports"],
    metrics: [
      { label: "Contas", value: "164" },
      { label: "Duplicatas", value: "9", tone: "risk" }
    ],
    checklist: ["Preview de merge", "Base legal visivel", "Origem do dado clara"]
  },
  {
    code: "T40",
    title: "Leads",
    slug: ["comercial", "leads"],
    area: "Comercial",
    module: "CRM",
    summary: "Fila de leads com sinais, score ICP, proxima acao e filtros por etapa e owner.",
    states: ["scored", "unassigned", "empty"],
    endpoints: ["GET /v1/crm/leads"],
    metrics: [
      { label: "Leads quentes", value: "18", tone: "accent" },
      { label: "Sem owner", value: "4", tone: "risk" }
    ],
    checklist: ["Score explicado", "Proxima acao visivel", "Filtra por etapa"]
  },
  {
    code: "T41",
    title: "Detalhe do lead",
    slug: ["comercial", "lead-detalhe"],
    area: "Comercial",
    module: "CRM",
    summary: "Timeline, sinais, contexto, ICP, origem e atividades sugeridas por lead.",
    states: ["active", "disqualified", "converted"],
    endpoints: ["GET /v1/crm/leads/{leadId}"],
    metrics: [
      { label: "Score ICP", value: "82", tone: "accent" },
      { label: "Ultimo sinal", value: "Hoje" }
    ],
    checklist: ["Origem preservada", "Timeline coerente", "Acao sugerida segura"]
  },
  {
    code: "T42",
    title: "Pipeline e oportunidades",
    slug: ["comercial", "pipeline"],
    area: "Comercial",
    module: "CRM",
    summary: "Funil de oportunidades com forecast, ganho/perda e campos obrigatorios por etapa.",
    states: ["board", "forecast", "stage_guard"],
    endpoints: ["GET /v1/crm/opportunities", "POST /v1/crm/opportunities/{id}/stage"],
    metrics: [
      { label: "Pipeline", value: "R$ 1,2M", tone: "accent" },
      { label: "Em risco", value: "R$ 220k", tone: "risk" }
    ],
    checklist: ["Bloqueia campos faltantes", "Forecast por owner", "Ganhos/perdas auditados"]
  },
  {
    code: "T43",
    title: "Campanhas",
    slug: ["comercial", "campanhas"],
    area: "Comercial",
    module: "Conteudo",
    summary: "Gestao de campanhas com objetivos, canais, publico, status e atribuicao futura.",
    states: ["draft", "running", "paused", "completed"],
    endpoints: ["GET /v1/content/campaigns"],
    metrics: [
      { label: "Ativas", value: "5", tone: "accent" },
      { label: "Atrasadas", value: "1", tone: "risk" }
    ],
    checklist: ["Objetivo claro", "Canal e publico definidos", "Status auditavel"]
  },
  {
    code: "T44",
    title: "Estudio de conteudo",
    slug: ["comercial", "conteudo"],
    area: "Comercial",
    module: "Conteudo",
    summary: "Briefings, ativos, variantes, aprovacoes e metadados editoriais por conteudo.",
    states: ["editing", "awaiting_approval", "changes_requested"],
    endpoints: ["GET /v1/content/assets", "POST /v1/content/assets"],
    metrics: [
      { label: "Variantes", value: "8" },
      { label: "Aguardando aprovacao", value: "3", tone: "risk" }
    ],
    checklist: ["Mostra brief", "Versiona variante", "Integra com aprovacao"]
  },
  {
    code: "T45",
    title: "Calendario editorial/publicacoes",
    slug: ["comercial", "publicacoes"],
    area: "Comercial",
    module: "Conteudo",
    summary: "Calendario de publicacoes com agendamento, erro de provider e retry seguro.",
    states: ["scheduled", "published", "provider_error"],
    endpoints: ["GET /v1/content/publications", "POST /v1/content/publications/{id}/retry"],
    metrics: [
      { label: "Agendadas", value: "21" },
      { label: "Falhas", value: "2", tone: "risk" }
    ],
    checklist: ["Preserva payload na falha", "Mostra canal", "Retry seguro"]
  },
  {
    code: "T46",
    title: "Lista de experimentos",
    slug: ["aprendizado", "experimentos"],
    area: "Aprendizado",
    module: "Experimentos",
    summary: "Catalogo de experimentos com hipotese, status, metrica e owner.",
    states: ["draft", "running", "completed"],
    endpoints: ["GET /v1/experiments"],
    metrics: [
      { label: "Rodando", value: "3", tone: "accent" },
      { label: "Concluidos", value: "14" }
    ],
    checklist: ["Hipotese clara", "Owner visivel", "Status imutavel quando iniciado"]
  },
  {
    code: "T47",
    title: "Configuracao e resultado do experimento",
    slug: ["aprendizado", "experimento-detalhe"],
    area: "Aprendizado",
    module: "Experimentos",
    summary: "Detalhe de experimento com variantes, janela, stop rule e resultado.",
    states: ["configuring", "locked", "result"],
    endpoints: ["GET /v1/experiments/{experimentId}", "PATCH /v1/experiments/{experimentId}"],
    metrics: [
      { label: "Variantes", value: "3" },
      { label: "Metrica primaria", value: "SQL rate", tone: "accent" }
    ],
    checklist: ["Bloqueia campos imutaveis", "Explica janela", "Mostra conclusao e amostra"]
  },
  {
    code: "T48",
    title: "Dashboard executivo",
    slug: ["aprendizado", "dashboard-executivo"],
    area: "Aprendizado",
    module: "Analytics",
    summary: "Visao executiva de operacao, receita influenciada, qualidade e custo.",
    states: ["executive", "partial", "drilldown"],
    endpoints: ["GET /v1/analytics/summary"],
    metrics: [
      { label: "Receita influenciada", value: "R$ 480k", tone: "accent" },
      { label: "Custo operacional", value: "R$ 31k" }
    ],
    checklist: ["Fonte do KPI", "Periodo/timezone", "Drilldown ate registros"]
  },
  {
    code: "T49",
    title: "Operacoes e SLA",
    slug: ["aprendizado", "analytics-sla"],
    area: "Aprendizado",
    module: "Analytics",
    summary: "Painel operacional com SLA, throughput, backlog e falhas por equipe.",
    states: ["trend", "comparison", "breach"],
    endpoints: ["GET /v1/analytics/operations"],
    metrics: [
      { label: "Throughput", value: "138/semana" },
      { label: "Breaches", value: "4", tone: "risk" }
    ],
    checklist: ["Comparativo temporal", "Drilldown por equipe", "Freshness do dado"]
  },
  {
    code: "T50",
    title: "Performance de agentes/skills",
    slug: ["aprendizado", "analytics-agentes"],
    area: "Aprendizado",
    module: "Analytics",
    summary: "Metricas de latencia, sucesso, custo e falha por agente, skill e modelo.",
    states: ["leaderboard", "degraded", "cost_spike"],
    endpoints: ["GET /v1/analytics/agents"],
    metrics: [
      { label: "Sucesso medio", value: "91%", tone: "accent" },
      { label: "Spikes de custo", value: "2", tone: "risk" }
    ],
    checklist: ["Filtra por provider", "Mostra custo por execucao", "Degradacao visivel"]
  },
  {
    code: "T51",
    title: "Custos, budgets e quotas",
    slug: ["aprendizado", "custos"],
    area: "Aprendizado",
    module: "Analytics",
    summary: "Controle de budgets, quotas e consumo por tenant, equipe, agente e campanha.",
    states: ["within_budget", "near_limit", "exceeded"],
    endpoints: ["GET /v1/analytics/costs", "GET /v1/budgets"],
    metrics: [
      { label: "Budget do mes", value: "68%", tone: "accent" },
      { label: "Quotas em alerta", value: "3", tone: "risk" }
    ],
    checklist: ["Limites claros", "Tendencia por periodo", "Alertas compreensiveis"]
  },
  {
    code: "T52",
    title: "Funil e atribuicao",
    slug: ["aprendizado", "funil"],
    area: "Aprendizado",
    module: "Analytics",
    summary: "Conversao de funil e atribuicao declarada ligando campanha, conteudo, lead e receita.",
    states: ["multi_touch", "single_touch", "unknown_source"],
    endpoints: ["GET /v1/analytics/funnel"],
    metrics: [
      { label: "SQL -> Won", value: "18%" },
      { label: "Receita atribuida", value: "R$ 380k", tone: "accent" }
    ],
    checklist: ["Modelo declarado", "Fonte por KPI", "Drilldown por campanha"]
  },
  {
    code: "T53",
    title: "Organizacao e branding",
    slug: ["administracao", "organizacao"],
    area: "Administracao",
    module: "Admin",
    summary: "Configuracoes da organizacao, branding, dominio, timezone e defaults operacionais.",
    states: ["configured", "preview", "unsaved"],
    endpoints: ["GET /v1/organizations/{organizationId}", "PATCH /v1/organizations/{organizationId}"],
    metrics: [
      { label: "Brand kit", value: "Ativo", tone: "accent" },
      { label: "Dominios", value: "2" }
    ],
    checklist: ["Preview do branding", "Defaults por tenant", "Nao afeta portal externo sem revisao"]
  },
  {
    code: "T54",
    title: "Membros, convites e papeis",
    slug: ["administracao", "membros"],
    area: "Administracao",
    module: "Admin",
    summary: "Gestao de membros, convites, papeis e bloqueio do ultimo owner.",
    states: ["members", "invite", "last_owner_guard"],
    endpoints: ["GET /v1/memberships", "POST /v1/invitations", "PATCH /v1/memberships/{id}"],
    metrics: [
      { label: "Membros", value: "42" },
      { label: "Owners", value: "2", tone: "accent" }
    ],
    checklist: ["Nao remove ultimo owner", "Convite idempotente", "Papeis claros"]
  },
  {
    code: "T55",
    title: "Integracoes e webhooks",
    slug: ["administracao", "integracoes"],
    area: "Administracao",
    module: "Admin",
    summary: "Catalogo de integracoes, webhooks, deliveries e secrets revelados apenas uma vez.",
    states: ["connected", "secret_once", "delivery_failed"],
    endpoints: ["GET /v1/integrations", "POST /v1/webhooks/test"],
    metrics: [
      { label: "Integracoes", value: "7" },
      { label: "Falhas de delivery", value: "3", tone: "risk" }
    ],
    checklist: ["Secret aparece uma vez", "Historico de deliveries", "Teste seguro"]
  },
  {
    code: "T56",
    title: "Privacidade, retencao e auditoria",
    slug: ["administracao", "privacidade-auditoria"],
    area: "Administracao",
    module: "Compliance",
    summary: "LGPD, legal hold, exportacao, exclusao e auditoria append-only sem editar/excluir.",
    states: ["request_open", "legal_hold", "audit_only"],
    endpoints: ["GET /v1/privacy/requests", "GET /v1/audit/events"],
    metrics: [
      { label: "Requests abertas", value: "4", tone: "risk" },
      { label: "Eventos de auditoria", value: "12.8k" }
    ],
    checklist: ["Sem editar/excluir auditoria", "Impacto e escopo claros", "Status de job LGPD"]
  }
];

export const screens = definitions;

export const screensByArea = definitions.reduce<Record<ScreenDefinition["area"], ScreenDefinition[]>>(
  (accumulator, screen) => {
    accumulator[screen.area].push(screen);
    return accumulator;
  },
  {
    Acesso: [],
    Operacao: [],
    Governanca: [],
    Automacao: [],
    Conhecimento: [],
    Comercial: [],
    Aprendizado: [],
    Administracao: []
  }
);

export const areaOrder: ScreenDefinition["area"][] = [
  "Acesso",
  "Operacao",
  "Governanca",
  "Automacao",
  "Conhecimento",
  "Comercial",
  "Aprendizado",
  "Administracao"
];

export function getScreenBySlug(slug: string[]): ScreenDefinition | undefined {
  return definitions.find((screen) => screen.slug.join("/") === slug.join("/"));
}

export function getDefaultScreen(): ScreenDefinition {
  return definitions.find((screen) => screen.code === "T06") ?? definitions[0]!;
}
