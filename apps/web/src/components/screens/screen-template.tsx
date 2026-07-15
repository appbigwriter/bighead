import { WorkspaceAccessState } from "@/components/shell/workspace-access-state";
import type { ScreenDefinition } from "@/lib/screen-catalog";
import { getServerWorkspaceData } from "@/lib/server-workspace-service";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";
import { ConversationsWorkspace } from "./conversations-workspace";
import { CommercialWorkspace } from "./commercial-workspace";
import { ApprovalsWorkspace } from "./approvals-workspace";
import { AgentsWorkspace } from "./agents-workspace";
import { GlobalSearch } from "./global-search";
import { HomeDashboard } from "./home-dashboard";
import { NotificationsCenter } from "./notifications-center";
import { ScreenExperience } from "./screen-experience";
import { TasksWorkspace } from "./tasks-workspace";

type ScreenTemplateProps = {
  screen: ScreenDefinition;
  searchParams?: Record<string, string | string[] | undefined>;
};

export async function ScreenTemplate({ screen, searchParams = {} }: ScreenTemplateProps) {
  const route = screen.slug.join("/");
  if (route === "operacao/busca-global") return <GlobalSearch />;
  if (route === "colaboracao/salas") return <ConversationsWorkspace mode="list" />;
  if (route === "colaboracao/sala") return <ConversationsWorkspace mode="room" />;
  if (route === "tarefas/inbox") return <TasksWorkspace mode="inbox" />;
  if (route === "tarefas/criar") return <TasksWorkspace mode="create" />;
  if (route === "tarefas/detalhe") return <TasksWorkspace mode="detail" />;
  if (route === "comercial/leads") return <CommercialWorkspace mode="leads" />;
  if (route === "comercial/lead-detalhe") return <CommercialWorkspace mode="detail" />;
  if (route === "comercial/pipeline") return <CommercialWorkspace mode="pipeline" />;
  if (route === "governanca/aprovacoes") return <ApprovalsWorkspace mode="inbox" />;
  if (route === "governanca/aprovacao-detalhe") return <ApprovalsWorkspace mode="detail" />;
  if (route === "automacao/agentes") return <AgentsWorkspace mode="catalog" />;
  if (route === "automacao/agente-config") return <AgentsWorkspace mode="detail" />;

  const context = await getWorkspaceRequestContext();
  const snapshot = await getServerWorkspaceData(context);
  if (route === "operacao/home") {
    return <HomeDashboard snapshot={snapshot} />;
  }
  if (route === "operacao/notificacoes") {
    const organizationId = snapshot.currentOrganizationId ?? context.tenantId;
    if (!organizationId) return <WorkspaceAccessState kind="tenant-empty" />;
    const requestedFilter = Array.isArray(searchParams.filter) ? searchParams.filter[0] : searchParams.filter;
    return (
      <NotificationsCenter
        organizationId={organizationId}
        filter={requestedFilter === "unread" ? "unread" : "all"}
      />
    );
  }
  return <ScreenExperience screen={screen} snapshot={snapshot} />;
}
