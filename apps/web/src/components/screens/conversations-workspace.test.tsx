import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { push, roomId } = vi.hoisted(() => ({ push: vi.fn(), roomId: { value: "" } }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(roomId.value ? { roomId: roomId.value } : {})
}));

import { ConversationsWorkspace } from "./conversations-workspace";

const rooms = { rooms: [{ id: "room-7", name: "Operação comercial", description: "Decisões do time", isPrivate: true, createdAt: "2026-07-13T12:00:00Z" }], counters: { total: 1 }, nextCursor: null };
const roomPage = { messages: [{ id: "message-1", roomId: "room-7", authorUserId: "user-1", body: "Contexto confirmado", metadata: {}, createdAt: "2026-07-13T12:05:00Z" }], roomContext: rooms.rooms[0], nextCursor: null };
let roomBStatus = 200;
let fileStatus = 200;
let activeRoomPage = roomPage;

function requestUrl(input: RequestInfo | URL) {
  return typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
}

function requestBody(init?: RequestInit) {
  return typeof init?.body === "string" ? init.body : "";
}

function routeFetch(input: RequestInfo | URL, init?: RequestInit) {
  const url = requestUrl(input);
  if (url === "/api/rooms" && init?.method === "POST") return Promise.resolve(Response.json(rooms.rooms[0], { status: 201 }));
  if (url === "/api/rooms") return Promise.resolve(Response.json(rooms));
  if (url.endsWith("/messages") && init?.method === "POST") {
    const payload = JSON.parse(requestBody(init)) as { body: string; clientId: string };
    return Promise.resolve(Response.json({ id: "message-2", roomId: "room-7", clientId: payload.clientId, authorUserId: "user-1", body: payload.body, metadata: { client_id: payload.clientId }, createdAt: "2026-07-13T12:06:00Z" }, { status: 201 }));
  }
  if (url.includes("room-b/messages") && roomBStatus !== 200) return Promise.resolve(Response.json({ detail: "Acesso negado." }, { status: roomBStatus }));
  if (url.endsWith("/messages")) return Promise.resolve(Response.json(activeRoomPage));
  if (url.endsWith("/files") && fileStatus !== 200) return Promise.resolve(Response.json({ detail: "Arquivos indisponiveis." }, { status: fileStatus }));
  if (url.endsWith("/files")) return Promise.resolve(Response.json({ files: [{ id: "file-1", name: "proposta.pdf", kind: "document", quarantineStatus: "clean", createdAt: "2026-07-13T12:00:00Z" }] }));
  if (url.endsWith("/members")) return Promise.resolve(Response.json({ room: rooms.rooms[0], members: [{ userId: "user-1", isModerator: true }] }));
  if (url.startsWith("/api/tasks?roomId=")) return Promise.resolve(Response.json({ items: [{ id: "task-1", title: "Revisar proposta", status: "in_progress" }], nextCursor: null }));
  return Promise.reject(new Error(`Unexpected request: ${url}`));
}

