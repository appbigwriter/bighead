import { screens, screensByArea, type ScreenDefinition } from "./screen-catalog";
import type { RealtimeMessage } from "./message-reconciliation";

export type MockStateCard = {
  title: string;
  value: string;
  detail: string;
  tone?: "default" | "risk" | "accent";
};

export type MockFeedItem = {
  id?: string;
  title: string;
  description: string;
  meta: string;
};

export type AnalyticsDrilldown = { card: "total"; dimension: string; value: number; recordIds: string[]; recordCount: number; recordsTruncated: boolean; recordsEndpoint: "/v1/analytics/summary/records"; periodFrom: string; periodTo: string };

export type WorkspaceOption = {
  id: string;
  name: string;
  status?: string;
  version?: number;
  round?: number;
  updatedAt?: string;
  isPrivate?: boolean;
  hasAccess?: boolean;
  unreadCount?: number;
  riskLevel?: string;
  dueAt?: string;
  slaAt?: string;
  assigneeId?: string;
  nextAction?: string;
};

export type WorkspaceSnapshot = {
  organizations: string[];
  currentOrganization: string;
  currentOrganizationId?: string;
  organizationOptions: WorkspaceOption[];
  roomOptions: WorkspaceOption[];
  messageOptions: RealtimeMessage[];
  taskOptions: WorkspaceOption[];
  approvalOptions: WorkspaceOption[];
  experimentOptions: WorkspaceOption[];
  notifications: number | null;
  commandShortcuts: string[];
  summaryCards: MockStateCard[];
  inboxItems: MockFeedItem[];
  accessMoments: MockFeedItem[];
  roomMoments: MockFeedItem[];
  taskMoments: MockFeedItem[];
  governanceMoments: MockFeedItem[];
  automationMoments: MockFeedItem[];
  knowledgeMoments: MockFeedItem[];
  commercialMoments: MockFeedItem[];
  analyticsMoments: MockFeedItem[];
  analyticsDrilldowns: AnalyticsDrilldown[];
  adminMoments: MockFeedItem[];
  screens: ScreenDefinition[];
  areas: typeof screensByArea;
};

