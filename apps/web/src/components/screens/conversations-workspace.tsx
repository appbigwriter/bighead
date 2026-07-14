"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Button } from "@bighead/ui";

import { reconcileRealtimeMessages, type RealtimeMessage } from "@/lib/message-reconciliation";
import type { WorkspaceRealtimeEvent } from "@/lib/realtime-protocol";
import styles from "./conversations-workspace.module.css";

type Room = { id: string; name: string; description?: string | null; isPrivate: boolean; createdAt: string };
type RoomPage = { rooms: Room[]; counters?: Record<string, number>; nextCursor?: string | null };
type RoomContext = { id: string; name: string; description?: string | null; isPrivate: boolean; createdAt: string };
type FileItem = { id: string; name: string; kind: string; quarantineStatus: string; createdAt: string };
type MessagePage = { messages: RealtimeMessage[]; roomContext?: RoomContext | null };
type RoomMember = { userId: string; isModerator: boolean };
type RoomMemberPage = { room: RoomContext; members: RoomMember[] };
type RoomTask = { id: string; title: string; status: string };

class ResponseError extends Error {
  constructor(public readonly status: number, message: string) { super(message); }
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

async function json<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({})) as T & { detail?: unknown };
  if (!response.ok) throw new ResponseError(response.status, typeof payload.detail === "string" ? payload.detail : "Operacao nao concluida.");
  return payload;
}

function authorLabel(message: RealtimeMessage) {
  const type = message.metadata?.authorType ?? message.metadata?.author_type;
  const name = message.metadata?.authorName ?? message.metadata?.author_name;
  if (typeof name === "string" && name.trim()) return name;
  if (type === "agent") return "Agente";
  if (type === "system" || !message.authorUserId) return "Sistema";
  return "Membro";
}

function messageStatus(message: RealtimeMessage) {
  if (message.pending) return "Enviando";
  if (message.deletedAt) return "Removida";
  if (message.editedAt) return "Editada";
  return "Enviada";
}

function timeLabel(value: string) {
  const instant = new Date(value);
  return Number.isNaN(instant.getTime()) ? "Horario indisponivel" : new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" }).format(instant);
}