describe("ConversationsWorkspace", () => {
  beforeEach(() => {
    roomId.value = "";
    push.mockClear();
    localStorage.clear();
    roomBStatus = 200;
    fileStatus = 200;
    activeRoomPage = roomPage;
    vi.stubGlobal("fetch", vi.fn(routeFetch));
    Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("lists real rooms and opens the selected roomId", async () => {
    render(<ConversationsWorkspace mode="list" />);
    const link = await screen.findByRole("link", { name: /Operação comercial/ });
    expect(link).toHaveAttribute("href", "/colaboracao/sala?roomId=room-7");
    expect(screen.getByText("1 salas")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/fixture|T10|endpoint|OpenAPI|catalogo/i);
  });

  it("uses the URL roomId, renders timeline context and reconciles an idempotent send", async () => {
    roomId.value = "room-7";
    render(<ConversationsWorkspace mode="room" />);
    expect(await screen.findByText("Contexto confirmado")).toBeTruthy();
    expect(screen.getByRole("log", { name: "Mensagens da sala" })).toBeTruthy();
    expect(screen.getByText("Membro")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Criar tarefa a partir da mensagem" })).toHaveAttribute(
      "href",
      "/tarefas/criar?roomId=room-7&sourceMessageId=message-1"
    );
    expect(screen.getByText("proposta.pdf")).toBeTruthy();
    expect(screen.getByText("user-1")).toBeTruthy();
    expect(screen.getByText("Moderador")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Revisar proposta/ })).toHaveAttribute("href", "/tarefas/detalhe?taskId=task-1");
    expect(vi.mocked(fetch)).toHaveBeenCalledWith("/api/tasks?roomId=room-7", { cache: "no-store" });
    expect(vi.mocked(fetch)).toHaveBeenCalledWith("/api/rooms/room-7/members", { cache: "no-store" });
    const draft = screen.getByRole("textbox", { name: "Mensagem" });
    fireEvent.change(draft, { target: { value: "Nova decisão" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(screen.getByText("Você")).toBeTruthy();
    expect(screen.queryByText(/Enter envia/i)).toBeNull();
    await waitFor(() => expect(screen.getAllByText("Nova decisão")).toHaveLength(1));
    const post = vi.mocked(fetch).mock.calls.find(([url, init]) => requestUrl(url).endsWith("/messages") && init?.method === "POST");
    const body = JSON.parse(requestBody(post?.[1])) as { clientId: string; body: string };
    expect(body.body).toBe("Nova decisão");
    expect(body.clientId).toBeTruthy();
    expect(localStorage.getItem("bighead:draft:room-7")).toBe("");
  });

  it("preserves the room draft and prevents sending while offline", async () => {
    roomId.value = "room-7";
    render(<ConversationsWorkspace mode="room" />);
    await screen.findByText("Contexto confirmado");
    const draft = screen.getByRole("textbox", { name: "Mensagem" });
    fireEvent.change(draft, { target: { value: "Continuar depois" } });
    expect(localStorage.getItem("bighead:draft:room-7")).toBe("Continuar depois");
    fireEvent(window, new Event("offline"));
    expect(screen.getByRole("button", { name: "Enviar" })).toBeDisabled();
    expect(screen.getByText(/rascunho salvo/i)).toBeTruthy();
  });

  it("refetches and deduplicates the authoritative timeline after Realtime", async () => {
    roomId.value = "room-7";
    render(<ConversationsWorkspace mode="room" />);
    await screen.findByText("Contexto confirmado");
    window.dispatchEvent(new CustomEvent("bighead:realtime-event", { detail: { id: "event-1", table: "messages", operation: "INSERT", entityId: "message-1", occurredAt: new Date().toISOString() } }));
    await waitFor(() => expect(vi.mocked(fetch).mock.calls.filter(([url]) => requestUrl(url).endsWith("/messages"))).toHaveLength(2));
    expect(screen.getAllByText("Contexto confirmado")).toHaveLength(1);
    expect(screen.getByText("Conversa atualizada com novas mensagens.")).toHaveAttribute("aria-live", "polite");
    expect(document.querySelectorAll("[aria-live]")).toHaveLength(1);
  });

  it("clears room A before showing a denied room B", async () => {
    roomId.value = "room-7";
    const view = render(<ConversationsWorkspace mode="room" />);
    await screen.findByText("Contexto confirmado");
    expect(screen.getByText("proposta.pdf")).toBeTruthy();
    roomBStatus = 403;
    roomId.value = "room-b";
    view.rerender(<ConversationsWorkspace mode="room" />);
    await screen.findByText("Conversa indisponivel");
    expect(screen.queryByText("Contexto confirmado")).toBeNull();
    expect(screen.queryByText("proposta.pdf")).toBeNull();
    expect(screen.queryByText("Comece a conversa")).toBeNull();
  });

  it.each([
    [403, "Voce nao tem permissao para ver os arquivos desta sala."],
    [503, "Arquivos temporariamente indisponiveis."]
  ])("shows an explicit file state for HTTP %i", async (statusCode, expected) => {
    roomId.value = "room-7";
    fileStatus = statusCode;
    render(<ConversationsWorkspace mode="room" />);
    expect(await screen.findByText(expected)).toBeTruthy();
    expect(screen.queryByText("Nenhum arquivo nesta sala.")).toBeNull();
  });

  it("performs an authoritative online refetch without losing the draft", async () => {
    roomId.value = "room-7";
    render(<ConversationsWorkspace mode="room" />);
    await screen.findByText("Contexto confirmado");
    const draft = screen.getByRole("textbox", { name: "Mensagem" });
    fireEvent.change(draft, { target: { value: "Rascunho preservado" } });
    fireEvent(window, new Event("offline"));
    const firstMessage = roomPage.messages[0]!;
    activeRoomPage = { ...roomPage, messages: [firstMessage, { ...firstMessage, id: "message-2", body: "Chegou online" }] };
    fireEvent(window, new Event("online"));
    await screen.findByText("Chegou online");
    expect(draft).toHaveValue("Rascunho preservado");
    expect(screen.getAllByText("Contexto confirmado")).toHaveLength(1);
  });
});
