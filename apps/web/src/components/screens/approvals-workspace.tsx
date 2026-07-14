"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Button } from "@bighead/ui";

import styles from "./approvals-workspace.module.css";

type ApprovalItem = {
  id: string; taskId?: string; title: string; status: string; riskLevel: string;
  round: number; dueAt?: string | null; assignedTo?: string | null; createdAt?: string;
};
type ApprovalPage = { items: Array<Record<string, unknown>>; counters?: Record<string, number> };
type ApprovalDetail = {
  approval: Record<string, unknown>; task: Record<string, unknown>; requester: Record<string, unknown>;
  assignee?: Record<string, unknown> | null; artifact?: Record<string, unknown> | null;
  evidence?: Array<Record<string, unknown>>; impact: Record<string, unknown>;
  availableActions?: string[]; decisionBlockedReason?: string | null;
};
type DecisionHistory = { items: Array<Record<string, unknown>> };
type Tab = "pending" | "overdue" | "decided";

class ResponseError extends Error {
  constructor(public readonly status: number, message: string) { super(message); }
}

const riskLabels: Record<string, string> = { low: "Baixo", medium: "Médio", high: "Alto", critical: "Crítico" };
const decisionLabels: Record<string, string> = { approved: "Aprovada", changes_requested: "Alterações solicitadas", rejected: "Rejeitada" };
const actionLabels: Record<string, string> = { approved: "Aprovar", changes_requested: "Solicitar alterações", rejected: "Rejeitar" };
const blockedLabels: Record<string, string> = {
  self_approval_prohibited: "Você solicitou esta aprovação. Outra pessoa deve decidir.",
  assigned_to_another_reviewer: "Esta decisão está atribuída a outro revisor.",
  approval_already_decided: "Esta aprovação já foi decidida."
};

function value(record: Record<string, unknown>, ...keys: string[]) {
  for (const key of keys) if (record[key] !== undefined && record[key] !== null) return record[key];
  return undefined;
}
function text(record: Record<string, unknown>, ...keys: string[]) {
  const result = value(record, ...keys);
  return typeof result === "string" ? result : typeof result === "number" || typeof result === "boolean" ? String(result) : "";
}
function normalizeItem(raw: Record<string, unknown>): ApprovalItem {
  const taskId = text(raw, "taskId", "task_id");
  const createdAt = text(raw, "createdAt", "created_at");
  return {
    id: text(raw, "id"), ...(taskId ? { taskId } : {}),
    title: text(raw, "title") || "Aprovação sem título", status: text(raw, "status") || "pending",
    riskLevel: text(raw, "riskLevel", "risk_level") || "low", round: Number(value(raw, "round")) || 1,
    dueAt: text(raw, "dueAt", "due_at") || null, assignedTo: text(raw, "assignedTo", "assigned_to") || null,
    ...(createdAt ? { createdAt } : {})
  };
}
function dateLabel(raw: unknown) {
  if (typeof raw !== "string" || !raw) return "Sem prazo";
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? "Data indisponível" : new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(date);
}
function isOverdue(item: ApprovalItem) {
  return item.status === "pending" && Boolean(item.dueAt) && new Date(item.dueAt as string).getTime() < Date.now();
}
async function responseJson<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => ({})) as T & { detail?: unknown };
  if (!response.ok) throw new ResponseError(response.status, typeof body.detail === "string" ? body.detail : "Operação não concluída.");
  return body;
}
function compactId(raw: unknown) {
  const id = typeof raw === "string" ? raw : "";
  return id ? `${id.slice(0, 8)}…${id.slice(-4)}` : "Não informado";
}