export function getWorkspaceSnapshot(): WorkspaceSnapshot {
  return {
    organizations: ["Acme Growth", "Northwind Labs", "FBR Ventures", "Atlas RevOps"],
    currentOrganization: "Acme Growth",
    currentOrganizationId: "fixture-acme",
    organizationOptions: [{ id: "fixture-acme", name: "Acme Growth" }],
    roomOptions: [
      { id: "fixture-room", name: "Sala de operacao", unreadCount: 2 },
      { id: "fixture-private", name: "Diretoria", isPrivate: true, hasAccess: true, unreadCount: 1 },
      { id: "fixture-denied", name: "M&A confidencial", isPrivate: true, hasAccess: false, unreadCount: 40 }
    ],
    messageOptions: [
      { id: "fixture-message", roomId: "fixture-room", clientId: "fixture-client", body: "Mensagem reconciliada", createdAt: "2026-01-01T00:00:00Z" }
    ],
    taskOptions: [
      { id: "fixture-task", name: "Tarefa de exemplo", status: "new", version: 1 },
      { id: "fixture-dependent-task", name: "Tarefa que depende da atual", status: "triaged", version: 2 }
    ],
    approvalOptions: [{ id: "fixture-approval", name: "Aprovacao de exemplo", status: "pending", round: 1 }],
    experimentOptions: [{ id: "fixture-experiment", name: "Experimento de exemplo", status: "draft", updatedAt: "2026-01-01T00:00:00Z" }],
    notifications: 11,
    commandShortcuts: [
      "Criar tarefa",
      "Abrir sala",
      "Buscar lead",
      "Executar playbook",
      "Revisar aprovacoes"
    ],
    summaryCards: [
      {
        title: "Throughput semanal",
        value: "138",
        detail: "12% acima da semana anterior",
        tone: "accent"
      },
      {
        title: "Tarefas em risco",
        value: "6",
        detail: "3 aguardando decisao humana",
        tone: "risk"
      },
      {
        title: "Custo operacional",
        value: "R$ 31k",
        detail: "68% do budget mensal consumido"
      }
    ],
    inboxItems: [
      {
        title: "Aprovacao de campanha enterprise",
        description: "Esperando decisao do cliente externo antes de publicar no LinkedIn.",
        meta: "T20 • risco alto • vence em 2h"
      },
      {
        title: "Workflow SDR outbound com skill de enriquecimento",
        description: "Node de timeout impactando 14 execucoes e exigindo rollback.",
        meta: "T32 • 2 warnings • 1 skill degradada"
      },
      {
        title: "Lead Atlas Logistics",
        description: "Score ICP subiu apos novo sinal de compra no segmento mid-market.",
        meta: "T41 • score 82 • owner Camila"
      }
    ],
    accessMoments: [
      {
        title: "Convite pendente para time comercial",
        description: "Membro convidado ainda nao aceitou acesso de reviewer para conteudo.",
        meta: "email transacional • expira em 18h"
      },
      {
        title: "Sessao encerrada em dispositivo antigo",
        description: "Logout remoto concluido apos redefinicao de credencial.",
        meta: "T09 • dispositivo Windows"
      },
      {
        title: "Onboarding enterprise salvo no passo 3",
        description: "Wizard pausado apos configuracao inicial de objetivos e branding.",
        meta: "T04 • retomavel"
      }
    ],
    roomMoments: [
      {
        title: "Sala #operacoes-produto",
        description: "Nova mensagem de agente com citacao de fonte e custo R$ 3,20.",
        meta: "T11 • 4 nao lidas"
      },
      {
        title: "Upload em quarentena",
        description: "Arquivo PDF aguardando revisao antes de liberar preview aos membros.",
        meta: "T13 • 12 MB"
      },
      {
        title: "Criar tarefa a partir da mensagem 8831",
        description: "Acao preserva origem, thread e anexos relevantes no detalhe da tarefa.",
        meta: "T11 -> T15"
      }
    ],
    taskMoments: [
      {
        title: "Tarefa BH-1842 em ready_for_review",
        description: "Plano concluido, artefato anexado e aprovacao interna aguardando revisor.",
        meta: "T16 • SLA restante 3h"
      },
      {
        title: "Falha agrupada em enrichment.timeout",
        description: "14 runs impactadas com retry seguro e rollback sugerido do workflow.",
        meta: "T18 • severidade alta"
      },
      {
        title: "Calendario de SLA da sexta-feira",
        description: "Cinco entregas em risco e duas pendencias bloqueadas por aprovacao externa.",
        meta: "T19 • owner Camila"
      }
    ],
    governanceMoments: [
      {
        title: "Aprovacao concorrente no portal externo",
        description: "Segundo decisor tentou responder depois da rodada ja ter sido encerrada.",
        meta: "T21 • conflito de decisao"
      },
      {
        title: "Scorecard Sentinel com falha critica",
        description: "Conteudo externo foi bloqueado por baixa aderencia ao checklist de compliance.",
        meta: "T22 • score 61/100"
      },
      {
        title: "Politica de segregacao em simulacao",
        description: "Nova regra exige dupla aprovacao quando o risco da skill for alto.",
        meta: "T23 • simulador ativo"
      }
    ],
    automationMoments: [
      {
        title: "Workflow outbound v8 com warnings",
        description: "Um node de espera esta sem timeout e afeta 11 playbooks dependentes.",
        meta: "T32 • impacto alto"
      },
      {
        title: "Skill enrichment.lookup degradada",
        description: "Teste automatizado de health mostra timeout em 2 das ultimas 5 execucoes.",
        meta: "T28 • retries 2"
      },
      {
        title: "Agente SDR enterprise com novo prompt",
        description: "Versao de prompt publicada exige revisao de consumidores antes do rollout completo.",
        meta: "T26 • 6 consumidores"
      }
    ],
    knowledgeMoments: [
      {
        title: "Documento de ICP em reprocessamento",
        description: "Chunk 14 falhou por parse e foi reenfileirado com ajustes de separacao.",
        meta: "T36 • job ativo"
      },
      {
        title: "Memoria contestada por time comercial",
        description: "Informacao sobre pricing anterior deixou de aparecer nos resultados da busca.",
        meta: "T37 • contested"
      },
      {
        title: "Busca semantica para onboarding enterprise",
        description: "Top score recuperou politica vigente com fonte revisada e escopo correto do tenant.",
        meta: "T38 • score 0.91"
      }
    ],
    commercialMoments: [
      {
        title: "Lead Atlas Logistics promovido a oportunidade",
        description: "Mudanca de estagio exigiu budget estimado e data de fechamento prevista.",
        meta: "T42 • forecast R$ 180k"
      },
      {
        title: "Campanha Q3 enterprise pausada",
        description: "Publicacao social falhou e o payload foi preservado para retry seguro.",
        meta: "T45 • provider error"
      },
      {
        title: "Dedupe de contatos em revisao",
        description: "Preview mostra merge de 2 registros com consentimento e historico de origem.",
        meta: "T39 • aprovacao manual"
      }
    ],
    analyticsMoments: [
      {
        title: "Experimento onboarding-enterprise bloqueado",
        description: "Campos de alocacao e stop rule ficaram imutaveis apos o inicio da janela.",
        meta: "T47 • running"
      },
      {
        title: "Dashboard executivo com spike de custo",
        description: "Uso de modelos premium subiu 18% e ja impacta a quota de duas equipes.",
        meta: "T48/T51 • budget alert"
      },
      {
        title: "Atribuicao multi-touch atualizada",
        description: "Receita influenciada foi recalculada com novo modelo declarado por campanha.",
        meta: "T52 • freshness 5 min"
      }
    ],
    analyticsDrilldowns: [
      { card: "total", dimension: "in_progress", value: 2, recordIds: ["11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"], recordCount: 2, recordsTruncated: false, recordsEndpoint: "/v1/analytics/summary/records", periodFrom: "2026-06-13T00:00:00Z", periodTo: "2026-07-13T00:00:00Z" },
      { card: "total", dimension: "overdue", value: 1, recordIds: ["33333333-3333-4333-8333-333333333333"], recordCount: 1, recordsTruncated: false, recordsEndpoint: "/v1/analytics/summary/records", periodFrom: "2026-06-13T00:00:00Z", periodTo: "2026-07-13T00:00:00Z" }
    ],
    adminMoments: [
      {
        title: "Ultimo owner protegido",
        description: "Tentativa de rebaixamento foi bloqueada para evitar tenant sem responsavel.",
        meta: "T54 • guard rail"
      },
      {
        title: "Secret de webhook recem-gerado",
        description: "Valor exibido uma unica vez com delivery de teste pendente.",
        meta: "T55 • reveal once"
      },
      {
        title: "Pedido LGPD em execucao",
        description: "Exportacao de auditoria e dados pessoais segue com legal hold preservado.",
        meta: "T56 • job running"
      }
    ],
    screens,
    areas: screensByArea
  };
}
