import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  CircleAlert,
  Clock3,
  ListTodo,
  WalletCards
} from "lucide-react";

import type { WorkspaceSnapshot, WorkspaceOption } from "@/lib/mock-workspace";

import styles from "./home-dashboard.module.css";

const terminalTaskStates = new Set(["done", "completed", "canceled", "cancelled"]);
const riskOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

const statusLabels: Record<string, string> = {
  new: "Nova",
  triaged: "Triada",
  in_progress: "Em andamento",
  blocked: "Bloqueada",
  ready_for_review: "Pronta para revisão",
  done: "Concluída",
  completed: "Concluída",
  canceled: "Cancelada",
  cancelled: "Cancelada",
  overdue: "Em atraso",
  critical: "Crítico",
  high: "Alto",
  medium: "Médio",
  low: "Baixo",
  pending: "Aguardando decisão",
  approved: "Aprovada",
  rejected: "Rejeitada"
};

function statusLabel(status?: string) {
  if (!status) return "Status não informado";
  return statusLabels[status] ?? status.replaceAll("_", " ");
}

function isPendingApproval(item: WorkspaceOption) {
  return !item.status || item.status === "pending";
}

function taskHref(item: WorkspaceOption) {
  const params = new URLSearchParams({ taskId: item.id });
  return `/tarefas/detalhe?${params.toString()}`;
}

function approvalHref(item: WorkspaceOption) {
  const params = new URLSearchParams({ approvalId: item.id });
  return `/governanca/aprovacao-detalhe?${params.toString()}`;
}

function dueTimestamp(item: WorkspaceOption) {
  const value = item.dueAt ?? item.slaAt;
  if (!value) return Number.POSITIVE_INFINITY;
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : Number.POSITIVE_INFINITY;
}

function dueLabel(item: WorkspaceOption) {
  const timestamp = dueTimestamp(item);
  if (!Number.isFinite(timestamp)) return "Prazo indisponível";
  return `Prazo ${new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", timeZone: "UTC" }).format(timestamp)}`;
}

function ownerLabel(item: WorkspaceOption) {
  return item.assigneeId ? `ID do responsável: ${item.assigneeId}` : "Responsável indisponível";
}

function riskLabel(item: WorkspaceOption) {
  return item.riskLevel ? `Risco ${statusLabel(item.riskLevel)}` : "Risco indisponível";
}

