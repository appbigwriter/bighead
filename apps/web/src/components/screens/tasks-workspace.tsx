"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { allowedTaskTransitions, type TaskStatus } from "@/lib/task-transitions";
import { transitionTask } from "@/lib/transition-task-client";
import styles from "./tasks-workspace.module.css";

type Task = {
  id: string; roomId?: string | null; sourceMessageId?: string | null; title: string; objective: string;
  status: TaskStatus; priority: number; riskLevel: string; requesterId?: string | null; assigneeId?: string | null;
  dueAt?: string | null; slaAt?: string | null; version: number; createdAt: string; updatedAt: string;
};
type TaskPage = { items: Task[]; nextCursor?: string | null };

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
  const [filter, setFilter] = useState<TaskStatus | "">("");
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState<"permission" | "offline" | "unavailable" | null>(null);
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [conflict, setConflict] = useState(false);
  const [reason, setReason] = useState("");
  const createKey = useRef(crypto.randomUUID());
  const requestSequence = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);

  const loadTasks = useCallback(async (selectedStatus: TaskStatus | "" = "") => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    const sequence = ++requestSequence.current;
    setState("loading");
    setLoadError(null);
    setFeedback("");
    try {
      const query = selectedStatus ? `?status=${encodeURIComponent(selectedStatus)}` : "";
      const page = await responseJson<TaskPage>(await fetch(`/api/tasks${query}`, { cache: "no-store", signal: controller.signal }));
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
  }, []);

  useEffect(() => {
    if (mode === "create") return;
    void loadTasks(filter);
    return () => activeRequest.current?.abort();
  }, [filter, loadTasks, mode]);

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
        {contextRoomId || contextMessageId ? <div className={styles.context}><strong>Contexto vinculado</strong><span>{contextRoomId ? "Sala de origem preservada" : null}{contextRoomId && contextMessageId ? " · " : null}{contextMessageId ? "Mensagem de origem preservada" : null}</span></div> : null}
        <button disabled={pending} type="submit">{pending ? "Criando..." : "Criar tarefa"}</button>
      </form>
    </section>
  );

  if (mode === "inbox") return (
    <section className={styles.page} aria-labelledby="tasks-title">
      <header className={styles.heading}><div><span>Trabalho</span><h1 id="tasks-title">Tarefas</h1><p>Acompanhe o estado do trabalho na organização atual.</p></div><Link href="/tarefas/criar">Criar tarefa</Link></header>
      <div className={styles.filters}><label>Estado<select onChange={(event) => setFilter(event.target.value as TaskStatus | "")} value={filter}>{statusOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label><div aria-label="Filtros ainda indisponíveis"><button disabled>Responsável</button><button disabled>Risco</button><button disabled>SLA</button><span>Filtros adicionais aguardam disponibilidade.</span></div></div>
      {feedback ? <p className={styles.feedback} role="status">{feedback}</p> : null}
      {state === "loading" ? <div className={styles.empty}>Carregando tarefas...</div> : null}
      {state === "ready" ? <div className={styles.taskList}>{tasks.map((task) => <Link href={`/tarefas/detalhe?taskId=${encodeURIComponent(task.id)}`} key={task.id} prefetch={false}><span><strong>{task.title}</strong><small>{task.objective}</small></span><span><em>{statusLabel(task.status)}</em><small>{dateLabel(task.dueAt ?? task.slaAt)}</small></span></Link>)}{tasks.length === 0 ? <div className={styles.empty}><strong>Nenhuma tarefa neste estado</strong><Link href="/tarefas/criar">Criar tarefa</Link></div> : null}</div> : null}
    </section>
  );

  const task = tasks.find((item) => item.id === taskId);
  if (!taskId) return <section className={styles.page}><div className={styles.empty}><strong>Selecione uma tarefa</strong><Link href="/tarefas/inbox">Voltar para tarefas</Link></div></section>;
  if (state === "loading") return <section className={styles.page}><div className={styles.empty}>Carregando tarefa...</div></section>;
  if (state === "error") return <section className={styles.page}><div className={styles.empty}><strong>{loadError === "permission" ? "Acesso negado" : loadError === "offline" ? "Você está offline" : "Tarefas indisponíveis"}</strong><span>{feedback}</span><button onClick={() => { void loadTasks(); }} type="button">Tentar novamente</button><Link href="/tarefas/inbox">Voltar para tarefas</Link></div></section>;
  if (!task) return <section className={styles.page}><div className={styles.empty}><strong>Tarefa não encontrada</strong><span>O detalhe não está disponível na página atual.</span><button onClick={() => { void loadTasks(); }} type="button">Recarregar</button><Link href="/tarefas/inbox">Voltar para tarefas</Link></div></section>;
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
          <button disabled={pending || !transitions.length} type="submit">{pending ? "Atualizando..." : "Confirmar alteração"}</button>
          {conflict ? <button className={styles.secondary} onClick={() => { void loadTasks(); }} type="button">Recarregar tarefa</button> : null}
        </form>
      </div>
    </section>
  );
}
