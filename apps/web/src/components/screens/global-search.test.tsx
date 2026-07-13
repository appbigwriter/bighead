import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GlobalSearch } from "./global-search";

describe("GlobalSearch", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("queries the real BFF boundary and links results using API identifiers", async () => {
    const fetcher = vi.fn().mockResolvedValue(Response.json({
      groups: [
        { scope: "tasks", items: [{ id: "task-42", title: "Revisar proposta", description: "Prazo hoje", status: "in_progress" }] },
        { scope: "rooms", items: [{ id: "room-7", title: "Operacao comercial" }] },
        { scope: "messages", items: [{ id: "message-9", roomId: "room-7", title: "Cliente aprovou o escopo" }] }
      ],
      shortcuts: [],
      removedCount: 0
    }));
    vi.stubGlobal("fetch", fetcher);
    render(<GlobalSearch />);

    fireEvent.change(screen.getByRole("searchbox", { name: "O que você procura?" }), { target: { value: "proposta" } });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));

    await waitFor(() => expect(screen.getByText("3 resultados")).toBeTruthy());
    expect(fetcher).toHaveBeenCalledWith("/api/search/global", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ query: "proposta", scopes: ["tasks", "rooms", "messages"] })
    }));
    expect(screen.getByRole("link", { name: /Revisar proposta/ })).toHaveAttribute("href", "/tarefas/detalhe?taskId=task-42");
    expect(screen.getByRole("link", { name: /Operacao comercial/ })).toHaveAttribute("href", "/colaboracao/sala?roomId=room-7");
    expect(screen.getByRole("link", { name: /Cliente aprovou o escopo/ })).toHaveAttribute("href", "/colaboracao/sala?roomId=room-7&messageId=message-9");
  });

  it("supports keyboard entry and cycling through result links", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({
      groups: [{ scope: "tasks", items: [{ id: "one", title: "Primeira" }, { id: "two", title: "Segunda" }] }],
      shortcuts: [], removedCount: 0
    })));
    render(<GlobalSearch />);
    const input = screen.getByRole("searchbox", { name: "O que você procura?" });
    fireEvent.change(input, { target: { value: "tarefa" } });
    fireEvent.submit(input.closest("form")!);
    const first = await screen.findByRole("link", { name: /Primeira/ });
    const second = screen.getByRole("link", { name: /Segunda/ });
    input.focus();
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(first).toHaveFocus();
    fireEvent.keyDown(first, { key: "ArrowDown" });
    expect(second).toHaveFocus();
    fireEvent.keyDown(second, { key: "ArrowDown" });
    expect(first).toHaveFocus();
  });

  it("preserves the query and offers retry after an API failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "Servico temporariamente indisponivel." }, { status: 503 })));
    render(<GlobalSearch />);
    const input = screen.getByRole("searchbox", { name: "O que você procura?" });
    fireEvent.change(input, { target: { value: "cliente" } });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Servico temporariamente indisponivel.");
    expect(input).toHaveValue("cliente");
    expect(screen.getByRole("button", { name: "Tentar novamente" })).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/T07|OpenAPI|fixture|endpoint|catalogo/i);
  });

  it("discards a slower response after a newer search starts", async () => {
    let resolveFirst!: (response: Response) => void;
    const first = new Promise<Response>((resolve) => { resolveFirst = resolve; });
    const fetcher = vi.fn()
      .mockReturnValueOnce(first)
      .mockResolvedValueOnce(Response.json({
        groups: [{ scope: "tasks", items: [{ id: "new", title: "Resultado novo" }] }]
      }));
    vi.stubGlobal("fetch", fetcher);
    render(<GlobalSearch />);
    const input = screen.getByRole("searchbox", { name: /O que/ });

    fireEvent.change(input, { target: { value: "antiga" } });
    fireEvent.submit(input.closest("form")!);
    fireEvent.change(input, { target: { value: "nova" } });
    fireEvent.submit(input.closest("form")!);

    expect(await screen.findByText("Resultado novo")).toBeTruthy();
    resolveFirst(Response.json({ groups: [{ scope: "tasks", items: [{ id: "old", title: "Resultado antigo" }] }] }));
    await waitFor(() => expect(screen.queryByText("Resultado antigo")).toBeNull());
  });
});
