import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { params, push, transitionTask } = vi.hoisted(() => ({
  params: { value: new URLSearchParams() }, push: vi.fn(), transitionTask: vi.fn()
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }), useSearchParams: () => params.value }));
vi.mock("@/lib/transition-task-client", () => ({ transitionTask }));

import { TasksWorkspace } from "./tasks-workspace";

const firstId = "11111111-1111-4111-8111-111111111111";
const targetId = "22222222-2222-4222-8222-222222222222";
const task = (id: string, title: string, status = "new", version = 1) => ({
  id, roomId: "33333333-3333-4333-8333-333333333333", sourceMessageId: "44444444-4444-4444-8444-444444444444",
  title, objective: `Objetivo ${title}`, status, priority: 3, riskLevel: "high", requesterId: null, assigneeId: null,
  dueAt: null, slaAt: null, version, createdAt: "2026-07-13T12:00:00Z", updatedAt: "2026-07-13T12:00:00Z"
});
let items = [task(firstId, "Primeira"), task(targetId, "Selecionada")];
let getStatus = 200;

function mockFetch(input: RequestInfo | URL, init?: RequestInit) {
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  if (url.startsWith("/api/tasks") && init?.method === "POST") return Promise.resolve(Response.json({ task: task(targetId, "Criada"), replayed: false }, { status: 201 }));
  if (url.startsWith("/api/tasks") && getStatus !== 200) return Promise.resolve(Response.json({ detail: `Falha ${getStatus}` }, { status: getStatus }));
  if (url === `/api/tasks/${targetId}`) return Promise.resolve(Response.json(items.find((item) => item.id === targetId)));
  if (url.startsWith("/api/tasks")) return Promise.resolve(Response.json({ items, nextCursor: null }));
  return Promise.reject(new Error(`Unexpected ${url}`));
}

