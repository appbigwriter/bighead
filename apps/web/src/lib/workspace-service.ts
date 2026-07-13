import { getWorkspaceSnapshot } from "./mock-workspace";
import type { WorkspaceSnapshot } from "./mock-workspace";
import { screens, screensByArea } from "./screen-catalog";

export type PortalPreview = {
  token: string;
  state: "valid" | "expired" | "revoked" | "used";
  title: string;
  summary: string;
  requestedBy: string;
  dueLabel: string;
  allowedActions: string[];
  guardRails: string[];
  expectedRound: number;
};

export type WorkspaceRequestContext = {
  tenantId?: string;
  signal?: AbortSignal;
};

/** Porta assíncrona consumida pela UI, independente de fixture, MSW ou HTTP. */
export interface WorkspaceTransport {
  getWorkspace(context?: WorkspaceRequestContext): Promise<unknown>;
  getPortal(token: string, context?: WorkspaceRequestContext): Promise<unknown>;
}

export type WorkspaceService = {
  getWorkspaceData(context?: WorkspaceRequestContext): Promise<WorkspaceSnapshot>;
  getPortalPreview(token: string, context?: WorkspaceRequestContext): Promise<PortalPreview>;
};

function portalFixture(token: string): PortalPreview {
  const state = token === "expired" || token === "used" || token === "revoked" ? token : "valid";
  return {
    token,
    state,
    title: "Revisao externa de entrega",
    summary: "Experiencia isolada para visualizar a entrega compartilhada, comentar e registrar uma decisao no escopo do link.",
    requestedBy: "Camila Moura",
    dueLabel: "Prazo de resposta: hoje, 18:00",
    allowedActions: ["Visualizar artefato e diff principal", "Adicionar comentarios externos auditaveis", "Aprovar, rejeitar ou solicitar alteracoes"],
    guardRails: ["Token opaco e escopado ao item compartilhado", "Sem shell interno, membros, analytics ou busca global", "Sem revelar recursos fora do tenant ou da entrega"]
    ,expectedRound: 1
  };
}

export function createMockWorkspaceTransport(): WorkspaceTransport {
  return {
    getWorkspace: () => Promise.resolve(structuredClone(getWorkspaceSnapshot())),
    getPortal: (token) => Promise.resolve(portalFixture(token))
  };
}

type HttpTransportOptions = {
  baseUrl: string;
  fetch?: typeof globalThis.fetch;
  headers?: HeadersInit | (() => HeadersInit | Promise<HeadersInit>);
};

export function createHttpWorkspaceTransport(options: HttpTransportOptions): WorkspaceTransport {
  const baseUrl = options.baseUrl.endsWith("/") ? options.baseUrl : `${options.baseUrl}/`;
  const request = async (path: string, context?: WorkspaceRequestContext): Promise<unknown> => {
    const fetcher = options.fetch ?? globalThis.fetch;
    const configuredHeaders = typeof options.headers === "function" ? await options.headers() : options.headers;
    const headers = new Headers(configuredHeaders);
    headers.set("accept", "application/json");
    if (context?.tenantId) headers.set("x-tenant-id", context.tenantId);
    const init: RequestInit = { headers };
    if (context?.signal) init.signal = context.signal;
    const response = await fetcher(new URL(path.replace(/^\/+/, ""), baseUrl), init);
    if (!response.ok) throw new Error(`Workspace API request failed (${response.status})`);
    return response.json();
  };
  return {
    getWorkspace: (context) => request("/workspace", context),
    getPortal: (token, context) => request(`/portal/${encodeURIComponent(token)}`, context)
  };
}

export type AuthenticatedWorkspaceOptions = {
  baseUrl: string;
  getAccessToken: () => Promise<string>;
  organizationId?: string;
  fetch?: typeof globalThis.fetch;
};

export class WorkspaceHttpError extends Error {
  constructor(public readonly status: number, path: string) {
    super(`Real workspace API ${path} failed (${status})`);
  }
}

function array(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object") : [];
}

function scalar(value: unknown, fallback: string): string {
  return typeof value === "string" || typeof value === "number" || typeof value === "boolean"
    ? String(value)
    : fallback;
}

function feed(items: Record<string, unknown>[], fallback: string) {
  return items.slice(0, 6).map((item, index) => ({
    title: scalar(item.title ?? item.name ?? item.code, `${fallback} ${index + 1}`),
    description: scalar(item.description ?? item.objective ?? item.status, "Registro carregado do backend real"),
    meta: scalar(item.status ?? item.role ?? item.riskLevel, "API real")
  }));
}

