import { areaOrder, screens, type ScreenDefinition } from "@/lib/screen-catalog";

export type ShellRoute = { label: string; href: string };
export type ShellGroup = { label: string; routes: ShellRoute[] };

export const primaryNavigation: ShellGroup[] = [
  { label: "Visao geral", routes: [{ label: "Inicio", href: "/operacao/home" }] },
  { label: "Conversas", routes: [{ label: "Salas", href: "/colaboracao/salas" }] },
  {
    label: "Trabalho",
    routes: [
      { label: "Tarefas", href: "/tarefas/inbox" },
      { label: "Criar tarefa", href: "/tarefas/criar" },
      { label: "Aprovacoes", href: "/governanca/aprovacoes" }
    ]
  },
  {
    label: "Comercial",
    routes: [
      { label: "Leads", href: "/comercial/leads" },
      { label: "Pipeline", href: "/comercial/pipeline" }
    ]
  }
];

export const primaryRoutePaths = new Set(primaryNavigation.flatMap((group) => group.routes.map((route) => route.href)));

/** Rotas classificadas como `productize_later` no gate S4-00. */
export const productizeLaterRoutePaths = new Set([
  "/acesso/convite",
  "/acesso/onboarding",
  "/operacao/perfil",
  "/governanca/politicas",
  "/automacao/agentes",
  "/automacao/agente-config",
  "/automacao/skills",
  "/automacao/skill-teste",
  "/automacao/modelos",
  "/automacao/prompts",
  "/automacao/workflows",
  "/automacao/workflow-editor",
  "/automacao/workflow-versoes",
  "/automacao/playbooks",
  "/conhecimento/biblioteca",
  "/conhecimento/ingestao",
  "/conhecimento/memoria",
  "/conhecimento/busca-semantica",
  "/comercial/contas-contatos",
  "/comercial/campanhas",
  "/comercial/conteudo",
  "/comercial/publicacoes",
  "/aprendizado/experimentos",
  "/aprendizado/experimento-detalhe",
  "/aprendizado/dashboard-executivo",
  "/aprendizado/analytics-sla",
  "/aprendizado/analytics-agentes",
  "/aprendizado/custos",
  "/aprendizado/funil",
  "/administracao/organizacao",
  "/administracao/membros",
  "/administracao/integracoes",
  "/administracao/privacidade-auditoria"
]);

export function buildMoreNavigation(definitions: ScreenDefinition[] = screens): ShellGroup[] {
  return areaOrder.flatMap((area) => {
    const routes = definitions
      .filter((screen) => screen.area === area)
      .map((screen) => ({ label: screen.title, href: `/${screen.slug.join("/")}` }))
      .filter((route) => productizeLaterRoutePaths.has(route.href));
    return routes.length ? [{ label: area, routes }] : [];
  });
}
