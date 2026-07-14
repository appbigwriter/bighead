"use client";

import type { components } from "@bighead/contracts";
import { Button } from "@bighead/ui";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import styles from "./commercial-workspace.module.css";

type LeadPage = components["schemas"]["LeadListResponse"];
type LeadDetail = components["schemas"]["LeadDetailResponse"];
type Pipeline = components["schemas"]["PipelineBoardResponse"];
type Opportunity = components["schemas"]["PipelineOpportunity"];
type Stage = "discovery" | "qualification" | "proposal" | "negotiation" | "won" | "lost";
type LoadState = "loading" | "ready" | "error";

const stageLabels: Record<string, string> = { discovery: "Descoberta", qualification: "Qualificacao", proposal: "Proposta", negotiation: "Negociacao", won: "Ganha", lost: "Perdida" };
const stages: Stage[] = ["discovery", "qualification", "proposal", "negotiation", "won", "lost"];

class ResponseError extends Error { constructor(public status: number, message: string) { super(message); } }
async function responseJson<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => ({})) as T & { detail?: unknown };
  if (!response.ok) throw new ResponseError(response.status, typeof body.detail === "string" ? body.detail : "Operacao nao concluida.");
  return body;
}
function dateLabel(value?: string | null) {
  if (!value) return "Nao definida";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Indisponivel" : new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(date);
}
function shortId(value?: string | null) { return value ? value.slice(0, 8) : "Nao atribuido"; }
function scoreLabel(value?: number | null) { return value == null ? "Sem score" : `${Math.round(value <= 1 ? value * 100 : value)}%`; }
function money(value: number, currency = "BRL") { return new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(value); }
function text(value: unknown) { return typeof value === "string" && value.trim() ? value : null; }
function timelineTitle(item: Record<string, unknown>) {
  if (text(item.action)) return text(item.action)!;
  if (text(item.signalType) === "follow_up" || text(item.type) === "follow_up") return "Follow-up criado";
  return text(item.type) ?? text(item.signalType) ?? "Atualizacao do lead";
}
function timelineDate(item: Record<string, unknown>) { return text(item.createdAt) ?? text(item.occurredAt) ?? text(item.at) ?? text(item.dueAt); }

