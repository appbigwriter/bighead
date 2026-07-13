import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function expectNoCriticalAccessibilityViolations(page: Parameters<typeof AxeBuilder>[0]["page"]) {
  const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
  expect(
    accessibilityScanResults.violations.filter(
      (item) => item.impact === "critical" || item.impact === "serious"
    )
  ).toHaveLength(0);
}

test("shell inicial carrega com navegacao completa, teclado e reduced motion", async ({
  page
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /Home operacional/i })).toBeVisible();
  await expect(page.getByRole("navigation", { name: /Navegacao principal/i })).toContainText(
    "T56"
  );

  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();

  const interactiveCount = await page.locator("a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])").count();
  for (let index = 0; index < Math.min(interactiveCount, 40); index += 1) {
    await page.keyboard.press("Tab");
    await expect(page.locator(":focus")).toBeVisible();
  }

  await page.evaluate(() => {
    document.body.style.zoom = "2";
  });
  await expect(page.getByRole("heading", { name: /Home operacional/i })).toBeVisible();

  await expectNoCriticalAccessibilityViolations(page);

  await page.goto("/operacao/busca-global");
  const commandSearch = page.getByLabel("Pesquisar no command palette");
  await commandSearch.focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.locator('[data-command-index="0"]')).toBeFocused();
  await page.keyboard.press("Alt+1");
  await expect(page.getByText(/Atalho executado:/i)).toBeVisible();
  await expectNoCriticalAccessibilityViolations(page);
});

for (const width of [360, 768, 1280, 1920]) {
  test(`shell nao cria overflow horizontal em ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/operacao/home");
    await expect(page.getByRole("heading", { name: /Home operacional/i })).toBeVisible();
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

test("jornada onboarding conclui o wizard", async ({ page }) => {
  await page.goto("/acesso/onboarding");
  await expect(page.locator("h2", { hasText: "Onboarding" })).toBeVisible();

  await page.getByRole("button", { name: /Proximo/i }).click();
  await page.getByRole("button", { name: /Proximo/i }).click();
  await page.getByRole("button", { name: /Proximo/i }).click();
  await page.getByRole("button", { name: /Concluir/i }).click();

  await expect(page.getByText(/Onboarding concluido/i)).toBeVisible();
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada conversa para tarefa preserva contexto", async ({ page }) => {
  await page.goto("/colaboracao/sala");
  await expect(page.locator("h2", { hasText: "Sala conversacional" })).toBeVisible();

  await page.getByRole("button", { name: /^Criar tarefa a partir da mensagem$/i }).click();
  await expect(page.getByTestId("mutation-feedback")).toContainText(/Tarefa originada da conversa criada/i);
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada run para aprovacao executa retry e registra decisao", async ({ page }) => {
  await page.goto("/tarefas/execucao");
  await page.getByRole("button", { name: /^Retry$/i }).click();
  await expect(page.getByText(/Retry solicitado para run-244/i)).toBeVisible();

  await page.goto("/governanca/aprovacao-detalhe");
  await page.getByRole("combobox", { name: "Decisao" }).selectOption("changes_requested");
  await page.getByLabel(/^Comentario$/i).fill("Precisa ajustar o checklist final.");
  await page.getByRole("button", { name: /Registrar decisao/i }).click();

  await expect(page.getByTestId("mutation-feedback")).toContainText(/Decisao changes_requested registrada/i);
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

test("jornada lead para oportunidade aplica guard rails no pipeline", async ({ page }) => {
  await page.goto("/comercial/pipeline");
  await page.getByLabel(/Valor da oportunidade/i).fill("180000");
  await page.getByLabel(/Data de fechamento/i).fill("2026-08-01");
  await page.getByRole("button", { name: /Mover oportunidade/i }).click();
  await expect(page.getByText(/Movida para proposal/i)).toBeVisible();
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
