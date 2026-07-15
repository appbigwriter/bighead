"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button } from "@bighead/ui";
import { Bot, Building2, ChevronDown, CircleGauge, FileCheck2, FolderSearch, Home, KanbanSquare, LibraryBig, Menu, MessageSquare, Plus, ShieldCheck, Sparkles, Target, UserRound, UsersRound, X } from "lucide-react";

import type { WorkspaceOption } from "@/lib/mock-workspace";
import { TenantSelector } from "./tenant-selector";
import type { ShellGroup, ShellIcon } from "./workspace-navigation-config";
import styles from "./workspace-shell.module.css";

const focusableSelector = [
  "a[href]",
  "button:not([disabled])",
  "select:not([disabled])",
  "summary",
  "[tabindex]:not([tabindex='-1'])"
].join(",");

const routeIcons: Record<ShellIcon, typeof Home> = {
  home: Home, messages: MessageSquare, tasks: KanbanSquare, plus: Plus,
  approvals: FileCheck2, leads: UsersRound, pipeline: Target
};

const groupIcons: Record<string, typeof Home> = {
  Conta: UserRound, Preferencias: UserRound, Governanca: ShieldCheck, Automacao: Bot,
  Conhecimento: LibraryBig, Crescimento: Sparkles,
  Analises: CircleGauge, Administracao: Building2
};

export function WorkspaceNavigation({
  tenantName,
  tenantCount,
  currentOrganizationId,
  organizations,
  primary,
  more
}: {
  tenantName: string;
  tenantCount: number;
  currentOrganizationId: string;
  organizations: WorkspaceOption[];
  primary: ShellGroup[];
  more: ShellGroup[];
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const sidebar = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    const workspace = document.getElementById("workspace-content");
    const workspaceWasInert = workspace?.hasAttribute("inert") ?? false;
    const previousAriaHidden = workspace?.getAttribute("aria-hidden");
    const previousBodyOverflow = document.body.style.overflow;
    workspace?.setAttribute("inert", "");
    workspace?.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "hidden";
    sidebar.current?.querySelector<HTMLButtonElement>("button[aria-label='Fechar menu']")?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(sidebar.current?.querySelectorAll<HTMLElement>(focusableSelector) ?? [])
        .filter((element) => {
          const closedDetails = element.closest("details:not([open])");
          return !closedDetails || element.tagName === "SUMMARY";
        });
      const first = focusable[0];
      const last = focusable.at(-1);
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      if (!workspaceWasInert) workspace?.removeAttribute("inert");
      if (previousAriaHidden === null || previousAriaHidden === undefined) workspace?.removeAttribute("aria-hidden");
      else workspace?.setAttribute("aria-hidden", previousAriaHidden);
      document.body.style.overflow = previousBodyOverflow;
      document
        .querySelector<HTMLButtonElement>("button[aria-controls='workspace-navigation']")
        ?.focus();
    };
  }, [open]);

  const close = () => setOpen(false);

  return (
    <>
      <Button
        aria-controls="workspace-navigation"
        aria-expanded={open}
        className={styles.menuButton}
        onClick={() => setOpen(true)}
        type="button"
      >
        <Menu aria-hidden="true" size={18} /><span>Menu</span>
      </Button>
      <Button aria-hidden="true" aria-label="Fechar menu ao clicar fora" className={styles.backdrop} data-open={open} onClick={close} tabIndex={-1} tone="secondary" type="button" />
      <aside
        aria-label={open ? "Navegacao do workspace" : undefined}
        aria-modal={open ? true : undefined}
        className={styles.sidebar}
        data-open={open}
        id="workspace-navigation"
        ref={sidebar}
        role={open ? "dialog" : undefined}
      >
        <div className={styles.brandRow}>
          <Link className={styles.brand} href="/operacao/home" onClick={close}>
            <span className={styles.brandMark} aria-hidden="true">B</span>
            <span><strong>BigHead</strong><small>Operacoes</small></span>
          </Link>
          <Button aria-label="Fechar menu" className={styles.closeButton} onClick={close} tone="secondary" type="button"><X aria-hidden="true" size={19} /></Button>
        </div>

        <div className={styles.tenant}>
          <span className={styles.tenantAvatar} aria-hidden="true">{tenantName.slice(0, 1).toUpperCase()}</span>
          <span><strong>{tenantName}</strong><em>{tenantCount === 1 ? "1 acesso" : `${tenantCount} acessos`}</em></span>
        </div>
        <TenantSelector currentOrganizationId={currentOrganizationId} organizations={organizations} />

        <nav aria-label="Navegacao principal" className={styles.navigation}>
          {primary.map((group) => (
            <div className={styles.navGroup} key={group.label}>
              <span className={styles.groupLabel}>{group.label}</span>
              {group.routes.map((route) => {
                const Icon = route.icon ? routeIcons[route.icon] : FolderSearch;
                return <Link
                  aria-current={pathname === route.href || pathname.startsWith(`${route.href}/`) ? "page" : undefined}
                  className={styles.navLink}
                  href={route.href}
                  key={route.href}
                  onClick={close}
                  prefetch={false}
                >
                  <Icon aria-hidden="true" className={styles.navIcon} size={17} />
                  <span>{route.label}</span>
                </Link>;
              })}
            </div>
          ))}
          <div className={styles.moduleNavigation}>
            <span className={styles.moduleHeading}>Modulos</span>
            {more.map((group) => {
              const Icon = groupIcons[group.label] ?? FolderSearch;
              const current = group.routes.some((route) => pathname === route.href || pathname.startsWith(`${route.href}/`));
              return <details className={styles.moduleGroup} key={group.label} open={current || undefined}>
                <summary><Icon aria-hidden="true" size={17} /><span>{group.label}</span><ChevronDown aria-hidden="true" className={styles.moduleChevron} size={15} /></summary>
                <div className={styles.moduleRoutes}>
                {group.routes.map((route) => (
                  <Link aria-current={pathname === route.href ? "page" : undefined} href={route.href} key={route.href} onClick={close} prefetch={false}>{route.label}</Link>
                ))}
                </div>
              </details>;
            })}
          </div>
        </nav>
      </aside>
    </>
  );
}