export function ConversationsWorkspace({ mode }: { mode: "list" | "room" }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const [rooms, setRooms] = useState<Room[]>([]);
  const [counters, setCounters] = useState<Record<string, number>>({});
  const [messages, setMessages] = useState<RealtimeMessage[]>([]);
  const [room, setRoom] = useState<RoomContext | null>(null);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [members, setMembers] = useState<RoomMember[]>([]);
  const [roomTasks, setRoomTasks] = useState<RoomTask[]>([]);
  const [draft, setDraft] = useState("");
  const [online, setOnline] = useState(true);
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState("");
  const [roomState, setRoomState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [fileState, setFileState] = useState<"idle" | "loading" | "ready" | "denied" | "unavailable">("idle");
  const [memberState, setMemberState] = useState<"idle" | "loading" | "ready" | "unavailable">("idle");
  const [taskState, setTaskState] = useState<"idle" | "loading" | "ready" | "unavailable">("idle");
  const [realtimeAnnouncement, setRealtimeAnnouncement] = useState("");
  const requestSequence = useRef(0);

  const loadRooms = useCallback(async () => {
    const page = await json<RoomPage>(await fetch("/api/rooms", { cache: "no-store" }));
    setRooms(page.rooms);
    setCounters(page.counters ?? {});
  }, []);

  const loadRoom = useCallback(async (selectedRoomId: string, options: { reset?: boolean } = {}) => {
    const sequence = ++requestSequence.current;
    if (options.reset) {
      setMessages([]);
      setRoom(null);
      setFiles([]);
      setMembers([]);
      setRoomTasks([]);
      setRoomState("loading");
      setFileState("loading");
      setMemberState("loading");
      setTaskState("loading");
    }
    const [messageResult, fileResult, memberResult, taskResult] = await Promise.allSettled([
      fetch(`/api/rooms/${encodeURIComponent(selectedRoomId)}/messages`, { cache: "no-store" }).then((response) => json<MessagePage>(response)),
      fetch(`/api/rooms/${encodeURIComponent(selectedRoomId)}/files`, { cache: "no-store" }).then((response) => json<{ files: FileItem[] }>(response)),
      fetch(`/api/rooms/${encodeURIComponent(selectedRoomId)}/members`, { cache: "no-store" }).then((response) => json<RoomMemberPage>(response)),
      fetch(`/api/tasks?roomId=${encodeURIComponent(selectedRoomId)}`, { cache: "no-store" }).then((response) => json<{ items: RoomTask[] }>(response))
    ]);
    if (sequence !== requestSequence.current) return;
    if (fileResult.status === "fulfilled") {
      setFiles(fileResult.value.files);
      setFileState("ready");
    } else {
      setFiles([]);
      setFileState(fileResult.reason instanceof ResponseError && fileResult.reason.status === 403 ? "denied" : "unavailable");
    }
    if (memberResult.status === "fulfilled") {
      setMembers(memberResult.value.members);
      setMemberState("ready");
    } else {
      setMembers([]);
      setMemberState("unavailable");
    }
    if (taskResult.status === "fulfilled") {
      setRoomTasks(taskResult.value.items);
      setTaskState("ready");
    } else {
      setRoomTasks([]);
      setTaskState("unavailable");
    }
    if (messageResult.status === "fulfilled") {
      setMessages((current) => reconcileRealtimeMessages(current.filter((item) => item.roomId === selectedRoomId && item.pending), messageResult.value.messages));
      setRoom(messageResult.value.roomContext ?? null);
      setRoomState("ready");
    } else {
      setMessages([]);
      setRoom(null);
      setFiles([]);
      setMembers([]);
      setRoomTasks([]);
      setFileState("idle");
      setMemberState("idle");
      setTaskState("idle");
      setRoomState("error");
      throw messageResult.reason;
    }
  }, []);

  useEffect(() => {
    void loadRooms().catch((error: unknown) => setStatus(errorMessage(error, "Nao foi possivel carregar as salas.")));
  }, [loadRooms]);

  useEffect(() => {
    if (mode !== "room" || !roomId) return;
    setStatus("");
    void loadRoom(roomId, { reset: true }).catch((error: unknown) => setStatus(errorMessage(error, "Nao foi possivel abrir a conversa.")));
  }, [loadRoom, mode, roomId]);

  useEffect(() => {
    setOnline(navigator.onLine !== false);
    const key = roomId ? `bighead:draft:${roomId}` : "";
    if (key) setDraft(localStorage.getItem(key) ?? "");
    const onOffline = () => setOnline(false);
    const onOnline = () => {
      setOnline(true);
      if (roomId) void loadRoom(roomId).catch((error: unknown) => setStatus(errorMessage(error, "Nao foi possivel atualizar a conversa.")));
    };
    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    return () => {
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
    };
  }, [roomId]);

  useEffect(() => {
    if (mode !== "room" || !roomId) return;
    const onRealtime = (event: Event) => {
      const detail = (event as CustomEvent<WorkspaceRealtimeEvent>).detail;
      if (detail?.table === "messages") void loadRoom(roomId)
        .then(() => setRealtimeAnnouncement("Conversa atualizada com novas mensagens."))
        .catch(() => undefined);
    };
    window.addEventListener("bighead:realtime-event", onRealtime);
    return () => window.removeEventListener("bighead:realtime-event", onRealtime);
  }, [loadRoom, mode, roomId]);

  function updateDraft(value: string) {
    setDraft(value);
    if (roomId) localStorage.setItem(`bighead:draft:${roomId}`, value);
  }

  async function createRoom(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setStatus("");
    const form = new FormData(event.currentTarget);
    try {
      const created = await json<Room>(await fetch("/api/rooms", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: form.get("name"), description: form.get("description"), isPrivate: form.get("isPrivate") === "on" })
      }));
      await loadRooms();
      router.push(`/colaboracao/sala?roomId=${encodeURIComponent(created.id)}`);
    } catch (error) { setStatus(errorMessage(error, "Nao foi possivel criar a sala.")); }
    finally { setPending(false); }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = draft.trim();
    if (!body || !roomId || !online) return;
    const clientId = crypto.randomUUID();
    const optimistic: RealtimeMessage = { id: `pending-${clientId}`, roomId, clientId, authorUserId: "local", body, metadata: { authorName: "Você", authorType: "human" }, createdAt: new Date().toISOString(), pending: true };
    setMessages((current) => reconcileRealtimeMessages(current, [optimistic]));
    setPending(true);
    setStatus("");
    try {
      const persisted = await json<RealtimeMessage>(await fetch(`/api/rooms/${encodeURIComponent(roomId)}/messages`, {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ body, clientId })
      }));
      setMessages((current) => reconcileRealtimeMessages(current, [{ ...persisted, pending: false }]));
      updateDraft("");
      setStatus("Mensagem enviada.");
    } catch (error) {
      setMessages((current) => current.filter((item) => item.clientId !== clientId));
      setStatus(errorMessage(error, "Nao foi possivel enviar. Seu rascunho foi preservado."));
    } finally { setPending(false); }
  }

  if (mode === "list") return (
    <section className={styles.page} aria-labelledby="rooms-title">
      <header className={styles.heading}><div><span>Conversas</span><h1 id="rooms-title">Salas</h1><p>Acompanhe os espaços de trabalho disponíveis para sua organização.</p></div><strong>{counters.total ?? rooms.length} salas</strong></header>
      {status ? <p className={styles.feedback} role="status">{status}</p> : null}
      <div className={styles.roomsLayout}>
        <div className={styles.roomList} aria-label="Salas disponíveis">
          {rooms.map((item) => <Link href={`/colaboracao/sala?roomId=${encodeURIComponent(item.id)}`} key={item.id} prefetch={false}><span><strong>{item.name}</strong><small>{item.description || "Sem descrição"}</small></span><em>{item.isPrivate ? "Privada" : "Aberta"}</em></Link>)}
          {rooms.length === 0 ? <div className={styles.empty}><strong>Nenhuma sala disponível</strong><span>Crie a primeira sala para iniciar uma conversa.</span></div> : null}
        </div>
        <form className={styles.createRoom} onSubmit={(event) => { void createRoom(event); }}>
          <h2>Criar sala</h2>
          <label>Nome<input maxLength={160} name="name" required /></label>
          <label>Descrição<textarea maxLength={2000} name="description" /></label>
          <label className={styles.check}><input name="isPrivate" type="checkbox" /> Somente convidados</label>
          <Button disabled={pending} type="submit">{pending ? "Criando..." : "Criar e abrir"}</Button>
        </form>
      </div>
    </section>
  );

  if (!roomId) return <section className={styles.page}><div className={styles.empty}><strong>Selecione uma sala</strong><span>Abra uma sala para acompanhar mensagens e arquivos.</span><Link href="/colaboracao/salas">Ver salas</Link></div></section>;

  const visibleMessages = messages.filter((message) => message.roomId === roomId);

  return (
    <section className={styles.conversation} aria-labelledby="conversation-title">
      <header className={styles.conversationHeader}><div><Link href="/colaboracao/salas">Salas</Link><h1 id="conversation-title">{room?.name ?? "Conversa"}</h1></div><span>{online ? "Online" : "Offline · rascunho salvo"}</span></header>
      <div className={styles.conversationGrid}>
        <div className={styles.timelineColumn}>
          <p className={styles.srOnly} aria-live="polite">{realtimeAnnouncement}</p>
          {status ? <p className={styles.feedback} role="status">{status}</p> : null}
          {roomState === "loading" ? <div className={styles.empty}><strong>Carregando conversa...</strong><span>Buscando o contexto desta sala.</span></div> : null}
          {roomState === "error" ? <div className={styles.empty}><strong>Conversa indisponivel</strong><span>Verifique seu acesso ou escolha outra sala.</span><Link href="/colaboracao/salas">Voltar para salas</Link></div> : null}
          <div aria-label="Mensagens da sala" className={styles.timeline} role="log">
            {visibleMessages.map((message) => (
              <article data-client-id={message.clientId} data-message-id={message.id} key={message.id}>
                <div><strong>{authorLabel(message)}</strong><time dateTime={message.createdAt}>{timeLabel(message.createdAt)}</time></div>
                <p>{message.deletedAt ? "Mensagem removida" : message.body}</p>
                <small>{messageStatus(message)}</small>
              </article>
            ))}
            {roomState === "ready" && visibleMessages.length === 0 ? <div className={styles.empty}><strong>Comece a conversa</strong><span>Envie a primeira mensagem para esta sala.</span></div> : null}
          </div>
          <form className={styles.composer} onSubmit={(event) => { void sendMessage(event); }}>
            <label htmlFor="conversation-draft">Mensagem</label>
            <textarea id="conversation-draft" maxLength={100000} onChange={(event) => updateDraft(event.target.value)} placeholder="Escreva uma mensagem" value={draft} />
            <div><span>{!online ? "O rascunho será mantido neste dispositivo." : "Seu rascunho fica salvo neste dispositivo."}</span><Button disabled={pending || !online || roomState !== "ready" || !draft.trim()} type="submit">{pending ? "Enviando..." : "Enviar"}</Button></div>
          </form>
        </div>
        <aside className={styles.inspector} aria-label="Contexto da sala">
          <section><h2>Sobre</h2><p>{room?.description || "Sem descrição."}</p><span>{room?.isPrivate ? "Sala privada" : "Sala aberta"}</span></section>
          <section><h2>Membros</h2>
            {memberState === "loading" ? <p>Carregando membros...</p> : null}
            {memberState === "unavailable" ? <p>Membros temporariamente indisponíveis.</p> : null}
            {memberState === "ready" && members.length ? <ul>{members.map((member) => <li key={member.userId}><strong>{member.userId}</strong><span>{member.isModerator ? "Moderador" : "Membro"}</span></li>)}</ul> : null}
            {memberState === "ready" && members.length === 0 ? <p>Nenhum membro nesta sala.</p> : null}
          </section>
          <section><h2>Tarefas</h2>
            {taskState === "loading" ? <p>Carregando tarefas...</p> : null}
            {taskState === "unavailable" ? <p>Tarefas temporariamente indisponíveis.</p> : null}
            {taskState === "ready" && roomTasks.length ? <ul>{roomTasks.map((task) => <li key={task.id}><Link href={`/tarefas/detalhe?taskId=${encodeURIComponent(task.id)}`}><strong>{task.title}</strong><span>{task.status.replaceAll("_", " ")}</span></Link></li>)}</ul> : null}
            {taskState === "ready" && roomTasks.length === 0 ? <p>Nenhuma tarefa vinculada.</p> : null}
          </section>
          <section><h2>Arquivos</h2>
            {fileState === "loading" ? <p>Carregando arquivos...</p> : null}
            {fileState === "denied" ? <p>Voce nao tem permissao para ver os arquivos desta sala.</p> : null}
            {fileState === "unavailable" ? <p>Arquivos temporariamente indisponiveis.</p> : null}
            {fileState === "ready" && files.length ? <ul>{files.map((file) => <li key={file.id}><strong>{file.name}</strong><span>{file.quarantineStatus === "clean" ? "Disponível" : "Em análise"}</span></li>)}</ul> : null}
            {fileState === "ready" && files.length === 0 ? <p>Nenhum arquivo nesta sala.</p> : null}
          </section>
        </aside>
      </div>
    </section>
  );
}
