"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

import { Card } from "@bighead/ui";
import {
  createContentAsset,
  confirmArtifact,
  createMessage,
  createRoom,
  createTask,
  decideApproval,
  initiateArtifact,
  scheduleExperiment,
  switchTenant,
  transitionTask,
  type MutationResult
} from "@/app/actions/critical-mutations";
import type { WorkspaceSnapshot } from "@/lib/mock-workspace";
import type { ScreenCode } from "@/lib/screen-catalog";
import { mutationFailure } from "@/lib/mutation-result";
import { putSignedUpload, sha256Hex } from "@/lib/signed-upload";
import { visibleRoomsForMember } from "@/lib/room-visibility";
import { createTimelineFixtures, VirtualTimeline } from "./virtual-timeline";

const timelineFixtures = createTimelineFixtures(5_000);

export const criticalJourneyCodes = new Set<ScreenCode>(["T05", "T10", "T11", "T13", "T15", "T16", "T21", "T44", "T47"]);

type Action = (form: FormData) => Promise<MutationResult>;

export function CriticalJourney({ code, snapshot }: { code: ScreenCode; snapshot: WorkspaceSnapshot }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<MutationResult | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());

  const submit = (action: Action) => (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    void (async () => {
      try {
        const next = await action(form);
        setFeedback(next);
        if (next.ok) {
          setIdempotencyKey(crypto.randomUUID());
          router.refresh();
        }
      } finally {
        setPending(false);
      }
    })();
  };
  const organizationId = snapshot.currentOrganizationId ?? snapshot.organizationOptions[0]?.id ?? "";
  const visibleRooms = visibleRoomsForMember(snapshot.roomOptions);
  const submitUpload = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const fileInput = event.currentTarget.elements.namedItem("file");
    const file = fileInput instanceof HTMLInputElement ? fileInput.files?.[0] : undefined;
    if (!file) { setFeedback({ ok: false, status: 422, message: "Selecione um arquivo." }); return; }
    setPending(true);
    void (async () => {
      try {
        const checksum = await sha256Hex(file);
        const metadata = new FormData();
        metadata.set("organizationId", organizationId); metadata.set("filename", file.name);
        metadata.set("mimeType", file.type || "application/octet-stream"); metadata.set("sizeBytes", String(file.size));
        metadata.set("checksumSha256", checksum);
        const initiated = await initiateArtifact(metadata);
        if (!initiated.ok) { setFeedback(initiated); return; }
        const artifactId = initiated.data?.artifactId;
        const uploadUrl = initiated.data?.uploadUrl;
        const rawHeaders = initiated.data?.requiredHeaders;
        if (typeof artifactId !== "string" || typeof uploadUrl !== "string" || !rawHeaders || typeof rawHeaders !== "object" || Array.isArray(rawHeaders)) {
          setFeedback(mutationFailure(502, "Resposta de assinatura invalida.")); return;
        }
        const requiredHeaders = Object.fromEntries(Object.entries(rawHeaders).filter((entry): entry is [string, string] => typeof entry[1] === "string"));
        const storageFailure = await putSignedUpload(uploadUrl, requiredHeaders, file);
        if (storageFailure) { setFeedback(storageFailure); return; }
        const confirmation = new FormData();
        confirmation.set("organizationId", organizationId); confirmation.set("artifactId", artifactId); confirmation.set("checksumSha256", checksum);
        const confirmed = await confirmArtifact(confirmation);
        setFeedback(confirmed);
        if (confirmed.ok) router.refresh();
      } catch (error) {
        setFeedback({ ok: false, status: 422, message: error instanceof Error ? error.message : "Arquivo invalido." });
      } finally {
        setPending(false);
      }
    })();
  };
  const status = (
    <div className={`bh-state-panel ${feedback && !feedback.ok ? "bh-state-panel-risk" : ""}`} role="status" data-testid="mutation-feedback">
      <strong>{pending ? "Processando" : feedback?.ok ? "Concluido" : feedback ? `Falha HTTP ${feedback.status}` : "Pronto"}</strong>
      <p>{pending ? "A operacao esta sendo confirmada no backend." : feedback?.message ?? "Preencha os dados e confirme a operacao."}</p>
    </div>
  );
  const hiddenOrganization = <input name="organizationId" type="hidden" value={organizationId} />;

  if (code === "T05") return (
    <Journey title="Trocar organizacao" status={status}>
      <form onSubmit={submit(switchTenant)} className="bh-form-grid">
        <label className="bh-field"><span>Organizacao</span><select name="organizationId" defaultValue={organizationId}>{snapshot.organizationOptions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <Submit pending={pending}>Trocar tenant</Submit>
      </form>
    </Journey>
  );

  if (code === "T10") return (
    <Journey title="Criar sala" status={status}>
      <div aria-label="Salas visiveis" className="bh-state-panel">
        <strong>{visibleRooms.counters.total} salas · {visibleRooms.counters.unread} nao lidas</strong>
        <ul className="bh-list">{visibleRooms.items.map((room) => <li key={room.id}>{room.name}</li>)}</ul>
      </div>
      <form onSubmit={submit(createRoom)} className="bh-form-grid">
        {hiddenOrganization}
        <label className="bh-field"><span>Nome</span><input name="name" required maxLength={160} defaultValue="Sala criada pela interface" /></label>
        <label className="bh-field"><span>Descricao</span><textarea name="description" maxLength={2000} /></label>
        <label className="bh-field"><span><input name="isPrivate" type="checkbox" /> Sala privada</span></label>
        <Submit pending={pending}>Criar sala</Submit>
      </form>
    </Journey>
  );

  if (code === "T11") return (
    <Journey title="Enviar mensagem" status={status}>
      <VirtualTimeline items={timelineFixtures} />
      <form onSubmit={submit(createMessage)} className="bh-form-grid">
        {hiddenOrganization}<input name="clientId" type="hidden" value={idempotencyKey} />
        <label className="bh-field"><span>Sala</span><select name="roomId" required>{snapshot.roomOptions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="bh-field"><span>Mensagem</span><textarea name="body" required maxLength={100000} aria-label="Nova mensagem real" /></label>
        <Submit pending={pending}>Enviar mensagem</Submit>
      </form>
    </Journey>
  );

  if (code === "T13") return (
    <Journey title="Upload assinado" status={status}>
      <form onSubmit={submitUpload} className="bh-form-grid">
        <label className="bh-field"><span>Arquivo</span><input name="file" type="file" required /></label>
        <Submit pending={pending}>Enviar e confirmar</Submit>
      </form>
    </Journey>
  );

  if (code === "T15") return (
    <Journey title="Criar tarefa" status={status}>
      <form onSubmit={submit(createTask)} className="bh-form-grid">
        {hiddenOrganization}<input name="idempotencyKey" type="hidden" value={idempotencyKey} />
        <label className="bh-field"><span>Titulo</span><input name="title" maxLength={240} defaultValue="Tarefa criada pela interface" /></label>
        <label className="bh-field"><span>Objetivo</span><textarea name="goal" required maxLength={10000} /></label>
        <label className="bh-field"><span>Risco</span><select name="risk" defaultValue="low"><option value="low">Baixo</option><option value="medium">Medio</option><option value="high">Alto</option></select></label>
        <label className="bh-field"><span>Sala de origem</span><select name="roomId"><option value="">Sem sala</option>{snapshot.roomOptions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <Submit pending={pending}>Criar tarefa</Submit>
      </form>
    </Journey>
  );

  if (code === "T16") {
    const task = snapshot.taskOptions[0];
    return (
      <Journey title="Transicionar tarefa" status={status}>
        <form onSubmit={submit(transitionTask)} className="bh-form-grid">
          {hiddenOrganization}
          <input name="taskId" type="hidden" value={task?.id ?? ""} />
          <p>{task?.name ?? "Nenhuma tarefa disponivel"}</p>
          <input name="expectedVersion" type="hidden" value={task?.version ?? 1} />
          <label className="bh-field"><span>Destino</span><select name="targetState" defaultValue="triaged"><option value="triaged">Triaged</option><option value="in_progress">Em andamento</option><option value="ready_for_review">Pronta para revisao</option></select></label>
          <label className="bh-field"><span>Motivo</span><textarea name="reason" maxLength={4000} /></label>
          <Submit pending={pending} disabled={!task}>Aplicar transicao</Submit>
        </form>
      </Journey>
    );
  }

  if (code === "T21") {
    const approval = snapshot.approvalOptions.find((item) => item.status === "pending");
    return (
      <Journey title="Decidir aprovacao" status={status}>
        <form onSubmit={submit(decideApproval)} className="bh-form-grid">
          {hiddenOrganization}<input name="approvalId" type="hidden" value={approval?.id ?? ""} /><input name="expectedRound" type="hidden" value={approval?.round ?? 1} />
          <label className="bh-field"><span>Decisao</span><select name="decision"><option value="approved">Aprovar</option><option value="changes_requested">Solicitar alteracoes</option><option value="rejected">Rejeitar</option></select></label>
          <label className="bh-field"><span>Comentario</span><textarea name="comment" maxLength={10000} /></label>
          <Submit pending={pending} disabled={!approval}>Registrar decisao</Submit>
        </form>
      </Journey>
    );
  }

  if (code === "T44") return (
    <Journey title="Criar conteudo" status={status}>
      <form onSubmit={submit(createContentAsset)} className="bh-form-grid">
        {hiddenOrganization}<input name="idempotencyKey" type="hidden" value={idempotencyKey} />
        <label className="bh-field"><span>Titulo</span><input name="title" maxLength={500} /></label>
        <label className="bh-field"><span>Briefing</span><textarea name="brief" required maxLength={20000} /></label>
        <label className="bh-field"><span>Canal</span><select name="channel"><option value="email">E-mail</option><option value="linkedin">LinkedIn</option></select></label>
        <Submit pending={pending}>Criar ativo</Submit>
      </form>
    </Journey>
  );

  const experiment = snapshot.experimentOptions.find((item) => item.status === "draft");
  return (
    <Journey title="Configurar e iniciar experimento" status={status}>
      <form onSubmit={submit(scheduleExperiment)} className="bh-form-grid">
        {hiddenOrganization}<input name="experimentId" type="hidden" value={experiment?.id ?? ""} /><input name="expectedUpdatedAt" type="hidden" value={experiment?.updatedAt ?? ""} />
        <label className="bh-field"><span>Hipotese</span><textarea name="hypothesis" required maxLength={10000} defaultValue={experiment?.name ?? "Hipotese configurada pela interface"} /></label>
        <Submit pending={pending} disabled={!experiment}>Configurar e iniciar</Submit>
        {!experiment ? <p>Nao ha experimento draft disponivel. Experimentos em execucao mantem hipotese e variantes bloqueadas.</p> : null}
      </form>
    </Journey>
  );
}

function Journey({ title, status, children }: { title: string; status: ReactNode; children: ReactNode }) {
  return <div className="bh-columns" data-testid="critical-journey"><Card><div className="bh-card-title"><h3>{title}</h3><span className="bh-label">persistencia real</span></div>{children}</Card><Card>{status}</Card></div>;
}

function Submit({ pending, disabled, children }: { pending: boolean; disabled?: boolean; children: ReactNode }) {
  return <button type="submit" disabled={pending || disabled} className="bh-chip">{pending ? "Processando..." : children}</button>;
}
