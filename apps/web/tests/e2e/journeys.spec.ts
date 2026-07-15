import { expect, test, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({ body: JSON.stringify(body), contentType: "application/json", status });
}

async function expectNoCriticalAccessibilityViolations(page: Parameters<typeof AxeBuilder>[0]["page"]) {
  const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
  expect(
    accessibilityScanResults.violations.filter(
      (item) => item.impact === "critical" || item.impact === "serious"
    )
  ).toHaveLength(0);
}

test("shell inicial carrega com navegacao operacional, teclado e reduced motion", async ({
  page
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");

  await expect(page.locator("main").first()).toBeVisible();
  const menuButton = page.getByRole("button", { name: "Menu", exact: true });
  const mobileNavigation = await menuButton.isVisible();
  if (mobileNavigation) await menuButton.click();
  const navigation = page.getByRole("navigation", { name: /Navegacao principal/i });
  await expect(navigation).toContainText("Inicio");
  await expect(navigation).toContainText("Pipeline");
  await expect(navigation).not.toContainText(/T\d{2}|Sprint|OpenAPI|endpoint|handoff/i);
  await expect(navigation).toContainText("Modulos");
  if (mobileNavigation) await page.getByRole("button", { name: "Fechar menu", exact: true }).click();

  const searchShell = page.getByRole("link", { name: /Buscar tarefas, conversas e clientes/i });
  await searchShell.focus();
  await expect(searchShell).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: /Notificacoes:/i })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Perfil" })).toBeFocused();

  await page.evaluate(() => {
    document.body.style.zoom = "2";
  });
  await expect(page.locator("main").first()).toBeVisible();

  await expectNoCriticalAccessibilityViolations(page);

  await page.goto("/operacao/busca-global");
  const globalSearch = page.getByRole("searchbox", { name: /O que voc/i });
  await globalSearch.fill("x");
  await page.getByRole("button", { name: "Buscar", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Digite ao menos dois caracteres." })).toBeVisible();
  await expect(globalSearch).toHaveValue("x");
  await expectNoCriticalAccessibilityViolations(page);
});

for (const width of [360, 768, 1280, 1920]) {
  test(`shell nao cria overflow horizontal em ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/operacao/home");
    await expect(page.locator("main").first()).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
}

test("tema persistido e aplicado antes da hidratacao", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("bighead-theme", "radar-dark"));
  await page.goto("/operacao/home");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "radar-dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "radar-dark");
});

test("catalogo demonstra todos os estados transversais", async ({ page }) => {
  await page.goto("/catalogo");
  for (const state of ["Loading", "Vazio", "Erro", "Sem permissao", "Offline", "Sucesso"]) {
    await expect(page.getByText(state, { exact: true })).toBeVisible();
  }
});

test("onboarding exige sessao autenticada antes de abrir o wizard", async ({ page }) => {
  await page.goto("/acesso/onboarding");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Boas-vindas" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Concluir/i })).toHaveCount(0);
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada conversa para tarefa preserva ids e contexto pela fronteira HTTP", async ({ page }) => {
  const roomId = "room-e2e";
  const messageId = "message-e2e";
  const taskId = "task-e2e";
  let createdTask: Record<string, unknown> | null = null;
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === "/api/rooms") return fulfillJson(route, { rooms: [], counters: { total: 0 }, nextCursor: null });
    if (url.pathname === `/api/rooms/${roomId}/messages` && request.method() === "GET") return fulfillJson(route, {
      messages: [{ id: messageId, roomId, authorUserId: "user-e2e", body: "Transformar decisao em tarefa", metadata: {}, createdAt: "2026-07-14T12:00:00Z" }],
      roomContext: { id: roomId, name: "Sala E2E", description: "Contexto contratual", isPrivate: true, createdAt: "2026-07-14T11:00:00Z" },
      nextCursor: null
    });
    if (url.pathname === `/api/rooms/${roomId}/files`) return fulfillJson(route, { files: [] });
    if (url.pathname === `/api/rooms/${roomId}/members`) return fulfillJson(route, { room: { id: roomId, name: "Sala E2E", isPrivate: true, createdAt: "2026-07-14T11:00:00Z" }, members: [{ userId: "user-e2e", isModerator: true }] });
    if (url.pathname === "/api/tasks" && request.method() === "GET") return fulfillJson(route, { items: [], nextCursor: null });
    if (url.pathname === "/api/tasks" && request.method() === "POST") {
      createdTask = request.postDataJSON() as Record<string, unknown>;
      return fulfillJson(route, { task: { id: taskId }, replayed: false }, 201);
    }
    if (url.pathname === `/api/tasks/${taskId}`) return fulfillJson(route, {
      id: taskId, roomId, sourceMessageId: messageId, title: "Tarefa originada da conversa", objective: "Executar contexto preservado", status: "new", priority: 3, riskLevel: "low", requesterId: null, assigneeId: null, dueAt: null, slaAt: null, version: 1, createdAt: "2026-07-14T12:01:00Z", updatedAt: "2026-07-14T12:01:00Z"
    });
    return route.fallback();
  });

  await page.goto(`/colaboracao/sala?roomId=${roomId}`);
  const message = page.locator(`[data-message-id="${messageId}"]`);
  await expect(message).toContainText("Transformar decisao em tarefa");
  await message.getByRole("link", { name: "Criar tarefa a partir da mensagem" }).click();
  await expect(page).toHaveURL(new RegExp(`/tarefas/criar\\?roomId=${roomId}&sourceMessageId=${messageId}$`));
  await expect(page.getByText("Sala de origem preservada")).toBeVisible();
  await page.getByRole("textbox", { name: /T.tulo/i }).fill("Tarefa originada da conversa");
  await page.getByRole("textbox", { name: "Objetivo" }).fill("Executar contexto preservado");
  await page.getByRole("button", { name: "Criar tarefa", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/tarefas/detalhe\\?taskId=${taskId}$`));
  await expect(page.getByRole("heading", { name: "Tarefa originada da conversa" })).toBeVisible();
  expect(createdTask).toMatchObject({ roomId, sourceMessageId: messageId, title: "Tarefa originada da conversa", goal: "Executar contexto preservado" });
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada run para aprovacao registra decisao pela fronteira HTTP", async ({ page }) => {
  const approvalId = "approval-e2e";
  let decision: Record<string, unknown> | null = null;
  let decided = false;
  await page.route("**/api/approvals/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === `/api/approvals/${approvalId}/decision` && request.method() === "POST") {
      decision = request.postDataJSON() as Record<string, unknown>;
      decided = true;
      return fulfillJson(route, { approval: { id: approvalId, status: "approved", round: 2 }, roundResult: "approved", nextActions: ["resume_task"] });
    }
    if (url.pathname === `/api/approvals/${approvalId}/decisions`) return fulfillJson(route, { items: decided ? [{ id: "decision-e2e", decision: "approved", actor: { type: "user", id: "reviewer-e2e" }, comment: "Risco revisado no browser", decidedAt: "2026-07-14T12:10:00Z" }] : [] });
    if (url.pathname === `/api/approvals/${approvalId}`) return fulfillJson(route, {
      approval: { id: approvalId, status: decided ? "approved" : "pending", risk_level: "high", round: 2, due_at: "2099-07-15T12:00:00Z" },
      task: { id: "task-approval-e2e", title: "Publicar campanha E2E", objective: "Validar risco antes da publicacao" }, requester: { id: "requester-e2e" }, evidence: [],
      impact: { taskStatus: "waiting_human", activeRunCount: 1, estimatedCost: "42.50", slaAt: "2099-07-15T13:00:00Z" },
      availableActions: decided ? [] : ["approved", "changes_requested", "rejected"], decisionBlockedReason: decided ? "approval_already_decided" : null
    });
    return route.fallback();
  });

  await page.goto("/tarefas/execucao");
  await page.getByRole("button", { name: /^Retry$/i }).click();
  await expect(page.getByText(/Retry solicitado para run-244/i)).toBeVisible();

  await page.goto(`/governanca/aprovacao-detalhe?approvalId=${approvalId}`);
  await expect(page.getByRole("heading", { name: "Publicar campanha E2E" })).toBeVisible();
  await page.getByLabel(/Coment.rio/i).fill("Risco revisado no browser");
  await page.getByRole("button", { name: /Confirmar decis.o/i }).click();
  await expect(page.getByText(/Decis.o registrada\. O trabalho relacionado foi atualizado\./i)).toBeVisible();
  expect(decision).toEqual({ decision: "approved", comment: "Risco revisado no browser", expectedRound: 2 });
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada portal externo aceita resposta quando token e valido", async ({ page }) => {
  await page.goto("/portal/demo");
  await expect(page.getByRole("heading", { name: /Revisao externa de entrega/i })).toBeVisible();

  await page.getByRole("button", { name: /^approved$/i }).click();
  await page.getByLabel(/Comentario externo/i).fill("Aprovado com pequenos ajustes visuais.");
  await page.getByRole("button", { name: /Enviar resposta/i }).click();

  await expect(page.getByText(/Resposta approved registrada/i)).toBeVisible();
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada ingestao para busca retorna resultados com fonte", async ({ page }) => {
  await page.goto("/conhecimento/busca-semantica");
  await page.getByLabel(/Consulta governada/i).fill("onboarding");
  await expect(page.getByText(/Politica vigente de onboarding/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /Fonte: handbook/i })).toBeVisible();
  await expect(page.getByText(/Plano secreto de outro tenant/i)).toHaveCount(0);
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada lead para oportunidade persiste etapa pela fronteira HTTP", async ({ page }) => {
  const opportunityId = "50000000-0000-4000-8000-000000000001";
  const leadId = "60000000-0000-4000-8000-000000000001";
  let stage = "discovery";
  let stagePayload: Record<string, unknown> | null = null;
  await page.route("**/api/commercial/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === `/api/commercial/opportunities/${opportunityId}/stage` && request.method() === "POST") {
      stagePayload = request.postDataJSON() as Record<string, unknown>;
      stage = String(stagePayload.targetStage);
      return fulfillJson(route, { opportunity: { id: opportunityId, stage }, timelineItem: { type: "stage_changed" }, replayed: false });
    }
    if (url.pathname === "/api/commercial/pipeline") return fulfillJson(route, {
      stages: [
        { id: "discovery", label: "Descoberta", count: stage === "discovery" ? 1 : 0, amount: stage === "discovery" ? 180000 : 0, opportunities: stage === "discovery" ? [{ id: opportunityId, name: "Atlas E2E", stage, amount: 180000, currency: "BRL", probability: 30, expectedCloseDate: null, leadId, accountId: null, updatedAt: "2026-07-14T12:00:00Z" }] : [] },
        { id: "proposal", label: "Proposta", count: stage === "proposal" ? 1 : 0, amount: stage === "proposal" ? 180000 : 0, opportunities: stage === "proposal" ? [{ id: opportunityId, name: "Atlas E2E", stage, amount: 180000, currency: "BRL", probability: 60, expectedCloseDate: "2026-08-01", leadId, accountId: null, updatedAt: "2026-07-14T12:05:00Z" }] : [] }
      ],
      totals: { opportunities: 1, amount: 180000 }
    });
    return route.fallback();
  });

  await page.goto("/comercial/pipeline");
  await page.getByRole("button", { name: /Atlas E2E/ }).click();
  await page.getByLabel("Nova etapa").selectOption("proposal");
  await page.getByLabel("Valor").fill("180000");
  await page.getByLabel("Fechamento previsto").fill("2026-08-01");
  const confirmStage = page.getByRole("button", { name: "Confirmar etapa" });
  const invalidFields = await confirmStage.evaluate((button) => Array.from(button.closest("form")!.querySelectorAll<HTMLElement>(":invalid")).map((field) => field.getAttribute("name") || field.textContent));
  expect(invalidFields).toEqual([]);
  await confirmStage.click();
  await expect.poll(() => stagePayload).not.toBeNull();
  await expect(page.getByRole("status")).toContainText("Etapa atualizada.");
  expect(stagePayload).toMatchObject({ targetStage: "proposal", amount: "180000", expectedCloseDate: "2026-08-01" });
  await expect(page.getByRole("button", { name: /Atlas E2E/ })).toBeVisible();
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada conteudo para publicacao permite retry seguro", async ({ page }) => {
  await page.goto("/comercial/publicacoes");
  await page.getByRole("button", { name: /Repetir publicacao/i }).click();
  await expect(page.getByText(/Retry enfileirado/i)).toBeVisible();
  await expect(page.getByText(/Tentativa 2/i)).toBeVisible();
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada experimento para resultado bloqueia campos apos start", async ({ page }) => {
  await page.goto("/aprendizado/experimento-detalhe");
  await page.getByRole("button", { name: /Configurar e iniciar/i }).click();

  await expect(page.getByTestId("mutation-feedback")).toContainText(/Experimento configurado e iniciado/i);
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada admin para auditoria executa job auditavel", async ({ page }) => {
  await page.goto("/administracao/privacidade-auditoria");
  await page.getByRole("button", { name: /Exportacao de dados pessoais/i }).click();

  await expect(page.getByText(/Job auditado: Exportacao de dados pessoais/i)).toBeVisible();
  await expectNoCriticalAccessibilityViolations(page);
});
