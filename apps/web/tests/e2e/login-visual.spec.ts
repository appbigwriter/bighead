import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("login permanece legivel com preferencia escura salva", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("bighead-theme", "radar-dark");
    localStorage.setItem(
      "bighead-visual-preferences",
      JSON.stringify({ theme: "radar-dark", density: "comfortable", motion: "full" })
    );
  });
  await page.goto("/login");

  await expect(page.getByRole("heading", { name: "Boas-vindas" })).toBeVisible();
  const primaryAction = page.getByRole("button", { name: "Entrar", exact: true });
  await expect(primaryAction).toBeVisible();
  const actionBox = await primaryAction.boundingBox();
  const viewport = page.viewportSize();
  expect(actionBox && viewport && actionBox.y + actionBox.height <= viewport.height).toBe(true);
  await expect(page.getByLabel("Entrar sem senha")).toBeHidden();
  await page.getByText("Outras formas de acesso", { exact: true }).click();
  await expect(page.getByLabel("Entrar sem senha")).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth
  );
  expect(overflow).toBeLessThanOrEqual(1);

  const scan = await new AxeBuilder({ page }).analyze();
  expect(
    scan.violations.filter(({ impact }) => impact === "critical" || impact === "serious")
  ).toHaveLength(0);
});