export function CommercialWorkspace({ mode }: { mode: "leads" | "detail" | "pipeline" }) {
  const params = useSearchParams();
  const leadId = params.get("leadId") ?? "";
  const [state, setState] = useState<LoadState>("loading");
  const [leads, setLeads] = useState<LeadPage | null>(null);
  const [detail, setDetail] = useState<LeadDetail | null>(null);
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [stageFilter, setStageFilter] = useState("");
  const [feedback, setFeedback] = useState("");
  const [pending, setPending] = useState(false);
  const [selected, setSelected] = useState<Opportunity | null>(null);
  const [targetStage, setTargetStage] = useState<Stage>("qualification");
  const [action, setAction] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [notes, setNotes] = useState("");
  const followUpKey = useRef(globalThis.crypto.randomUUID());

  const load = useCallback(async () => {
    setState("loading"); setFeedback("");
    try {
      if (mode === "leads") {
        const query = stageFilter ? `?stage=${encodeURIComponent(stageFilter)}` : "";
        setLeads(await responseJson<LeadPage>(await fetch(`/api/commercial/leads${query}`, { cache: "no-store" })));
      } else if (mode === "detail") {
        if (!leadId) { setState("ready"); return; }
        setDetail(await responseJson<LeadDetail>(await fetch(`/api/commercial/leads/${encodeURIComponent(leadId)}`, { cache: "no-store" })));
      } else setPipeline(await responseJson<Pipeline>(await fetch("/api/commercial/pipeline", { cache: "no-store" })));
      setState("ready");
    } catch (error) { setState("error"); setFeedback(error instanceof Error ? error.message : "Dados comerciais indisponiveis."); }
  }, [leadId, mode, stageFilter]);

  useEffect(() => { void load(); }, [load]);

  async function createFollowUp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setFeedback("");
    try {
      const result = await responseJson<components["schemas"]["LeadFollowUpResponse"]>(await fetch(`/api/commercial/leads/${encodeURIComponent(leadId)}/follow-ups`, {
        method: "POST", headers: { "content-type": "application/json", "Idempotency-Key": followUpKey.current },
        body: JSON.stringify({ action, dueAt: new Date(dueAt).toISOString(), notes })
      }));
      setDetail((current) => current ? { ...current, lead: result.lead, timeline: [result.timelineItem, ...current.timeline] } : current);
      setAction(""); setDueAt(""); setNotes(""); followUpKey.current = globalThis.crypto.randomUUID();
      setFeedback(result.replayed ? "Follow-up ja estava salvo." : "Follow-up salvo.");
    } catch (error) { setFeedback(`${error instanceof Error ? error.message : "Provider indisponivel."} O formulario foi preservado.`); }
    finally { setPending(false); }
  }

  async function moveOpportunity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setPending(true); setFeedback("");
    const form = new FormData(event.currentTarget);
    try {
      await responseJson(await fetch(`/api/commercial/opportunities/${encodeURIComponent(selected.id)}/stage`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ targetStage, amount: form.get("amount"), probability: form.get("probability"), expectedCloseDate: form.get("expectedCloseDate"), lossReason: form.get("lossReason") })
      }));
      setFeedback("Etapa atualizada."); setSelected(null); await load();
    } catch (error) { setFeedback(error instanceof Error ? error.message : "Nao foi possivel mover a oportunidade."); }
    finally { setPending(false); }
  }

  if (mode === "leads") return (
    <section className={styles.page} aria-labelledby="commercial-leads-title">
      <header className={styles.heading}><div><span>Comercial</span><h1 id="commercial-leads-title">Leads</h1><p>Priorize contatos pela origem, score e proxima acao.</p></div><Link href="/comercial/pipeline">Abrir pipeline</Link></header>
      <div className={styles.toolbar}><label>Etapa<select value={stageFilter} onChange={(event) => setStageFilter(event.target.value)}><option value="">Todas</option><option value="new">Novos</option><option value="qualified">Qualificados</option><option value="converted">Convertidos</option></select></label>{leads ? <span>{leads.items.length} leads nesta visao</span> : null}</div>
      {feedback ? <p className={styles.feedback} role="status">{feedback}</p> : null}
      {state === "loading" ? <div className={styles.empty}>Carregando leads...</div> : null}
      {state === "error" ? <ErrorState message={feedback} retry={load} /> : null}
      {state === "ready" ? <div className={styles.leadList}>{leads?.items.map((lead) => <Link href={`/comercial/lead-detalhe?leadId=${encodeURIComponent(lead.id)}`} key={lead.id} prefetch={false}><span className={styles.score}>{scoreLabel(lead.icpScore)}</span><span><strong>{lead.source || "Origem nao informada"}</strong><small>Lead {shortId(lead.id)} · owner {shortId(lead.ownerUserId)}</small></span><span><em>{lead.status}</em><small>{lead.nextAction || "Definir proxima acao"}</small></span></Link>)}{leads?.items.length === 0 ? <div className={styles.empty}><strong>Nenhum lead nesta etapa</strong><Button onClick={() => setStageFilter("")} type="button">Limpar filtro</Button></div> : null}</div> : null}
    </section>
  );

  if (mode === "detail") {
    if (!leadId) return <section className={styles.page}><div className={styles.empty}><strong>Selecione um lead</strong><Link href="/comercial/leads">Voltar para leads</Link></div></section>;
    if (state === "loading") return <section className={styles.page}><div className={styles.empty}>Carregando lead...</div></section>;
    if (state === "error" || !detail) return <section className={styles.page}><ErrorState message={feedback || "Lead nao encontrado."} retry={load} /></section>;
    const timeline = detail.timeline as Record<string, unknown>[];
    return <section className={styles.page} aria-labelledby="lead-detail-title">
      <header className={styles.heading}><div><Link href="/comercial/leads">Leads</Link><h1 id="lead-detail-title">Lead {shortId(detail.lead.id)}</h1><p>{detail.lead.nextAction || "Nenhuma proxima acao definida."}</p></div><span className={styles.scoreLarge}>{scoreLabel(detail.lead.icpScore)}</span></header>
      {feedback ? <p className={styles.feedback} role="status">{feedback}</p> : null}
      <div className={styles.detailGrid}><div><dl className={styles.facts}><div><dt>Origem</dt><dd>{detail.lead.source || "Nao informada"}</dd></div><div><dt>Estado</dt><dd>{detail.lead.status}</dd></div><div><dt>Responsavel</dt><dd>{shortId(detail.lead.ownerUserId)}</dd></div><div><dt>Proxima acao</dt><dd>{dateLabel(detail.lead.nextActionAt)}</dd></div></dl><section className={styles.timeline}><h2>Historico</h2>{timeline.map((item, index) => <article key={`${timelineTitle(item)}-${timelineDate(item)}-${index}`}><i /><div><strong>{timelineTitle(item)}</strong><span>{timelineDate(item) ? dateLabel(timelineDate(item)) : "Momento nao informado"}</span>{text(item.notes) ? <p>{text(item.notes)}</p> : null}</div></article>)}{timeline.length === 0 ? <p>Nenhuma atividade registrada.</p> : null}</section></div>
      <form className={styles.inspector} onSubmit={(event) => { void createFollowUp(event); }}><h2>Novo follow-up</h2><p>O envio pode ser repetido com seguranca se a conexao falhar.</p><label>Acao<input required maxLength={2000} value={action} onChange={(event) => setAction(event.target.value)} /></label><label>Prazo<input required type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} /></label><label>Notas<textarea maxLength={10000} value={notes} onChange={(event) => setNotes(event.target.value)} /></label><Button disabled={pending} type="submit">{pending ? "Salvando..." : feedback.includes("preservado") ? "Tentar novamente" : "Criar follow-up"}</Button></form></div>
    </section>;
  }

  return <section className={styles.pageWide} aria-labelledby="pipeline-title">
    <header className={styles.heading}><div><span>Comercial</span><h1 id="pipeline-title">Pipeline</h1><p>Mova oportunidades e mantenha a previsao atualizada.</p></div><Link href="/comercial/leads">Ver leads</Link></header>
    {feedback ? <p className={styles.feedback} role="status">{feedback}</p> : null}
    {state === "loading" ? <div className={styles.empty}>Carregando pipeline...</div> : null}
    {state === "error" ? <ErrorState message={feedback} retry={load} /> : null}
    {state === "ready" ? <><div className={styles.pipelineSummary}><strong>{pipeline?.totals.opportunities ?? 0} oportunidades</strong><span>{money(Number(pipeline?.totals.amount ?? 0))}</span></div><div className={styles.board}>{pipeline?.stages.map((stage) => <section key={stage.id}><header><strong>{stage.label}</strong><span>{stage.count} · {money(stage.amount)}</span></header><div>{stage.opportunities.map((item) => <Button key={item.id} onClick={() => { setSelected(item); setTargetStage(item.stage === "discovery" ? "qualification" : item.stage as Stage); }} tone="secondary" type="button"><strong>{item.name}</strong><span>{item.amount == null ? "Valor a definir" : money(item.amount, item.currency)}</span><small>{item.probability == null ? "Probabilidade a definir" : `${item.probability}%`} · {item.expectedCloseDate || "Sem fechamento"}</small></Button>)}{stage.opportunities.length === 0 ? <p>Sem oportunidades</p> : null}</div></section>)}</div></> : null}
    {selected ? <form className={styles.stagePanel} onSubmit={(event) => { void moveOpportunity(event); }}><div><span>Atualizar oportunidade</span><h2>{selected.name}</h2></div><Button aria-label="Fechar painel" onClick={() => setSelected(null)} tone="secondary" type="button">×</Button><label>Nova etapa<select value={targetStage} onChange={(event) => setTargetStage(event.target.value as Stage)}>{stages.map((stage) => <option key={stage} value={stage}>{stageLabels[stage]}</option>)}</select></label>{["proposal", "negotiation", "won"].includes(targetStage) ? <label>Valor<input defaultValue={selected.amount ?? ""} min="0.01" name="amount" required type="number" /></label> : <input name="amount" type="hidden" value={selected.amount ?? ""} />}{targetStage === "negotiation" ? <label>Probabilidade<input defaultValue={selected.probability ?? ""} max="100" min="0" name="probability" required type="number" /></label> : <input name="probability" type="hidden" value={selected.probability ?? ""} />}<label>Fechamento previsto<input defaultValue={selected.expectedCloseDate ?? ""} name="expectedCloseDate" type="date" /></label>{targetStage === "lost" ? <label>Motivo da perda<textarea name="lossReason" required /></label> : <input name="lossReason" type="hidden" value="" />}<Button disabled={pending} type="submit">{pending ? "Atualizando..." : "Confirmar etapa"}</Button></form> : null}
  </section>;
}

function ErrorState({ message, retry }: { message: string; retry: () => Promise<void> }) {
  return <div className={styles.empty}><strong>Dados indisponiveis</strong><span>{message}</span><Button onClick={() => { void retry(); }} type="button">Tentar novamente</Button></div>;
}