describe("TasksWorkspace", () => {
  beforeEach(() => {
    params.value = new URLSearchParams();
    push.mockClear();
    transitionTask.mockReset();
    items = [task(firstId, "Primeira"), task(targetId, "Selecionada")];
    getStatus = 200;
    Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
    vi.stubGlobal("fetch", vi.fn(mockFetch));
  });

  it("applies status, owner, risk and SLA filters supported by the contract", async () => {
    render(<TasksWorkspace mode="inbox" />);
    await screen.findByText("Primeira");
    fireEvent.change(screen.getByRole("combobox", { name: "Estado" }), { target: { value: "triaged" } });
    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      "/api/tasks?status=triaged",
      expect.objectContaining({ cache: "no-store" })
    ));
    const filteredRequest = vi.mocked(fetch).mock.calls.find(([input]) => input === "/api/tasks?status=triaged");
    expect(filteredRequest?.[1]?.signal).toBeInstanceOf(AbortSignal);
    fireEvent.change(screen.getByRole("textbox", { name: "Responsável" }), { target: { value: "user-7" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Risco" }), { target: { value: "high" } });
    fireEvent.change(screen.getByRole("combobox", { name: "SLA" }), { target: { value: "overdue" } });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      "/api/tasks?status=triaged&ownerId=user-7&risk=high&slaStatus=overdue",
      expect.objectContaining({ cache: "no-store" })
    ));
  });

  it("creates with roomId and sourceMessageId from the URL", async () => {
    params.value = new URLSearchParams({ roomId: "33333333-3333-4333-8333-333333333333", sourceMessageId: "44444444-4444-4444-8444-444444444444" });
    render(<TasksWorkspace mode="create" />);
    fireEvent.change(screen.getByRole("textbox", { name: "Objetivo" }), { target: { value: "Executar contexto" } });
    fireEvent.change(screen.getByLabelText("SLA opcional (horário local)"), { target: { value: "2026-07-14T09:30" } });
    fireEvent.click(screen.getByRole("button", { name: "Criar tarefa" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith(`/tarefas/detalhe?taskId=${targetId}`));
    const post = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === "POST");
    const body = JSON.parse(typeof post?.[1]?.body === "string" ? post[1].body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({ roomId: "33333333-3333-4333-8333-333333333333", sourceMessageId: "44444444-4444-4444-8444-444444444444", goal: "Executar contexto", slaAt: new Date("2026-07-14T09:30").toISOString() });
    expect(new Headers(post?.[1]?.headers).get("idempotency-key")).toBeTruthy();
    expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method !== "POST")).toHaveLength(0);
  });

  it("selects the exact taskId instead of the first task", async () => {
    params.value = new URLSearchParams({ taskId: targetId });
    render(<TasksWorkspace mode="detail" />);
    expect(await screen.findByRole("heading", { name: "Selecionada" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Primeira" })).toBeNull();
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(`/api/tasks/${targetId}`, expect.objectContaining({ cache: "no-store" }));
    expect(screen.getByRole("link", { name: "Abrir conversa de origem" })).toHaveAttribute("href", "/colaboracao/sala?roomId=33333333-3333-4333-8333-333333333333&messageId=44444444-4444-4444-8444-444444444444");
  });

  it("preserves the reason on 409 and offers an authoritative reload", async () => {
    params.value = new URLSearchParams({ taskId: targetId });
    transitionTask.mockResolvedValue({ ok: false, status: 409, message: "O registro mudou." });
    render(<TasksWorkspace mode="detail" />);
    await screen.findByRole("heading", { name: "Selecionada" });
    const reason = screen.getByRole("textbox", { name: "Motivo" });
    fireEvent.change(reason, { target: { value: "Contexto que não pode sumir" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar alteração" }));
    expect(await screen.findByRole("button", { name: "Recarregar tarefa" })).toBeTruthy();
    expect(reason).toHaveValue("Contexto que não pode sumir");
    const before = vi.mocked(fetch).mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Recarregar tarefa" }));
    await waitFor(() => expect(vi.mocked(fetch).mock.calls.length).toBeGreaterThan(before));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Recarregar tarefa" })).toBeNull());
    expect(reason).toHaveValue("Contexto que não pode sumir");
  });

  it("preserves the conflict reason when reload fails and later succeeds", async () => {
    params.value = new URLSearchParams({ taskId: targetId });
    transitionTask.mockResolvedValue({ ok: false, status: 409, message: "O registro mudou." });
    render(<TasksWorkspace mode="detail" />);
    await screen.findByRole("heading", { name: "Selecionada" });
    fireEvent.change(screen.getByRole("textbox", { name: "Motivo" }), { target: { value: "Motivo preservado" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar alteração" }));
    await screen.findByRole("button", { name: "Recarregar tarefa" });
    getStatus = 500;
    fireEvent.click(screen.getByRole("button", { name: "Recarregar tarefa" }));
    await screen.findByText("Tarefas indisponíveis");
    getStatus = 200;
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    await screen.findByRole("heading", { name: "Selecionada" });
    expect(screen.getByRole("textbox", { name: "Motivo" })).toHaveValue("Motivo preservado");
    expect(screen.queryByRole("button", { name: "Recarregar tarefa" })).toBeNull();
  });

  it.each([
    [403, true, "Acesso negado"],
    [500, true, "Tarefas indisponíveis"],
    [500, false, "Você está offline"]
  ])("shows an explicit detail load failure for HTTP %i online=%s", async (statusCode, online, heading) => {
    params.value = new URLSearchParams({ taskId: targetId });
    getStatus = statusCode;
    Object.defineProperty(navigator, "onLine", { configurable: true, value: online });
    render(<TasksWorkspace mode="detail" />);
    expect(await screen.findByText(heading)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Tentar novamente" })).toBeTruthy();
    expect(screen.queryByText("Tarefa não encontrada")).toBeNull();
  });

  it("ignores a stale response during rapid status filtering", async () => {
    render(<TasksWorkspace mode="inbox" />);
    await screen.findByText("Primeira");
    let resolveTriaged!: (value: Response) => void;
    let resolveDone!: (value: Response) => void;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("status=triaged")) return new Promise<Response>((resolve) => { resolveTriaged = resolve; });
      if (url.includes("status=done")) return new Promise<Response>((resolve) => { resolveDone = resolve; });
      return Promise.resolve(Response.json({ items: [], nextCursor: null }));
    }));
    const select = screen.getByRole("combobox", { name: "Estado" });
    fireEvent.change(select, { target: { value: "triaged" } });
    await waitFor(() => expect(resolveTriaged).toBeTypeOf("function"));
    fireEvent.change(select, { target: { value: "done" } });
    await waitFor(() => expect(resolveDone).toBeTypeOf("function"));
    resolveDone(Response.json({ items: [task(targetId, "Resposta nova", "done")], nextCursor: null }));
    await screen.findByText("Resposta nova");
    resolveTriaged(Response.json({ items: [task(firstId, "Resposta antiga", "triaged")], nextCursor: null }));
    await Promise.resolve();
    expect(screen.queryByText("Resposta antiga")).toBeNull();
    expect(screen.getByText("Resposta nova")).toBeTruthy();
  });

  it("reconciles the inbox after a task Realtime event", async () => {
    render(<TasksWorkspace mode="inbox" />);
    await screen.findByText("Primeira");
    const realtimeTask = task("55555555-5555-4555-8555-555555555555", "Chegou por Realtime");
    items = [realtimeTask, ...items];
    act(() => {
      window.dispatchEvent(new CustomEvent("bighead:realtime-event", {
        detail: {
          id: `2026-07-13T12:01:00Z:tasks:INSERT:${realtimeTask.id}:1`,
          table: "tasks",
          operation: "INSERT",
          entityId: realtimeTask.id,
          occurredAt: "2026-07-13T12:01:00Z"
        }
      }));
    });
    expect(await screen.findByText("Chegou por Realtime")).toBeTruthy();
    expect(vi.mocked(fetch).mock.calls.filter(([input]) => input === "/api/tasks").length).toBeGreaterThanOrEqual(2);
  });

  it("shows the persisted triaged state after reload", async () => {
    params.value = new URLSearchParams({ taskId: targetId });
    items = [task(targetId, "Selecionada", "triaged", 2)];
    render(<TasksWorkspace mode="detail" />);
    expect(await screen.findByText("Triada")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/fixture|T1[456]|OpenAPI|endpoint|catalogo/i);
  });
});