export function HomeDashboard({ snapshot }: { snapshot: WorkspaceSnapshot }) {
  const activeTasks = snapshot.taskOptions.filter((task) => !terminalTaskStates.has(task.status ?? ""));
  const pendingApprovals = snapshot.approvalOptions.filter(isPendingApproval);
  const slaSignal = snapshot.analyticsDrilldowns.find((item) =>
    /overdue|sla|breach/i.test(item.dimension)
  );
  const priorities = [
    ...activeTasks.map((item) => ({
      id: `task-${item.id}`,
      kind: "Tarefa",
      title: item.name,
      status: statusLabel(item.status),
      href: taskHref(item),
      owner: ownerLabel(item),
      due: dueLabel(item),
      risk: riskLabel(item),
      nextAction: item.nextAction ? `Próxima ação: ${item.nextAction}` : "Próxima ação indisponível",
      riskRank: riskOrder[item.riskLevel ?? ""] ?? 4,
      dueRank: dueTimestamp(item)
    })),
    ...pendingApprovals.map((item) => ({
      id: `approval-${item.id}`,
      kind: "Aprovação",
      title: item.name,
      status: statusLabel(item.status),
      href: approvalHref(item),
      owner: ownerLabel(item),
      due: dueLabel(item),
      risk: riskLabel(item),
      nextAction: item.nextAction ? `Próxima ação: ${item.nextAction}` : "Próxima ação indisponível",
      riskRank: riskOrder[item.riskLevel ?? ""] ?? 4,
      dueRank: dueTimestamp(item)
    }))
  ].sort((left, right) => {
    if (left.riskRank !== right.riskRank) return left.riskRank - right.riskRank;
    const dueDifference = left.dueRank - right.dueRank;
    if (Number.isFinite(dueDifference) && dueDifference) return dueDifference;
    return left.id.localeCompare(right.id);
  }).slice(0, 6);

  return (
    <div className={styles.home} aria-labelledby="home-title">
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Visão geral</p>
          <h2 id="home-title">Operação de {snapshot.currentOrganization}</h2>
          <p className={styles.intro}>Prioridades, decisões e sinais do workspace atual.</p>
        </div>
        <Link className={styles.primaryAction} href="/tarefas/criar">
          Nova tarefa <ArrowUpRight aria-hidden="true" size={17} />
        </Link>
      </header>

      <section className={styles.metrics} aria-label="Indicadores operacionais">
        <Metric icon={<ListTodo aria-hidden="true" />} label="Tarefas ativas nesta página" value={String(activeTasks.length)} href="/tarefas/inbox?view=active" />
        <Metric icon={<CheckCircle2 aria-hidden="true" />} label="Aprovações pendentes nesta página" value={String(pendingApprovals.length)} href="/governanca/aprovacoes?status=pending" />
        <Metric
          icon={<Clock3 aria-hidden="true" />}
          label="SLA em risco"
          value={slaSignal ? String(slaSignal.value) : "Indisponível"}
          muted={!slaSignal}
        />
        <Metric icon={<WalletCards aria-hidden="true" />} label="Custo no período" value="Indisponível" muted />
      </section>

      <div className={styles.workspaceGrid}>
        <section className={styles.prioritySection} aria-labelledby="priorities-title">
          <SectionHeading
            title="Prioridades"
            description="Itens que ainda exigem ação no workspace."
            href="/tarefas/inbox?view=active"
            action="Ver todas"
          />
          {priorities.length ? (
            <ol className={styles.priorityList} aria-label="Prioridades abertas">
              {priorities.map((item, index) => (
                <li key={item.id}>
                  <Link className={styles.priorityRow} href={item.href}>
                    <span className={styles.priorityIndex}>{String(index + 1).padStart(2, "0")}</span>
                    <span className={styles.priorityContent}>
                      <span className={styles.priorityKind}>{item.kind}</span>
                      <strong>{item.title}</strong>
                      <span className={styles.priorityMeta}>
                        <span>{item.owner}</span>
                        <span>{item.due}</span>
                        <span>{item.risk}</span>
                        <span>{item.nextAction}</span>
                      </span>
                    </span>
                    <span className={styles.priorityStatus}>{item.status}</span>
                    <ArrowUpRight aria-hidden="true" className={styles.rowArrow} size={18} />
                  </Link>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState icon={<CheckCircle2 aria-hidden="true" />} title="Nenhuma prioridade aberta" description="Não há tarefas ativas ou aprovações pendentes neste workspace." />
          )}
        </section>

        <aside className={styles.signalRail} aria-label="Contexto operacional">
          <section aria-labelledby="sla-title">
            <SectionHeading title="SLA" />
            {slaSignal ? (
              <div className={styles.signalValue}>
                <strong>{slaSignal.value}</strong>
                <span>itens sinalizados em {statusLabel(slaSignal.dimension)}</span>
              </div>
            ) : (
              <EmptyState compact icon={<Clock3 aria-hidden="true" />} title="Sem leitura de SLA" description="O resumo atual não fornece risco ou atraso de SLA." />
            )}
          </section>

          <section aria-labelledby="custo-title">
            <SectionHeading title="Custo" />
            <EmptyState compact icon={<WalletCards aria-hidden="true" />} title="Custo indisponível" description="O snapshot atual não inclui consumo financeiro." />
          </section>
        </aside>
      </div>

      <section className={styles.activitySection} aria-labelledby="atividade-recente-title">
        <SectionHeading title="Atividade recente" description="Últimos eventos visíveis para seu perfil." />
        {snapshot.adminMoments.length ? (
          <ul className={styles.activityList}>
            {snapshot.adminMoments.slice(0, 4).map((item, index) => (
              <li key={item.id ?? `${item.title}-${index}`}>
                <span className={styles.activityMarker}><Activity aria-hidden="true" size={15} /></span>
                <span>
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState icon={<CircleAlert aria-hidden="true" />} title="Atividade indisponível" description="Nenhum evento de auditoria foi retornado para este perfil." />
        )}
      </section>
    </div>
  );
}

function Metric({ icon, label, value, href, muted = false }: { icon: React.ReactNode; label: string; value: string; href?: string; muted?: boolean }) {
  const content = (
    <>
      <span className={styles.metricIcon}>{icon}</span>
      <span>
        <span className={styles.metricLabel}>{label}</span>
        <strong>{value}</strong>
      </span>
      {href ? <ArrowUpRight aria-hidden="true" size={16} /> : null}
    </>
  );
  const className = `${styles.metric} ${muted ? styles.metricMuted : ""} ${href ? "" : styles.metricStatic}`;
  return href ? <Link className={className} href={href}>{content}</Link> : <div className={className}>{content}</div>;
}

function SectionHeading({ title, description, href, action }: { title: string; description?: string; href?: string; action?: string }) {
  return (
    <div className={styles.sectionHeading}>
      <div>
        <h3 id={`${title.toLowerCase().replaceAll(" ", "-")}-title`}>{title}</h3>
        {description ? <p>{description}</p> : null}
      </div>
      {href && action ? <Link href={href}>{action}<ArrowUpRight aria-hidden="true" size={15} /></Link> : null}
    </div>
  );
}

function EmptyState({ icon, title, description, compact = false }: { icon: React.ReactNode; title: string; description: string; compact?: boolean }) {
  return (
    <div className={`${styles.empty} ${compact ? styles.emptyCompact : ""}`}>
      <span>{icon}</span>
      <div><strong>{title}</strong><p>{description}</p></div>
    </div>
  );
}
