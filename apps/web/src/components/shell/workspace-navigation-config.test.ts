import { describe, expect, it } from "vitest";

import { screens } from "@/lib/screen-catalog";
import { buildMoreNavigation, primaryNavigation, primaryRoutePaths, productizeLaterRoutePaths } from "./workspace-navigation-config";

const sprintFourRoutes = new Set([
  "/operacao/home", "/operacao/busca-global", "/operacao/notificacoes", "/acesso/organizacoes",
  "/colaboracao/salas", "/colaboracao/sala", "/tarefas/inbox", "/tarefas/criar", "/tarefas/detalhe",
  "/governanca/aprovacoes", "/governanca/aprovacao-detalhe", "/comercial/leads",
  "/comercial/lead-detalhe", "/comercial/pipeline"
]);

describe("workspace navigation configuration", () => {
  it("keeps at most seven operational groups and only Sprint 4 routes in primary navigation", () => {
    expect(primaryNavigation.length).toBeLessThanOrEqual(7);
    expect(primaryNavigation.flatMap((group) => group.routes)).toHaveLength(7);
    for (const route of primaryRoutePaths) expect(sprintFourRoutes.has(route)).toBe(true);
  });

  it("keeps every non-primary product route in categorized modules", () => {
    const more = buildMoreNavigation();
    const morePaths = new Set(more.flatMap((group) => group.routes.map((route) => route.href)));
    expect(productizeLaterRoutePaths.size).toBe(screens.length - primaryRoutePaths.size - 1);
    expect(morePaths).toEqual(productizeLaterRoutePaths);
    expect(morePaths.has("/acesso/login")).toBe(false);
    expect(morePaths.has("/colaboracao/membros")).toBe(true);
    expect(morePaths.has("/tarefas/execucao")).toBe(true);
    expect(morePaths.has("/governanca/portal-externo")).toBe(true);
    expect(more.map((group) => group.label)).toEqual([
      "Agentes", "Conta", "Preferencias", "Governanca", "Automacao", "Conhecimento", "Crescimento", "Analises", "Administracao"
    ]);
    expect(more.flatMap((group) => group.routes).map((route) => route.href)).toHaveLength(morePaths.size);
    expect(primaryNavigation.flatMap((group) => [group.label, ...group.routes.map((route) => route.label)]).join(" "))
      .not.toMatch(/T\d{2}|Sprint|OpenAPI|endpoint|handoff|contrato/i);
  });

  it("ignores catalog entries outside the canonical product catalog", () => {
    const unknown = { ...screens[0]!, area: "Acesso" as const, title: "Legado", slug: ["acesso", "legado"] };
    expect(buildMoreNavigation([unknown])).toEqual([]);
  });
});
