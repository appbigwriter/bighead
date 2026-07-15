"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Button } from "@bighead/ui";

import { allowedTaskTransitions, type TaskStatus } from "@/lib/task-transitions";
import { transitionTask } from "@/lib/transition-task-client";
import type { WorkspaceRealtimeEvent } from "@/lib/realtime-protocol";
import styles from "./tasks-workspace.module.css";

type Task = {
  id: string; roomId?: string | null; sourceMessageId?: string | null; title: string; objective: string;
  status: TaskStatus; priority: number; riskLevel: string; requesterId?: string | null; assigneeId?: string | null;
  dueAt?: string | null; slaAt?: string | null; version: number; createdAt: string; updatedAt: string;
};
type TaskPage = { items: Task[]; nextCursor?: string | null };
type TaskFilters = { status: TaskStatus | ""; ownerId: string; risk: string; slaStatus: string };
type ExecutorKind = "person" | "agent" | "team";

class ResponseError extends Error {
  constructor(public readonly status: number, message: string) { super(message); }
}

const statusOptions: Array<{ value: "" | TaskStatus; label: string }> = [
  { value: "", label: "Todos" }, { value: "new", label: "Novas" }, { value: "triaged", label: "Triadas" },
  { value: "in_progress", label: "Em andamento" }, { value: "waiting_human", label: "Aguardando pessoa" },
  { value: "ready_for_review", label: "Em revisão" }, { value: "done", label: "Concluídas" }, { value: "failed", label: "Com falha" }
];

const statusLabels: Record<string, string> = {
  new: "Nova", triaged: "Triada", in_progress: "Em andamento", waiting_tool: "Aguardando ferramenta",
  waiting_human: "Aguardando pessoa", ready_for_review: "Em revisão", approved: "Aprovada", done: "Concluída",
  failed: "Com falha", canceled: "Cancelada"
};
const riskLabels: Record<string, string> = { low: "Baixo", medium: "Médio", high: "Alto", critical: "Crítico" };
function statusLabel(status: string) { return statusLabels[status] ?? "Estado indisponível"; }
function riskLabel(risk: string) { return riskLabels[risk] ?? "Não informado"; }
export function localDateTimeToIso(value: string) {
  if (!value) return null;
  const instant = new Date(value);
  return Number.isNaN(instant.getTime()) ? null : instant.toISOString();
}
function dateLabel(value?: string | null) {
  if (!value) return "Não definido";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Indisponível" : new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(date);
}
async function responseJson<T>(response: Response): Promise<T> {
  const value = await response.json().catch(() => ({})) as T & { detail?: unknown };
  if (!response.ok) throw new ResponseError(response.status, typeof value.detail === "string" ? value.detail : "Operação não concluída.");
  return value;
}

