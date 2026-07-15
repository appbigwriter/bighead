import Link from "next/link";
import type { PropsWithChildren } from "react";
import { Button } from "@bighead/ui";
import { Bell, LogOut, Search, Settings2, UserRound } from "lucide-react";

import { getServerWorkspaceData } from "@/lib/server-workspace-service";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";
import { shouldUseMockWorkspace } from "@/lib/workspace-mode";
import { ThemeToggle } from "./theme-toggle";
import { classifyWorkspaceAccessError, WorkspaceAccessState } from "./workspace-access-state";
import { buildMoreNavigation, primaryNavigation } from "./workspace-navigation-config";
import { WorkspaceNavigation } from "./workspace-navigation";
import { WorkspaceRealtime } from "./workspace-realtime";
import styles from "./workspace-shell.module.css";

export async function WorkspaceShell({ children }: PropsWithChildren) {
  let snapshot;
  try {
    snapshot = await getServerWorkspaceData(await getWorkspaceRequestContext());
  } catch (error) {
    const state = classifyWorkspaceAccessError(error);
    if (state) return <WorkspaceAccessState kind={state} />;
    throw error;
  }
  const notificationLabel = snapshot.notifications === null
    ? "Notificacoes: contagem indisponivel"
    : `Notificacoes: ${snapshot.notifications} nao lidas`;

  return (
    <div className={styles.shell}>
      {!shouldUseMockWorkspace() && snapshot.currentOrganizationId ? <WorkspaceRealtime tenantId={snapshot.currentOrganizationId} /> : null}
      <WorkspaceNavigation
        more={buildMoreNavigation()}
        primary={primaryNavigation}
        currentOrganizationId={snapshot.currentOrganizationId ?? ""}
        organizations={snapshot.organizationOptions}
        tenantCount={snapshot.organizations.length}
        tenantName={snapshot.currentOrganization}
      />

      <div className={styles.workspace} id="workspace-content">
        <header className={styles.topbar}>
          <span className={styles.mobileBrand}>BigHead</span>
          <Link className={styles.search} href="/operacao/busca-global" prefetch={false}>
            <Search aria-hidden="true" size={17} />
            <span>Buscar tarefas, conversas e clientes</span><kbd>Ctrl K</kbd>
          </Link>
          <div className={styles.topbarActions}>
            <Link aria-label={notificationLabel} className={styles.action} href="/operacao/notificacoes" prefetch={false}>
              <Bell aria-hidden="true" size={17} /><span className={styles.actionText}>Notificacoes</span><span className={styles.count}>{snapshot.notifications ?? "-"}</span>
            </Link>
            <Link aria-label="Perfil" className={styles.action} href="/operacao/perfil" prefetch={false}><UserRound aria-hidden="true" size={17} /><span className={styles.actionText}>Perfil</span></Link>
            <details className={styles.settings}>
              <summary aria-label="Aparencia"><Settings2 aria-hidden="true" size={17} /><span className={styles.actionText}>Aparencia</span></summary>
              <div><ThemeToggle organizationId={snapshot.currentOrganizationId ?? ""} /></div>
            </details>
            <form action="/auth/signout" method="post">
              <Button aria-label="Sair" className={styles.action} type="submit"><LogOut aria-hidden="true" size={17} /><span className={styles.actionText}>Sair</span></Button>
            </form>
          </div>
        </header>

        <main className={styles.content}>{children}</main>
      </div>
    </div>
  );
}
