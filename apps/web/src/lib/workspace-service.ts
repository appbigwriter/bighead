import { getWorkspaceSnapshot } from "./mock-workspace";
import type { WorkspaceSnapshot } from "./mock-workspace";

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
const defaultService = createWorkspaceService();
export const getWorkspaceData: WorkspaceService["getWorkspaceData"] = (context) => defaultService.getWorkspaceData(context);
export const getPortalPreview: WorkspaceService["getPortalPreview"] = (token, context) => defaultService.getPortalPreview(token, context);
