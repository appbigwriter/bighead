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

type RealWorkspaceOptions = {
  baseUrl: string;
  email: string;
  password: string;
  organizationId: string;
  fetch?: typeof globalThis.fetch;
};

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

/** Adapter SSR usado pelo E2E real. Nenhuma fixture participa dos dados operacionais. */
export function createRealWorkspaceTransport(options: RealWorkspaceOptions): WorkspaceTransport {
  const fetcher = options.fetch ?? globalThis.fetch;
  const call = async (path: string, init: RequestInit = {}) => {
    const response = await fetcher(`${options.baseUrl.replace(/\/$/, "")}${path}`, {
      ...init,
      cache: "no-store",
      headers: { accept: "application/json", ...init.headers }
    });
    if (!response.ok) throw new Error(`Real workspace API ${path} failed (${response.status})`);
    return response.json() as Promise<Record<string, unknown>>;
  };
  const authenticate = async () => {
    const result = await call("/v1/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email: options.email, passwordOrMagicLink: options.password })
    });
    const session = object(result.session, "real session");
    return string(session.accessToken, "accessToken");
  };
  return {
    getWorkspace: async (context) => {
      const token = await authenticate();
      const organizationId = context?.tenantId ?? options.organizationId;
      const authHeaders = {
        authorization: `Bearer ${token}`,
        "x-organization-id": organizationId
      };
      const [organizations, rooms, tasks, approvals, agents, documents, leads, analytics, audit] =
        await Promise.all([
          call("/v1/organizations", { headers: authHeaders }),
          call("/v1/rooms", { headers: authHeaders }),
          call("/v1/tasks", { headers: authHeaders }),
          call("/v1/approvals", { headers: authHeaders }),
          call("/v1/agents", { headers: authHeaders }),
          call("/v1/knowledge/documents", { headers: authHeaders }),
          call("/v1/crm/leads", { headers: authHeaders }),
          call("/v1/analytics/summary", { headers: authHeaders }),
          call("/v1/audit/events", { headers: authHeaders })
        ]);
      const organizationRows = array(organizations.organizations);
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
      return {
        organizations: names,
        currentOrganization: scalar(current?.name, names[0] ?? organizationId),
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
  const state = string(value.state, "state");
  if (!(["valid", "expired", "revoked", "used"] as const).includes(state as PortalPreview["state"])) throw new TypeError("Invalid portal state");
  return {
    token: string(value.token, "token"), state: state as PortalPreview["state"],
    title: string(value.title, "title"), summary: string(value.summary, "summary"),
    requestedBy: string(value.requestedBy, "requestedBy"), dueLabel: string(value.dueLabel, "dueLabel"),
    allowedActions: strings(value.allowedActions, "allowedActions"), guardRails: strings(value.guardRails, "guardRails")
  };
}

export function createWorkspaceService(transport: WorkspaceTransport = createMockWorkspaceTransport()): WorkspaceService {
  return {
    getWorkspaceData: async (context) => normalizeWorkspaceSnapshot(await transport.getWorkspace(context)),
    getPortalPreview: async (token, context) => normalizePortalPreview(await transport.getPortal(token, context))
  };
}

// Stateless default: every module call delegates to an immutable service instance.
const defaultService = process.env.BIGHEAD_WORKSPACE_MODE === "real"
  ? createWorkspaceService(createRealWorkspaceTransport({
      baseUrl: process.env.API_URL ?? "http://127.0.0.1:8010",
      email: process.env.BIGHEAD_E2E_EMAIL ?? "owner@atlas.bighead.dev",
      password: process.env.BIGHEAD_E2E_PASSWORD ?? "BigHeadLocalOnly!2026",
      organizationId: process.env.BIGHEAD_E2E_ORGANIZATION_ID ?? "a7100000-0000-0000-0000-000000000001"
    }))
  : createWorkspaceService();
export const getWorkspaceData: WorkspaceService["getWorkspaceData"] = (context) => defaultService.getWorkspaceData(context);
export const getPortalPreview: WorkspaceService["getPortalPreview"] = (token, context) => defaultService.getPortalPreview(token, context);