export function ApprovalsWorkspace({ mode }: { mode: "inbox" | "detail" }) {
  const params = useSearchParams();
  const approvalId = params.get("approvalId") ?? "";
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [tab, setTab] = useState<Tab>(params.get("status") === "pending" ? "pending" : "pending");
  const [detail, setDetail] = useState<ApprovalDetail | null>(null);
  const [history, setHistory] = useState<DecisionHistory>({ items: [] });
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [feedback, setFeedback] = useState("");
  const [pending, setPending] = useState(false);
  const [conflict, setConflict] = useState(false);

  const loadList = useCallback(async () => {
    setState("loading"); setFeedback("");
    try {
      const page = await responseJson<ApprovalPage>(await fetch("/api/approvals", { cache: "no-store" }));
      setItems(page.items.map(normalizeItem)); setState("ready");
    } catch (error) { setItems([]); setState("error"); setFeedback(error instanceof Error ? error.message : "Aprovações indisponíveis."); }
  }, []);

  const loadDetail = useCallback(async () => {
    if (!approvalId) return;
    setState("loading"); setFeedback(""); setConflict(false);
    try {
      const encoded = encodeURIComponent(approvalId);
      const [nextDetail, nextHistory] = await Promise.all([
        responseJson<ApprovalDetail>(await fetch(`/api/approvals/${encoded}`, { cache: "no-store" })),
        responseJson<DecisionHistory>(await fetch(`/api/approvals/${encoded}/decisions`, { cache: "no-store" }))
      ]);
      setDetail(nextDetail); setHistory(nextHistory); setState("ready");
    } catch (error) { setDetail(null); setHistory({ items: [] }); setState("error"); setFeedback(error instanceof Error ? error.message : "Aprovação indisponível."); }
  }, [approvalId]);

  useEffect(() => { if (mode === "inbox") void loadList(); else void loadDetail(); }, [loadDetail, loadList, mode]);

  const groups = useMemo(() => ({
    pending: items.filter((item) => item.status === "pending" && !isOverdue(item)),
    overdue: items.filter(isOverdue), decided: items.filter((item) => item.status !== "pending")
  }), [items]);

  async function submitDecision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail || !approvalId) return;
    const form = new FormData(event.currentTarget);
    setPending(true); setConflict(false); setFeedback("");
    try {
      await responseJson(await fetch(`/api/approvals/${encodeURIComponent(approvalId)}/decision`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ decision: form.get("decision"), comment: form.get("comment"), expectedRound: Number(value(detail.approval, "round")) })
      }));
      await loadDetail();
      setFeedback("Decisão registrada. O trabalho relacionado foi atualizado.");
    } catch (error) {
      const message = error instanceof ResponseError && error.status === 403
        ? "Decisão bloqueada pela segregação de funções."
        : error instanceof ResponseError && error.status === 409
          ? "Outra pessoa decidiu esta rodada. Recarregue antes de continuar."
          : error instanceof Error ? error.message : "Decisão não registrada.";
      setConflict(error instanceof ResponseError && error.status === 409); setFeedback(message);
    } finally { setPending(false); }
  }

  if (mode === "inbox") return (
    <section className={styles.page} aria-labelledby="approvals-title">
      <header className={styles.heading}><div><span>Governança</span><h1 id="approvals-title">Aprovações</h1><p>Decida trabalho com contexto, evidências e impacto visíveis.</p></div></header>
      <nav className={styles.tabs} aria-label="Filtrar aprovações">
        {(["pending", "overdue", "decided"] as const).map((name) => <Button aria-current={tab === name ? "page" : undefined} key={name} onClick={() => setTab(name)} tone="secondary" type="button"><span>{name === "pending" ? "Pendentes" : name === "overdue" ? "Vencidas" : "Decididas"}</span><strong>{groups[name].length}</strong></Button>)}
      </nav>
      {feedback ? <p className={styles.feedback} role="status">{feedback}</p> : null}
      {state === "loading" ? <div className={styles.empty}>Carregando aprovações...</div> : null}
      {state === "error" ? <div className={styles.empty}><strong>Aprovações indisponíveis</strong><Button onClick={() => { void loadList(); }} type="button">Tentar novamente</Button></div> : null}
      {state === "ready" ? <div className={styles.list}>{groups[tab].map((item) => <Link href={`/governanca/aprovacao-detalhe?approvalId=${encodeURIComponent(item.id)}`} key={item.id} prefetch={false}><span className={styles.risk} data-risk={item.riskLevel} aria-label={`Risco ${riskLabels[item.riskLevel] ?? item.riskLevel}`} /><span><strong>{item.title}</strong><small>Rodada {item.round} · {riskLabels[item.riskLevel] ?? "Risco não informado"}</small></span><span><em>{item.status === "pending" ? isOverdue(item) ? "Vencida" : "Pendente" : decisionLabels[item.status] ?? "Decidida"}</em><small>{dateLabel(item.dueAt)}</small></span></Link>)}{groups[tab].length === 0 ? <div className={styles.empty}><strong>{tab === "pending" ? "Nenhuma decisão pendente" : tab === "overdue" ? "Nenhuma aprovação vencida" : "Nenhuma decisão registrada"}</strong><span>{tab === "pending" ? "O trabalho pode continuar sem revisão agora." : "Escolha outra fila para continuar."}</span>{tab !== "pending" ? <Button onClick={() => setTab("pending")} type="button">Ver pendentes</Button> : <Link href="/operacao/home">Voltar ao início</Link>}</div> : null}</div> : null}
    </section>
  );

  if (!approvalId) return <section className={styles.page}><div className={styles.empty}><strong>Selecione uma aprovação</strong><Link href="/governanca/aprovacoes">Abrir fila</Link></div></section>;
  if (state === "loading") return <section className={styles.page}><div className={styles.empty}>Carregando contexto da decisão...</div></section>;
  if (state === "error" || !detail) return <section className={styles.page}><div className={styles.empty}><strong>Aprovação indisponível</strong><span>{feedback}</span><Button onClick={() => { void loadDetail(); }} type="button">Tentar novamente</Button><Link href="/governanca/aprovacoes">Voltar para aprovações</Link></div></section>;

  const approval = detail.approval;
  const task = detail.task;
  const evidence = detail.evidence ?? [];
  const actions = detail.availableActions ?? [];
  const blocker = detail.decisionBlockedReason;
  return (
    <section className={styles.page} aria-labelledby="approval-detail-title">
      <header className={styles.heading}><div><Link href="/governanca/aprovacoes">Aprovações</Link><h1 id="approval-detail-title">{text(task, "title") || "Decisão pendente"}</h1><p>{text(task, "objective") || "Revise o contexto antes de decidir."}</p></div><em>{text(approval, "status") === "pending" ? "Pendente" : decisionLabels[text(approval, "status")] ?? "Decidida"}</em></header>
      {feedback ? <p className={styles.feedback} role="status">{feedback}</p> : null}
      <div className={styles.detailGrid}>
        <main className={styles.contextColumn}>
          <section aria-labelledby="decision-context"><h2 id="decision-context">Contexto da decisão</h2><dl><div><dt>Solicitante</dt><dd>{compactId(value(detail.requester, "id"))}</dd></div><div><dt>Risco</dt><dd>{riskLabels[text(approval, "risk_level", "riskLevel")] ?? "Não informado"}</dd></div><div><dt>Prazo</dt><dd>{dateLabel(value(approval, "due_at", "dueAt"))}</dd></div><div><dt>Rodada</dt><dd>{text(approval, "round") || "1"}</dd></div></dl></section>
          <section aria-labelledby="impact-title"><h2 id="impact-title">Impacto</h2><dl><div><dt>Estado da tarefa</dt><dd>{text(detail.impact, "taskStatus") || "Não informado"}</dd></div><div><dt>Execuções ativas</dt><dd>{text(detail.impact, "activeRunCount") || "0"}</dd></div><div><dt>Custo estimado</dt><dd>{text(detail.impact, "estimatedCost") || "Não informado"}</dd></div><div><dt>SLA</dt><dd>{dateLabel(value(detail.impact, "slaAt"))}</dd></div></dl>{text(task, "id") ? <Link href={`/tarefas/detalhe?taskId=${encodeURIComponent(text(task, "id"))}`}>Abrir tarefa relacionada</Link> : null}</section>
          <section aria-labelledby="evidence-title"><h2 id="evidence-title">Evidências</h2>{evidence.length ? <div className={styles.evidence}>{evidence.map((item, index) => { const artifact = value(item, "artifact") as Record<string, unknown> | undefined; const evaluation = value(item, "evaluation") as Record<string, unknown> | undefined; return <article key={text(item, "id") || `${text(item, "type")}-${index}`}><strong>{text(item, "type") === "artifact" ? text(artifact ?? {}, "name") || "Artefato" : "Avaliação de qualidade"}</strong><span>{evaluation ? `Nota ${text(evaluation, "score") || "—"} · ${value(evaluation, "passed") === true ? "Aprovada" : "Requer atenção"}` : text(artifact ?? {}, "kind") || "Documento associado"}</span></article>; })}</div> : <p className={styles.muted}>Nenhuma evidência anexada a esta rodada.</p>}</section>
          <section aria-labelledby="history-title"><h2 id="history-title">Histórico de decisões</h2>{history.items.length ? <ol className={styles.history}>{history.items.map((item, index) => { const actor = value(item, "actor") as Record<string, unknown> | undefined; return <li key={text(item, "id") || index}><span><strong>{decisionLabels[text(item, "decision")] ?? text(item, "decision")}</strong><small>{text(actor ?? {}, "type") === "external" ? text(actor ?? {}, "name") : `Pessoa ${compactId(value(actor ?? {}, "id"))}`}</small></span><time>{dateLabel(value(item, "decidedAt"))}</time>{text(item, "comment") ? <p>{text(item, "comment")}</p> : null}</li>; })}</ol> : <p className={styles.muted}>Nenhuma decisão anterior nesta aprovação.</p>}</section>
        </main>
        <aside className={styles.decisionPanel} aria-labelledby="register-decision">
          <h2 id="register-decision">Registrar decisão</h2>
          {blocker ? <div className={styles.blocked} role="status"><strong>Decisão bloqueada</strong><span>{blockedLabels[blocker] ?? "Você não pode decidir esta aprovação."}</span></div> : null}
          <form onSubmit={(event) => { void submitDecision(event); }}>
            <fieldset disabled={pending || actions.length === 0}><legend>Resultado</legend>{actions.map((action, index) => <label key={action}><input defaultChecked={index === 0} name="decision" type="radio" value={action} />{actionLabels[action] ?? action}</label>)}</fieldset>
            <label>Comentário<textarea maxLength={10000} name="comment" placeholder="Registre o motivo da decisão" /></label>
            <Button disabled={pending || actions.length === 0} type="submit">{pending ? "Registrando..." : "Confirmar decisão"}</Button>
            {conflict ? <Button className={styles.secondary} onClick={() => { void loadDetail(); }} tone="secondary" type="button">Recarregar rodada</Button> : null}
          </form>
        </aside>
      </div>
    </section>
  );
}
