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

  await page.evaluate(() => {
    document.body.style.zoom = "2";
  });
  await expect(page.getByRole("heading", { name: /Home operacional/i })).toBeVisible();

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

  await page.getByRole("button", { name: /Criar tarefa a partir da mensagem 8831/i }).first().click();

  await expect(page.getByText(/Mensagem convertida em tarefa/i)).toBeVisible();
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada run para aprovacao executa retry e registra decisao", async ({ page }) => {
  await page.goto("/tarefas/execucao");
  await page.getByRole("button", { name: /^Retry$/i }).click();
  await expect(page.getByText(/Retry solicitado para run-244/i)).toBeVisible();

  await page.goto("/governanca/aprovacao-detalhe");
  await page.getByRole("button", { name: /changes_requested/i }).nth(1).click();
  await page.getByLabel(/Comentario da aprovacao/i).fill("Precisa ajustar o checklist final.");
  await page.getByRole("button", { name: /Registrar decisao/i }).click();

  await expect(page.getByText(/Decisao changes_requested registrada/i)).toBeVisible();
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
  await page.getByLabel(/Consulta semantica/i).fill("onboarding enterprise");
  await page.getByRole("button", { name: /Executar busca/i }).click();

  await expect(page.getByText(/Resultados atualizados com score e fonte auditavel/i)).toBeVisible();
  await expect(page.getByText(/Busca semantica para onboarding enterprise/i).first()).toBeVisible();
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada lead para oportunidade aplica guard rails no pipeline", async ({ page }) => {
  await page.goto("/comercial/pipeline");
  await page.getByRole("button", { name: /^Atlas Logistics$/i }).click();

  await expect(page.getByText(/Atlas Logistics movida com validacao de campos obrigatorios/i)).toBeVisible();
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada conteudo para publicacao permite retry seguro", async ({ page }) => {
  await page.goto("/comercial/publicacoes");
  await page.getByRole("button", { name: /Campanha Q3 enterprise/i }).first().click();

  await expect(page.getByText(/Retry seguro solicitado/i)).toBeVisible();
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada experimento para resultado bloqueia campos apos start", async ({ page }) => {
  await page.goto("/aprendizado/experimento-detalhe");
  await page.getByRole("button", { name: /Iniciar experimento/i }).click();

  await expect(page.getByText(/Campos criticos agora estao bloqueados/i)).toBeVisible();
  await expectNoCriticalAccessibilityViolations(page);
});

test("jornada admin para auditoria executa job auditavel", async ({ page }) => {
  await page.goto("/administracao/privacidade-auditoria");
  await page.getByRole("button", { name: /Exportacao de dados pessoais/i }).click();

  await expect(page.getByText(/Job auditado: Exportacao de dados pessoais/i)).toBeVisible();
  await expectNoCriticalAccessibilityViolations(page);
});
