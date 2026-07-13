import Link from "next/link";
import type { PropsWithChildren } from "react";

import { areaOrder, screensByArea } from "@/lib/screen-catalog";
import { getServerWorkspaceData } from "@/lib/server-workspace-service";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";
import { shouldUseMockWorkspace } from "@/lib/workspace-mode";
import { ThemeToggle } from "./theme-toggle";
import { WorkspaceRealtime } from "./workspace-realtime";

export async function WorkspaceShell({ children }: PropsWithChildren) {
  const snapshot = await getServerWorkspaceData(await getWorkspaceRequestContext());

  return (
    <div className="bh-shell">
      {!shouldUseMockWorkspace() && snapshot.currentOrganizationId ? <WorkspaceRealtime tenantId={snapshot.currentOrganizationId} /> : null}
      <aside className="bh-sidebar">
        <div className="bh-brand">
          <div>
            <span className="bh-eyebrow">Sprint 2</span>
            <strong>BigHead Workspace</strong>
          </div>
          <span className="bh-badge bh-badge-accent">56 telas</span>
        </div>

        <div className="bh-sidebar-block">
          <span className="bh-label">Organizacao atual</span>
          <div className="bh-org-switcher">
            <strong>{snapshot.currentOrganization}</strong>
            <span>{snapshot.organizations.length} tenants disponiveis</span>
          </div>
        </div>

        <nav className="bh-nav" aria-label="Navegacao principal">
          {areaOrder.map((area) => {
            const entries = screensByArea[area];
            return (
              <div className="bh-nav-group" key={area}>
                <span className="bh-label">{area}</span>
                {entries.map((entry) => (
                  <Link className="bh-nav-link" href={`/${entry.slug.join("/")}`} key={entry.code}>
                    <span>{entry.code}</span>
                    <span>{entry.title}</span>
                  </Link>
                ))}
              </div>
            );
          })}
        </nav>
      </aside>

      <div className="bh-main">
        <header className="bh-topbar">
          <div className="bh-topbar-main">
            <div>
              <span className="bh-eyebrow">Operacao orientada por contratos</span>
              <h1>Workspace conectado aos servicos BigHead</h1>
            </div>
            <div className="bh-topbar-actions">
              <Link className="bh-chip" href="/catalogo">
                Catalogo UI
              </Link>
              <Link className="bh-chip" href="/operacao/busca-global">
                Command palette
              </Link>
              <Link className="bh-chip" href="/operacao/notificacoes">
                Notificacoes {snapshot.notifications}
              </Link>
              <ThemeToggle />
              <form action="/auth/signout" method="post">
                <button className="bh-chip" type="submit">Sair</button>
              </form>
            </div>
          </div>

          <div className="bh-command-bar">
            <input
              aria-label="Buscar contexto no workspace"
              defaultValue="Buscar tarefas, salas, leads ou memoria"
              readOnly
            />
            <div className="bh-shortcuts">
              {snapshot.commandShortcuts.map((shortcut) => (
                <span className="bh-shortcut" key={shortcut}>
                  {shortcut}
                </span>
              ))}
            </div>
          </div>
        </header>

        <main className="bh-content">{children}</main>
      </div>
    </div>
  );
}