export function TasksWorkspace({ mode }: { mode: "inbox" | "create" | "detail" }) {
  const router = useRouter();
  const params = useSearchParams();
  const taskId = params.get("taskId") ?? "";
  const contextRoomId = params.get("roomId") ?? "";
  const contextMessageId = params.get("sourceMessageId") ?? "";
  const [tasks, setTasks] = useState<Task[]>([]);
  const [filters, setFilters] = useState<TaskFilters>({ status: "", ownerId: "", risk: "", slaStatus: "" });
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState<"permission" | "offline" | "unavailable" | null>(null);
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [conflict, setConflict] = useState(false);
  const [reason, setReason] = useState("");
  const [executorKind, setExecutorKind] = useState<ExecutorKind>("person");
  const createKey = useRef(crypto.randomUUID());
  const requestSequence = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);

  const loadTasks = useCallback(async ({ preserveFeedback = false }: { preserveFeedback?: boolean } = {}) => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    const sequence = ++requestSequence.current;
    setState("loading");
    setLoadError(null);
    if (!preserveFeedback) setFeedback("");
    try {
      if (mode === "detail" && taskId) {
        const task = await responseJson<Task>(await fetch(`/api/tasks/${encodeURIComponent(taskId)}`, { cache: "no-store", signal: controller.signal }));
        if (sequence !== requestSequence.current) return;
        setTasks([task]);
        setConflict(false);
        setState("ready");
        return;
      }
      const query = new URLSearchParams();
      if (filters.status) query.set("status", filters.status);
      if (filters.ownerId) query.set("ownerId", filters.ownerId);
      if (filters.risk) query.set("risk", filters.risk);
      if (filters.slaStatus) query.set("slaStatus", filters.slaStatus);
      const page = await responseJson<TaskPage>(await fetch(`/api/tasks${query.size ? `?${query.toString()}` : ""}`, { cache: "no-store", signal: controller.signal }));
      if (sequence !== requestSequence.current) return;
      setTasks(page.items);
      setConflict(false);
      setState("ready");
    } catch (error) {
      if (controller.signal.aborted || sequence !== requestSequence.current) return;
      setTasks([]);
      setState("error");
      setLoadError(error instanceof ResponseError && error.status === 403 ? "permission" : navigator.onLine === false ? "offline" : "unavailable");
      setFeedback(error instanceof Error ? error.message : "Não foi possível carregar as tarefas.");
    }
  }, [filters, mode, taskId]);

  useEffect(() => {
    if (mode === "create") return;
    void loadTasks();
    return () => activeRequest.current?.abort();
  }, [loadTasks, mode]);

  useEffect(() => {
    if (mode === "create") return;
    const onRealtime = (event: Event) => {
      const detail = (event as CustomEvent<WorkspaceRealtimeEvent>).detail;
      if (detail?.table === "tasks") void loadTasks({ preserveFeedback: true });
    };
    window.addEventListener("bighead:realtime-event", onRealtime);
    return () => window.removeEventListener("bighead:realtime-event", onRealtime);
  }, [loadTasks, mode]);

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setFeedback("");
    const form = new FormData(event.currentTarget);
    const slaAt = form.get("slaAt");
    try {
      const result = await responseJson<{ task: Task; replayed?: boolean }>(await fetch("/api/tasks", {
        method: "POST",
        headers: { "content-type": "application/json", "Idempotency-Key": createKey.current },
        body: JSON.stringify({
          title: form.get("title"), goal: form.get("goal"), risk: form.get("risk"),
          assigneeId: form.get("assigneeId") || null,
          roomId: contextRoomId || null, sourceMessageId: contextMessageId || null,
          slaAt: localDateTimeToIso(typeof slaAt === "string" ? slaAt : ""), dependencies: []
        })
      }));
      createKey.current = crypto.randomUUID();
      router.push(`/tarefas/detalhe?taskId=${encodeURIComponent(result.task.id)}`);
    } catch (error) { setFeedback(error instanceof Error ? error.message : "Não foi possível criar a tarefa."); }
    finally { setPending(false); }
  }

  async function transition(event: FormEvent<HTMLFormElement>, task: Task) {
    event.preventDefault();
    setPending(true);
    setConflict(false);
    setFeedback("");
    const form = new FormData(event.currentTarget);
    const result = await transitionTask(form);
    setPending(false);
    setFeedback(result.message);
    if (result.status === 409) { setConflict(true); return; }
    if (!result.ok) return;
    const nextStatus = typeof result.data?.status === "string" ? result.data.status as TaskStatus : task.status;
    const nextVersion = typeof result.data?.version === "number" ? result.data.version : task.version;
    setTasks((current) => current.map((item) => item.id === task.id ? { ...item, status: nextStatus, version: nextVersion } : item));
    setReason("");
  }

  if (mode === "create") return (
    <section className={styles.page} aria-labelledby="create-task-title">
      <header className={styles.heading}><div><span>Tarefas</span><h1 id="create-task-title">Criar tarefa</h1><p>Defina o objetivo e mantenha o contexto de origem quando disponível.</p></div></header>
      {feedback ? <p className={styles.feedback} role="status">{feedback}</p> : null}
      <form className={styles.createForm} onSubmit={(event) => { void createTask(event); }}>
        <label>Título<input maxLength={240} name="title" /></label>
        <label>Objetivo<textarea maxLength={10000} name="goal" required /></label>
        <div className={styles.formRow}><label>Risco<select defaultValue="low" name="risk"><option value="low">Baixo</option><option value="medium">Médio</option><option value="high">Alto</option><option value="critical">Crítico</option></select></label><label>SLA opcional (horário local)<input name="slaAt" type="datetime-local" /></label></div>
        <div className={styles.formRow}><label>Executor<select aria-label="Tipo de executor" value={executorKind} onChange={(event) => setExecutorKind(event.target.value as ExecutorKind)}><option value="person">Pessoa</option><option value="agent">Agente</option><option value="team">Time</option></select></label><label>{executorKind === "person" ? "Responsável" : executorKind === "agent" ? "Agente executor" : "Time executor"}<input aria-label="Executor da tarefa" name="assigneeId" placeholder={executorKind === "team" ? "ID do time" : executorKind === "agent" ? "ID do agente" : "ID da pessoa"} /></label></div>
        <p className={styles.helper}>Executor pode ser pessoa, agente ou time. Campo grava `assigneeId`.</p>
        {contextRoomId || contextMessageId ? <div className={styles.context}><strong>Contexto vinculado</strong><span>{contextRoomId ? "Sala de origem preservada" : null}{contextRoomId && contextMessageId ? " · " : null}{contextMessageId ? "Mensagem de origem preservada" : null}</span></div> : null}
        <Button disabled={pending} type="submit">{pending ? "Criando..." : "Criar tarefa"}</Button>
      </form>
    </section>
  );

  if (mode === "inbox") return (
    <section className={styles.page} aria-labelledby="tasks-title">
      <header className={styles.heading}><div><span>Trabalho</span><h1 id="tasks-title">Tarefas</h1><p>Acompanhe o estado do trabalho na organização atual.</p></div><Link href="/tarefas/criar">Criar tarefa</Link></header>
      <form className={styles.filters} onSubmit={(event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        const ownerId = form.get("ownerId");
        const risk = form.get("risk");
        const slaStatus = form.get("slaStatus");
        setFilters((current) => ({
          ...current,
          ownerId: typeof ownerId === "string" ? ownerId.trim() : "",
          risk: typeof risk === "string" ? risk : "",
          slaStatus: typeof slaStatus === "string" ? slaStatus : ""
        }));
      }}>
        <label>Estado<select onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value as TaskStatus | "" }))} value={filters.status}>{statusOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
        <label>Responsável<input defaultValue={filters.ownerId} name="ownerId" placeholder="ID do responsável" /></label>
        <label>Risco<select defaultValue={filters.risk} name="risk"><option value="">Todos</option><option value="low">Baixo</option><option value="medium">Médio</option><option value="high">Alto</option><option value="critical">Crítico</option></select></label>
        <label>SLA<select defaultValue={filters.slaStatus} name="slaStatus"><option value="">Todos</option><option value="overdue">Atrasado</option><option value="upcoming">Próximo</option><option value="none">Sem SLA</option></select></label>
        <Button type="submit">Aplicar filtros</Button>
      </form>
      {feedback ? <p className={styles.feedback} role="status">{feedback}</p> : null}
      {state === "loading" ? <div className={styles.empty}>Carregando tarefas...</div> : null}
      {state === "ready" ? <div className={styles.taskList}>{tasks.map((task) => <Link href={`/tarefas/detalhe?taskId=${encodeURIComponent(task.id)}`} key={task.id} prefetch={false}><span><strong>{task.title}</strong><small>{task.objective}</small></span><span><em>{statusLabel(task.status)}</em><small>{dateLabel(task.dueAt ?? task.slaAt)}</small></span></Link>)}{tasks.length === 0 ? <div className={styles.empty}><strong>Nenhuma tarefa neste estado</strong><Link href="/tarefas/criar">Criar tarefa</Link></div> : null}</div> : null}
    </section>
  );

  const task = tasks.find((item) => item.id === taskId);
  if (!taskId) return <section className={styles.page}><div className={styles.empty}><strong>Selecione uma tarefa</strong><Link href="/tarefas/inbox">Voltar para tarefas</Link></div></section>;
  if (state === "loading") return <section className={styles.page}><div className={styles.empty}>Carregando tarefa...</div></section>;
  if (state === "error") return <section className={styles.page}><div className={styles.empty}><strong>{loadError === "permission" ? "Acesso negado" : loadError === "offline" ? "Você está offline" : "Tarefas indisponíveis"}</strong><span>{feedback}</span><Button onClick={() => { void loadTasks(); }} type="button">Tentar novamente</Button><Link href="/tarefas/inbox">Voltar para tarefas</Link></div></section>;
  if (!task) return <section className={styles.page}><div className={styles.empty}><strong>Tarefa não encontrada</strong><span>O detalhe não está disponível na página atual.</span><Button onClick={() => { void loadTasks(); }} type="button">Recarregar</Button><Link href="/tarefas/inbox">Voltar para tarefas</Link></div></section>;
  const transitions = allowedTaskTransitions(task.status);
  return (
    <section className={styles.page} aria-labelledby="task-detail-title">
      <header className={styles.heading}><div><Link href="/tarefas/inbox">Tarefas</Link><h1 id="task-detail-title">{task.title}</h1><p>{task.objective}</p></div><em>{statusLabel(task.status)}</em></header>
      {feedback ? <p className={styles.feedback} role="status">{feedback}</p> : null}
      <div className={styles.detailGrid}>
        <div className={styles.taskDetail}><dl><div><dt>Risco</dt><dd>{riskLabel(task.riskLevel)}</dd></div><div><dt>Prioridade</dt><dd>{task.priority}</dd></div><div><dt>Prazo</dt><dd>{dateLabel(task.dueAt)}</dd></div><div><dt>SLA</dt><dd>{dateLabel(task.slaAt)}</dd></div><div><dt>Responsável</dt><dd>{task.assigneeId ? "Atribuído" : "Não atribuído"}</dd></div><div><dt>Versão</dt><dd>{task.version}</dd></div></dl>{task.roomId ? <Link href={`/colaboracao/sala?roomId=${encodeURIComponent(task.roomId)}${task.sourceMessageId ? `&messageId=${encodeURIComponent(task.sourceMessageId)}` : ""}`}>Abrir conversa de origem</Link> : null}</div>
        <form className={styles.transition} onSubmit={(event) => { void transition(event, task); }}>
          <h2>Atualizar estado</h2><input name="taskId" type="hidden" value={task.id} /><input name="expectedVersion" type="hidden" value={task.version} />
          <label>Próximo estado<select disabled={!transitions.length} name="targetState" defaultValue={transitions[0]}>{transitions.map((item) => <option key={item} value={item}>{statusLabel(item)}</option>)}</select></label>
          <label>Motivo<textarea maxLength={4000} name="reason" onChange={(event) => setReason(event.target.value)} value={reason} /></label>
          <Button disabled={pending || !transitions.length} type="submit">{pending ? "Atualizando..." : "Confirmar alteração"}</Button>
          {conflict ? <Button className={styles.secondary} onClick={() => { void loadTasks(); }} tone="secondary" type="button">Recarregar tarefa</Button> : null}
        </form>
      </div>
    </section>
  );
}