/** Adapter HTTP autenticado. Credenciais nunca fazem parte desta fronteira. */
export function createAuthenticatedWorkspaceTransport(options: AuthenticatedWorkspaceOptions): WorkspaceTransport {
  const fetcher = options.fetch ?? globalThis.fetch;
  const call = async (path: string, init: RequestInit = {}) => {
    const response = await fetcher(`${options.baseUrl.replace(/\/$/, "")}${path}`, {
      ...init,
      cache: "no-store",
      headers: { accept: "application/json", ...init.headers }
    });
    if (!response.ok) throw new WorkspaceHttpError(response.status, path);
    return response.json() as Promise<Record<string, unknown>>;
  };
  const optionalForRole = async (path: string, headers: HeadersInit, forbiddenValue: Record<string, unknown>) => {
    try {
      return await call(path, { headers });
    } catch (error) {
      if (error instanceof WorkspaceHttpError && error.status === 403) return forbiddenValue;
      throw error;
    }
  };
  return {
    getWorkspace: async (context) => {
      const token = await options.getAccessToken();
      if (!token) throw new Error("Authenticated workspace requires an access token");
      const requestedOrganizationId = context?.tenantId ?? options.organizationId;
      const organizationHeaders = { authorization: `Bearer ${token}` };
      const organizations = await call("/v1/organizations", { headers: organizationHeaders });
      const organizationRows = array(organizations.organizations);
      const organizationId = requestedOrganizationId ?? scalar(organizationRows[0]?.id, "");
      if (!organizationId) throw new Error("Authenticated user has no organization membership");
      const authHeaders = {
        authorization: `Bearer ${token}`,
        "x-organization-id": organizationId
      };
      const [rooms, tasks, approvals, agents, documents, leads, experiments, analytics, audit] =
        await Promise.all([
          call("/v1/rooms", { headers: authHeaders }),
          call("/v1/tasks", { headers: authHeaders }),
          optionalForRole("/v1/approvals", authHeaders, { items: [] }),
          optionalForRole("/v1/agents", authHeaders, { items: [] }),
          call("/v1/knowledge/documents", { headers: authHeaders }),
          call("/v1/crm/leads", { headers: authHeaders }),
          optionalForRole("/v1/experiments", authHeaders, { items: [] }),
          optionalForRole("/v1/analytics/summary", authHeaders, { cards: [] }),
          optionalForRole("/v1/audit/events", authHeaders, { events: [] })
        ]);
      const names = organizationRows.map((item) => String(item.name));
      const current = organizationRows.find((item) => item.id === organizationId);
      const roomFeed = feed(array(rooms.rooms), "Sala");
      const taskFeed = feed(array(tasks.items), "Tarefa");
      const governanceFeed = feed(array(approvals.items), "Aprovacao");
      const automationFeed = feed(array(agents.items), "Agente");
      const knowledgeFeed = feed(array(documents.documents), "Documento");
      const commercialFeed = feed(array(leads.items), "Lead");
      const analyticsFeed = feed(array(analytics.cards), "Metrica");
      const adminFeed = feed(array(audit.events), "Auditoria");
      const roomRows = array(rooms.rooms);
      const taskRows = array(tasks.items);
      const approvalRows = array(approvals.items);
      const experimentRows = array(experiments.items);
      const toOptions = (items: Record<string, unknown>[], fallback: string) => items.map((item, index) => ({
        id: scalar(item.id, ""),
        name: scalar(item.title ?? item.name ?? item.objective, `${fallback} ${index + 1}`),
        status: scalar(item.status, ""),
        ...(typeof item.version === "number" ? { version: item.version } : {}),
        ...(typeof item.round === "number" ? { round: item.round } : {}),
        ...(typeof item.isPrivate === "boolean" ? { isPrivate: item.isPrivate } : {}),
        ...(typeof item.unreadCount === "number" ? { unreadCount: item.unreadCount } : {}),
        ...(typeof (item.updatedAt ?? item.updated_at) === "string" ? { updatedAt: String(item.updatedAt ?? item.updated_at) } : {})
      })).filter((item) => item.id);
      return {
        organizations: names,
        currentOrganization: scalar(current?.name, names[0] ?? organizationId),
        currentOrganizationId: organizationId,
        organizationOptions: toOptions(organizationRows, "Organizacao"),
        roomOptions: toOptions(roomRows, "Sala"),
        taskOptions: toOptions(taskRows, "Tarefa"),
        approvalOptions: toOptions(approvalRows, "Aprovacao"),
        experimentOptions: toOptions(experimentRows, "Experimento"),
        notifications: 0,
        commandShortcuts: ["Criar tarefa", "Abrir sala", "Revisar aprovacoes"],
        summaryCards: [
          { title: "Salas visiveis", value: String(roomFeed.length), detail: "FastAPI + RLS", tone: "accent" },
          { title: "Tarefas visiveis", value: String(taskFeed.length), detail: "PostgreSQL local" },
          { title: "Aprovacoes", value: String(governanceFeed.length), detail: "Tenant atual" }
        ],
        inboxItems: [...taskFeed, ...governanceFeed].slice(0, 6),
        accessMoments: feed(organizationRows, "Organizacao"),
        roomMoments: roomFeed,
        taskMoments: taskFeed,
        governanceMoments: governanceFeed,
        automationMoments: automationFeed,
        knowledgeMoments: knowledgeFeed,
        commercialMoments: commercialFeed,
        analyticsMoments: analyticsFeed,
        adminMoments: adminFeed,
        screens,
        areas: screensByArea
      } satisfies WorkspaceSnapshot;
    },
    getPortal: async (token) => call(`/v1/portal/items/${encodeURIComponent(token)}`)
  };
}

