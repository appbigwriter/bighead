import type { ScreenCode } from "@/lib/screen-catalog";

export type PlaybookPhase = "blocked" | "ready" | "applied";

export type ScreenPlaybook = {
  heading: string;
  action: string;
  precondition: string;
  effect: string;
  guard: string;
  domain: "identity" | "collaboration" | "operations" | "governance" | "automation" | "knowledge" | "commercial" | "analytics" | "admin";
};

export type PlaybookState = { phase: PlaybookPhase; revision: number };

export function transitionPlaybook(definition: ScreenPlaybook, state: PlaybookState, event: "satisfy" | "apply" | "reset") {
  if (event === "reset") return { state: { phase: "blocked", revision: state.revision } satisfies PlaybookState };
  if (event === "satisfy") return { state: { phase: "ready", revision: state.revision } satisfies PlaybookState };
  if (state.phase !== "ready") return { state, error: definition.guard };
  return { state: { phase: "applied", revision: state.revision + 1 } satisfies PlaybookState, effect: definition.effect };
}

export const screenPlaybooks = {
  T02: ["Recuperar acesso com token unico", "Enviar link seguro", "Email normalizado e rate limit disponivel", "Link opaco emitido sem revelar a existencia da conta", "Envio bloqueado ate email valido e janela de rate limit livre", "identity"],
  T03: ["Validar convite e membership", "Aceitar convite", "Token valido e email autenticado corresponde ao convite", "Membership criada uma unica vez para a organizacao convidante", "Convite expirado, usado ou de outro email nao pode criar membership", "identity"],
  T09: ["Gerenciar preferencias e sessoes", "Encerrar outra sessao", "Sessao alvo pertence ao usuario e nao e a sessao atual", "Sessao alvo revogada mantendo este dispositivo conectado", "Sessao atual ou de outro usuario nunca pode ser revogada por este fluxo", "identity"],
  T10: ["Organizar inbox de salas", "Aplicar filtro de privadas", "Membership ativa carregada no tenant atual", "Somente salas privadas autorizadas permanecem na lista", "Sala privada sem membership nunca pode aparecer nem em contagens", "collaboration"],
  T12: ["Administrar membros da sala", "Validar moderadores", "Lista de membros e papeis esta atualizada", "Alteracao aceita preservando ao menos um moderador", "Remocao do ultimo moderador e rejeitada", "collaboration"],
  T13: ["Inspecionar arquivos e quarentena", "Revalidar arquivo", "Arquivo esta em quarentena e possui checksum", "Nova analise enfileirada sem liberar a abertura", "Arquivo em quarentena continua indisponivel ate resultado seguro", "collaboration"],
  T18: ["Priorizar grupos de falha", "Reprocessar grupo", "Grupo possui falhas retryable selecionadas", "Nova tentativa idempotente criada preservando o historico", "Falha nao retryable ou tentativa duplicada nao e reprocessada", "operations"],
  T19: ["Reagendar tarefa em risco", "Confirmar reagendamento", "Novo prazo e justificativa foram informados", "Prazo alterado com contexto e auditoria preservados", "Prazo invalido ou sem justificativa nao e salvo", "operations"],
  T20: ["Triar aprovacoes por risco", "Ordenar fila critica", "Fila do tenant foi carregada com risco e prazo", "Fila ordenada por risco e SLA sem autoaprovacao", "Solicitante nunca pode autoaprovar o proprio item", "governance"],
  T22: ["Analisar scorecard Sentinel QA", "Explicar falha critica", "Rodada e criterio critico foram selecionados", "Criterio, politica e tendencia da rodada foram correlacionados", "Score sem evidencia nao pode ser apresentado como conclusivo", "governance"],
  T24: ["Revisar item no portal isolado", "Validar token externo", "Token opaco nao expirado foi apresentado", "Escopo do item carregado sem montar o shell interno", "Token expirado ou fora do escopo nao revela dados internos", "governance"],
  T25: ["Comparar agentes versionados", "Abrir consumidores", "Versao de agente foi selecionada", "Consumers e metricas da versao foram carregados", "Versao inexistente nao reutiliza consumers de outra versao", "automation"],
  T26: ["Avaliar impacto do agente", "Gerar analise de impacto", "Draft possui versao base e configuracao valida", "Impacto em consumers, limites e skills calculado antes da publicacao", "Draft com schema invalido nao pode ser publicado", "automation"],
  T27: ["Auditar catalogo de skills", "Filtrar skills de alto risco", "Catalogo e health checks estao atualizados", "Skills de alto risco exibidas com schema, versao e health", "Skill sem schema ou health nao pode ser marcada como segura", "automation"],
  T29: ["Validar pricing e fallback", "Verificar vigencia", "Modelo e periodo de vigencia foram selecionados", "Pricing vigente validado e fallback documentado preservado", "Modelo sem preco vigente nao pode receber estimativa enganosa", "automation"],
  T30: ["Comparar versoes de prompt", "Preparar rollback", "Duas versoes distintas foram selecionadas", "Diff e changelog carregados sem trocar a versao ativa", "Rollback nao pode sobrescrever silenciosamente a versao ativa", "automation"],
  T31: ["Localizar workflows por dominio", "Filtrar por owner", "Owner pertence ao tenant atual", "Workflows exibidos com status, dominio e risco operacional", "Owner externo ao tenant nao pode produzir resultados", "automation"],
  T33: ["Simular workflow publicado", "Executar simulacao", "Versao publicada e input valido foram congelados", "Passos, custos e resultado da simulacao ficaram rastreaveis", "Simulacao nunca altera a versao publicada nem dispara efeitos reais", "automation"],
  T34: ["Investigar execucoes do workflow", "Comparar tentativas", "Duas tentativas do mesmo run foram selecionadas", "Duracao, erro e correlacao das tentativas foram comparados", "Tentativas de runs diferentes nao podem formar comparacao causal", "automation"],
  T35: ["Navegar fontes de conhecimento", "Filtrar fontes ativas", "Politica de acesso do usuario foi resolvida", "Fontes ativas autorizadas exibidas com owner e freshness", "Fonte sem permissao nao aparece em itens, facets ou contagens", "knowledge"],
  T36: ["Editar documento versionado", "Salvar nova versao", "Changelog preenchido e base version ainda atual", "Nova versao criada mantendo a publicada intacta", "Conflito de versao preserva o rascunho e exige reconciliacao", "knowledge"],
  T37: ["Acompanhar pipeline de ingestao", "Reprocessar documento", "Etapa com falha retryable foi identificada", "Reprocessamento idempotente iniciado na etapa com falha", "Retry nao duplica chunks nem repete etapas concluidas", "knowledge"],
  T39: ["Revisar memoria governada", "Marcar memoria para revisao", "Motivo e owner responsavel foram informados", "Memoria sinalizada com trilha de auditoria", "Memoria protegida nao pode ser alterada sem motivo auditavel", "knowledge"],
  T41: ["Consolidar conta e stakeholders", "Atualizar mapa de poder", "Conta e stakeholders pertencem ao tenant atual", "Papel, influencia e proximo passo foram versionados", "Stakeholder de outra conta ou tenant nao pode ser associado", "commercial"],
  T43: ["Preparar atividade comercial", "Registrar interacao", "Oportunidade, owner e data foram definidos", "Interacao adicionada a timeline da oportunidade", "Interacao sem consentimento exigido ou owner valido nao e registrada", "commercial"],
  T44: ["Produzir conteudo com briefing", "Enviar para revisao", "Briefing, canal e fontes obrigatorias estao completos", "Versao imutavel enviada para revisao com fontes vinculadas", "Conteudo sem fonte obrigatoria ou canal nao entra em revisao", "commercial"],
  T46: ["Gerenciar biblioteca de ativos", "Validar direitos de uso", "Licenca possui canais e periodo definidos", "Ativo liberado apenas no escopo coberto pela licenca", "Licenca expirada ou canal ausente bloqueia o uso do ativo", "commercial"],
  T48: ["Analisar funil e atribuicao", "Aplicar janela de atribuicao", "Periodo, modelo e timezone foram selecionados", "Funil recalculado com janela explicita e freshness", "Dados fora da janela ou sem origem ficam segregados como desconhecidos", "analytics"],
  T49: ["Monitorar custos de IA", "Detalhar desvio de custo", "Periodo e centro de custo foram selecionados", "Desvio explicado por agente, modelo e tokens", "Custo parcial nao pode ser exibido sem indicador de freshness", "analytics"],
  T50: ["Avaliar qualidade operacional", "Abrir tendencia de score", "Politica, canal e periodo possuem amostra suficiente", "Tendencia exibida por politica, canal e rodada", "Amostra insuficiente nao pode gerar tendencia conclusiva", "analytics"],
  T51: ["Configurar regras de notificacao", "Testar preferencia", "Canal verificado e preferencia valida foram selecionados", "Teste enviado uma vez sem persistir duplicatas", "Canal nao verificado ou regra duplicada bloqueia o teste", "analytics"],
  T52: ["Consultar trilha de auditoria", "Filtrar por correlacao", "Correlation id valido pertence ao tenant atual", "Eventos append-only correlacionados foram carregados", "Filtro nunca permite editar eventos nem atravessar tenants", "analytics"],
  T53: ["Administrar organizacao", "Salvar politica do tenant", "Politica valida e versao atual foram carregadas", "Politica atualizada no tenant e registrada na auditoria", "Conflito ou dominio invalido preserva a politica anterior", "admin"]
} satisfies Record<string, readonly [string, string, string, string, string, ScreenPlaybook["domain"]]>;

export type PlaybookScreenCode = keyof typeof screenPlaybooks;

export function getScreenPlaybook(code: ScreenCode): ScreenPlaybook | undefined {
  const row = screenPlaybooks[code as PlaybookScreenCode];
  if (!row) return undefined;
  return { heading: row[0], action: row[1], precondition: row[2], effect: row[3], guard: row[4], domain: row[5] };
}
