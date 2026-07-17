import { areaOrder, screens, type ScreenDefinition } from "@/lib/screen-catalog";

export type ShellIcon = "home" | "messages" | "tasks" | "plus" | "approvals" | "leads" | "pipeline";
export type ShellRoute = { label: string; href: string; icon?: ShellIcon };
export type ShellGroup = { label: string; routes: ShellRoute[] };

export const primaryNavigation: ShellGroup[] = [
  { label: "Visao geral", routes: [{ label: "Inicio", href: "/operacao/home", icon: "home" }] },
  { label: "Conversas", routes: [{ label: "Salas", href: "/colaboracao/salas", icon: "messages" }] },
  {
    label: "Trabalho",
    routes: [
      { label: "Tarefas", href: "/tarefas/inbox", icon: "tasks" },
      { label: "Criar tarefa", href: "/tarefas/criar", icon: "plus" },
      { label: "Aprovacoes", href: "/governanca/aprovacoes", icon: "approvals" }
    ]
  },
  {
    label: "Comercial",
    routes: [
      { label: "Leads", href: "/comercial/leads", icon: "leads" },
      { label: "Pipeline", href: "/comercial/pipeline", icon: "pipeline" }
    ]
  }
];

export const primaryRoutePaths = new Set(primaryNavigation.flatMap((group) => group.routes.map((route) => route.href)));

const workspaceExcludedRoutePaths = new Set(["/acesso/login"]);

const agentRouteLabels = new Map([
  ["/automacao/agentes", "Painel de Agentes"],
  ["/automacao/agente-config", "Configuração do Agente"],
  ["/automacao/prompts", "Biblioteca de Prompts"],
  ["/automacao/workflows", "Lista de Workflows"],
  ["/conhecimento/biblioteca", "Biblioteca de Conhecimento (RAG)"]
]);

/** Deep links available from the module navigation. */
export const productizeLaterRoutePaths = new Set(
  screens
    .map((screen) => `/${screen.slug.join("/")}`)
    .filter((route) => !primaryRoutePaths.has(route) && !workspaceExcludedRoutePaths.has(route))
);

export function buildMoreNavigation(definitions: ScreenDefinition[] = screens): ShellGroup[] {
  const agentRoutes = definitions
    .map((screen) => `/${screen.slug.join("/")}`)
    .filter((route) => agentRouteLabels.has(route) && productizeLaterRoutePaths.has(route))
    .map((href) => ({ label: agentRouteLabels.get(href)!, href }));

  const baseGroups = areaOrder.flatMap((area) => {
    const routes = definitions
      .filter((screen) => screen.area === area)
      .map((screen) => ({ label: screen.title, href: `/${screen.slug.join("/")}` }))
      .filter(
        (route) => productizeLaterRoutePaths.has(route.href) && !agentRouteLabels.has(route.href)
      );
    const labels: Partial<Record<ScreenDefinition["area"], string>> = {
      Acesso: "Conta", Operacao: "Preferencias", Governanca: "Governanca", Automacao: "Automacao",
      Conhecimento: "Conhecimento", Comercial: "Crescimento",
      Aprendizado: "Analises", Administracao: "Administracao"
    };
    return routes.length ? [{ label: labels[area] ?? area, routes }] : [];
  });

  return agentRoutes.length ? [{ label: "Agentes", routes: agentRoutes }, ...baseGroups] : baseGroups;
}