function object(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new TypeError(`Invalid ${label} payload`);
  return value as Record<string, unknown>;
}

function string(value: unknown, field: string): string {
  if (typeof value !== "string") throw new TypeError(`Invalid ${field}`);
  return value;
}

function strings(value: unknown, field: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) throw new TypeError(`Invalid ${field}`);
  return [...(value as string[])];
}

export function normalizeWorkspaceSnapshot(payload: unknown): WorkspaceSnapshot {
  const value = object(payload, "workspace");
  const organizations = strings(value.organizations, "organizations");
  const currentOrganization = string(value.currentOrganization, "currentOrganization");
  if (!organizations.includes(currentOrganization)) throw new TypeError("Current organization is outside the workspace");
  if (typeof value.notifications !== "number" || !Number.isSafeInteger(value.notifications) || value.notifications < 0) throw new TypeError("Invalid notifications");
  strings(value.commandShortcuts, "commandShortcuts");
  if (!value.areas || typeof value.areas !== "object" || !Array.isArray(value.screens)) throw new TypeError("Invalid workspace catalog");
  return structuredClone(value) as WorkspaceSnapshot;
}

export function normalizePortalPreview(payload: unknown): PortalPreview {
  const value = object(payload, "portal");
  const rawState = string(value.state, "state");
  const state = rawState === "pending" ? "valid" : rawState === "approved" || rawState === "changes_requested" || rawState === "rejected" ? "used" : rawState;
  if (!(["valid", "expired", "revoked", "used"] as const).includes(state as PortalPreview["state"])) throw new TypeError("Invalid portal state");
  if (value.item && typeof value.item === "object" && !Array.isArray(value.item)) {
    const item = value.item as Record<string, unknown>;
    const actions = strings(value.allowedActions, "allowedActions");
    return {
      token: typeof value.token === "string" ? value.token : "",
      state: state as PortalPreview["state"],
      title: string(item.title, "item.title"),
      summary: string(item.objective, "item.objective"),
      requestedBy: "Equipe BigHead",
      dueLabel: typeof item.expiresAt === "string" ? `Expira em ${item.expiresAt}` : "Prazo definido pela aprovacao",
      allowedActions: actions,
      guardRails: ["Link isolado do workspace interno", "Decisao idempotente e auditavel", "Token limitado a esta aprovacao"],
      expectedRound: typeof item.round === "number" ? item.round : 1
    };
  }
  return {
    token: string(value.token, "token"), state: state as PortalPreview["state"],
    title: string(value.title, "title"), summary: string(value.summary, "summary"),
    requestedBy: string(value.requestedBy, "requestedBy"), dueLabel: string(value.dueLabel, "dueLabel"),
    allowedActions: strings(value.allowedActions, "allowedActions"), guardRails: strings(value.guardRails, "guardRails"),
    expectedRound: typeof value.expectedRound === "number" ? value.expectedRound : 1
  };
}

export function createWorkspaceService(transport: WorkspaceTransport): WorkspaceService {
  return {
    getWorkspaceData: async (context) => normalizeWorkspaceSnapshot(await transport.getWorkspace(context)),
    getPortalPreview: async (token, context) => normalizePortalPreview(await transport.getPortal(token, context))
  };
}

/** Fixture explícita para testes unitários e o catálogo local. */
export const fixtureWorkspaceService = createWorkspaceService(createMockWorkspaceTransport());
