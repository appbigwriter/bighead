import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const navigation = vi.hoisted(() => ({
  params: new URLSearchParams(),
  push: vi.fn()
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => navigation.params,
  useRouter: () => ({ push: navigation.push })
}));

import { AgentsWorkspace } from "./agents-workspace";

const agentId = "11111111-1111-4111-8111-111111111111";
const agent = {
  id: agentId,
  name: "Agente SDR",
  slug: "agente-sdr",
  description: "Prospeccao",
  riskLevel: "high",
  trustScore: 88,
  isEnabled: true
};
const detail = (version = 1) => ({
  agent,
  confidence: 88,
  consumers: [],
  versions: [
    {
      id: `version-${version}`,
      version,
      modelId: null,
      systemPrompt: `Prompt ${version}`,
      configuration: { limits: { maxTokens: 1200 } }
    }
  ]
});
function requestBody(init?: RequestInit) {
  return typeof init?.body === "string" ? init.body : "{}";
}

describe("AgentsWorkspace", () => {
  beforeEach(() => {
    navigation.params = new URLSearchParams();
    navigation.push.mockClear();
    vi.restoreAllMocks();
  });

  it("lists agents and links to the exact id", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json({ items: [agent], counters: { total: 1 } })
        )
    );
    render(<AgentsWorkspace mode="catalog" />);
    expect(
      await screen.findByRole("link", { name: /Agente SDR/ })
    ).toHaveAttribute("href", `/automacao/agente-config?agentId=${agentId}`);
    expect(screen.getByText("88%")).toBeTruthy();
  });

  it("identifies an unconfigured agent as a draft instead of archived", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json({
            items: [{ ...agent, isEnabled: false, lifecycle: "draft" }]
          })
        )
    );
    render(<AgentsWorkspace mode="catalog" />);
    expect(await screen.findByText("Rascunho")).toBeTruthy();
  });

  it("creates and opens the returned agent", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "POST")
          return Promise.resolve(Response.json({ agent }, { status: 201 }));
        return Promise.resolve(Response.json({ items: [] }));
      })
    );
    render(<AgentsWorkspace mode="catalog" />);
    fireEvent.click(screen.getByRole("button", { name: "Criar agente" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Nome" }), {
      target: { value: "Agente SDR" }
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Slug" }), {
      target: { value: "agente-sdr" }
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Prompt inicial" }), {
      target: { value: "Prospecte contas" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Criar e configurar" }));
    await waitFor(() =>
      expect(navigation.push).toHaveBeenCalledWith(
        `/automacao/agente-config?agentId=${agentId}`
      )
    );
    const post = vi
      .mocked(fetch)
      .mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(requestBody(post?.[1]))).toMatchObject({
      name: "Agente SDR",
      slug: "agente-sdr",
      prompt: "Prospecte contas"
    });
  });

  it("loads the exact detail and persists a new version", async () => {
    navigation.params = new URLSearchParams({ agentId });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "PATCH")
          return Promise.resolve(Response.json(detail(2)));
        return Promise.resolve(Response.json(detail(1)));
      })
    );
    render(<AgentsWorkspace mode="detail" />);
    expect(
      await screen.findByRole("heading", { name: "Agente SDR" })
    ).toBeTruthy();
    const prompt = screen.getByRole("textbox", { name: "Prompt" });
    fireEvent.change(prompt, { target: { value: "Prompt 2" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar nova versao" }));
    expect(
      await screen.findByText("Agente atualizado e nova versao registrada.")
    ).toBeTruthy();
    expect(screen.getByText("Versao 2")).toBeTruthy();
    const patch = vi
      .mocked(fetch)
      .mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(JSON.parse(requestBody(patch?.[1]))).toMatchObject({
      prompt: "Prompt 2",
      expectedVersion: 1
    });
  });

  it("preserves the editor on conflict and archives after confirmation", async () => {
    navigation.params = new URLSearchParams({ agentId });
    let conflict = true;
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "PATCH" && conflict)
          return Promise.resolve(
            Response.json({ detail: "conflict" }, { status: 409 })
          );
        if (init?.method === "DELETE")
          return Promise.resolve(new Response(null, { status: 204 }));
        return Promise.resolve(Response.json(detail(1)));
      })
    );
    render(<AgentsWorkspace mode="detail" />);
    const prompt = await screen.findByRole("textbox", { name: "Prompt" });
    fireEvent.change(prompt, { target: { value: "Rascunho preservado" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar nova versao" }));
    expect(
      await screen.findByText(/mudou ou possui consumidores ativos/)
    ).toBeTruthy();
    expect(prompt).toHaveValue("Rascunho preservado");
    conflict = false;
    fireEvent.click(screen.getByRole("button", { name: "Arquivar agente" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Confirmar arquivamento" })
    );
    await waitFor(() =>
      expect(navigation.push).toHaveBeenCalledWith("/automacao/agentes")
    );
  });
});
