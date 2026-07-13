"use client";

import { useMemo, useState, type ReactNode } from "react";

import { Button, Card } from "@bighead/ui";
import type { AnalyticsDrilldown } from "@/lib/mock-workspace";
import type { ScreenCode } from "@/lib/screen-catalog";
import {
  canApprove,
  filterKnowledgeResults,
  missingStageFields,
  retryPublication,
  validateWorkflow,
  type FailedPublication,
  type KnowledgeResult,
  type WorkflowEdge,
  type WorkflowNode
} from "@/lib/sprint2-domain-rules";

export const sprint2DomainCodes = new Set<ScreenCode>(["T20", "T27", "T29", "T30", "T32", "T33", "T38", "T42", "T45", "T48"]);

const initialNodes: WorkflowNode[] = [
  { id: "briefing", input: "brief", output: "lead" },
  { id: "score", input: "lead", output: "decision" },
  { id: "approve", input: "decision", output: "publication" }
];
const initialEdges: WorkflowEdge[] = [{ source: "briefing", target: "score" }, { source: "score", target: "approve" }];
export function Sprint2DomainExperience({ code, tenantId, analyticsDrilldowns = [] }: { code: ScreenCode; tenantId: string; analyticsDrilldowns?: AnalyticsDrilldown[] }) {
  if (code === "T20") return <SegregatedApproval />;
  if (code === "T27" || code === "T29") return <DependencyImpact initialResource={code === "T27" ? "skill:enrichment" : "model:gpt-enterprise"} />;
  if (code === "T30" || code === "T33") return <ImmutablePublication />;
  if (code === "T32") return <WorkflowValidation />;
  if (code === "T38") return <TenantKnowledgeSearch tenantId={tenantId} />;
  if (code === "T42") return <StageGuard />;
  if (code === "T45") return <SafePublicationRetry />;
  return <IndicatorDrilldown drilldowns={analyticsDrilldowns} tenantId={tenantId} />;
}

function Layout({ title, children, status }: { title: string; children: ReactNode; status: ReactNode }) {
  return <div className="bh-columns" data-testid="sprint2-domain-experience"><Card><div className="bh-card-title"><h3>{title}</h3><span className="bh-label">regra operacional comprovavel</span></div>{children}</Card><Card><div className="bh-state-panel" role="status">{status}</div></Card></div>;
}

function SegregatedApproval() {
  const requesterId = "camila";
  const authenticatedActorId = "camila";
  const allowed = canApprove(requesterId, authenticatedActorId, true);
  return <Layout title="Segregacao de aprovacao" status={<><strong>{allowed ? "Pronto para decisao" : "Autoaprovacao bloqueada"}</strong><p>A politica exige solicitante e ator autenticado distintos.</p></>}>
    <p>Solicitante: <strong>Camila Moura</strong></p>
    <p>Ator autenticado: <strong>Camila Moura</strong> <span className="bh-label">identidade da sessao</span></p>
    <Button disabled={!allowed}>Aprovar entrega</Button>
  </Layout>;
}

function DependencyImpact({ initialResource }: { initialResource: string }) {
  const [resource, setResource] = useState(initialResource);
  const [reviewed, setReviewed] = useState(false);
  const [disabled, setDisabled] = useState(false);
  const consumers = resource.startsWith("model") ? ["Agente SDR v12", "Workflow outbound v8", "Playbook enterprise"] : ["Agente Research v4", "Workflow enrichment v6"];
  return <Layout title="Impacto antes de desabilitar" status={<><strong>{disabled ? "Recurso desabilitado" : "Confirmacao protegida"}</strong><p>{consumers.length} consumidores afetados; fallback e owners permanecem visiveis.</p></>}>
    <label className="bh-field"><span>Recurso</span><select aria-label="Recurso de automacao" value={resource} onChange={(event) => { setResource(event.target.value); setReviewed(false); setDisabled(false); }}><option value="model:gpt-enterprise">Modelo GPT Enterprise</option><option value="skill:enrichment">Skill enrichment.lookup</option></select></label>
    <ul className="bh-list" aria-label="Consumidores afetados">{consumers.map((consumer) => <li key={consumer}><strong>{consumer}</strong><span>Owner notificado; fallback obrigatorio</span></li>)}</ul>
    <label className="bh-field"><span><input checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} type="checkbox" /> Revisei consumidores e fallback</span></label>
    <Button disabled={!reviewed || disabled} onClick={() => setDisabled(true)}>Desabilitar recurso</Button>
  </Layout>;
}

function ImmutablePublication() {
  const [published] = useState({ version: 3, body: "Use fontes aprovadas." });
  const [draft, setDraft] = useState("Use fontes aprovadas e inclua score.");
  const [next, setNext] = useState<{ version: number; body: string } | null>(null);
  return <Layout title="Publicacao versionada" status={<><strong>{next ? `v${next.version} publicada` : "Draft nao publicado"}</strong><p>{next ? "Versoes v3 e v4 sao imutaveis; diff preservado." : "A versao publicada permanece intacta durante a edicao."}</p></>}>
    <div data-testid="published-v3"><strong>Publicada v{published.version}</strong><p>{published.body}</p></div>
    <label className="bh-field"><span>Novo draft</span><textarea aria-label="Novo draft da publicacao" disabled={Boolean(next)} value={draft} onChange={(event) => setDraft(event.target.value)} /></label>
    <Button disabled={Boolean(next) || draft === published.body} onClick={() => setNext({ version: published.version + 1, body: draft })}>Publicar nova versao</Button>
    {next ? <div data-testid="publication-diff"><strong>Diff v3 para v4</strong><p>- {published.body}</p><p>+ {next.body}</p></div> : null}
  </Layout>;
}

function WorkflowValidation() {
  const [nodes, setNodes] = useState(initialNodes);
  const [edges, setEdges] = useState(initialEdges);
  const [published, setPublished] = useState(false);
  const errors = validateWorkflow(nodes, edges);
  const restore = () => { setNodes(initialNodes); setEdges(initialEdges); setPublished(false); };
  return <Layout title="Validacao do workflow" status={<><strong>{published ? "Versao publicada" : errors.length ? "Publicacao bloqueada" : "Grafo valido"}</strong><ul>{errors.map((error) => <li key={error}>{error}</li>)}</ul></>}>
    <p>briefing: brief para lead | score: lead para decision | approve: decision para publication</p>
    <div className="bh-inline"><Button tone="secondary" onClick={() => setEdges([...initialEdges, { source: "approve", target: "briefing" }])}>Adicionar ciclo</Button><Button tone="secondary" onClick={() => setNodes(initialNodes.map((node) => node.id === "approve" ? { ...node, input: "asset" } : node))}>Quebrar schema</Button><Button tone="secondary" onClick={restore}>Restaurar grafo</Button></div>
    <Button disabled={errors.length > 0 || published} onClick={() => setPublished(true)}>Validar e publicar</Button>
  </Layout>;
}

function TenantKnowledgeSearch({ tenantId }: { tenantId: string }) {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [minScore, setMinScore] = useState(0.8);
  const knowledge = useMemo<KnowledgeResult[]>(() => [
    { id: "k1", tenantId, title: "Politica vigente de onboarding", source: "handbook", score: 0.94, status: "active" },
    { id: "k2", tenantId, title: "Politica antiga contestada", source: "handbook", score: 0.99, status: "contested" },
    { id: "k3", tenantId: `${tenantId}-foreign`, title: "Plano secreto de outro tenant", source: "crm", score: 0.98, status: "active" },
    { id: "k4", tenantId, title: "Resumo comercial do tenant atual", source: "crm", score: 0.81, status: "active" }
  ], [tenantId]);
  const results = useMemo(() => filterKnowledgeResults(knowledge, { tenantId, query, source, minScore }), [knowledge, tenantId, query, source, minScore]);
  return <Layout title="Busca governada por tenant" status={<><strong>{results.length} resultados autorizados</strong><p>Contestados e itens de outros tenants foram removidos antes das facets e contagens.</p></>}>
    <div className="bh-form-grid"><label className="bh-field"><span>Consulta</span><input aria-label="Consulta governada" value={query} onChange={(event) => setQuery(event.target.value)} /></label><label className="bh-field"><span>Fonte</span><select aria-label="Filtrar fonte" value={source} onChange={(event) => setSource(event.target.value)}><option value="all">Todas</option><option value="handbook">Handbook</option><option value="crm">CRM</option></select></label><label className="bh-field"><span>Score minimo</span><input aria-label="Score minimo" max="1" min="0" step="0.05" type="number" value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} /></label></div>
    <ul className="bh-list" aria-label="Resultados semanticos">{results.map((item) => <li id={`source-${item.id}`} key={item.id}><strong>{item.title}</strong><span>Score {item.score.toFixed(2)}</span><a href={`#source-${item.id}`}>Fonte: {item.source}</a><span>Tenant: {tenantId}</span></li>)}</ul>
  </Layout>;
}

function StageGuard() {
  const [stage, setStage] = useState("proposal");
  const [values, setValues] = useState({ amount: "", closeDate: "", decisionMaker: "", contractId: "", lossReason: "" });
  const [moved, setMoved] = useState(false);
  const missing = missingStageFields(stage, values);
  return <Layout title="Guard rail de estagio" status={<><strong>{moved ? `Movida para ${stage}` : missing.length ? "Campos obrigatorios ausentes" : "Pronta para mover"}</strong><p>{missing.length ? `Preencha: ${missing.join(", ")}.` : "Forecast e auditoria serao preservados."}</p></>}>
    <label className="bh-field"><span>Estagio de destino</span><select aria-label="Estagio de destino" value={stage} onChange={(event) => { setStage(event.target.value); setMoved(false); }}><option value="proposal">Proposal</option><option value="negotiation">Negotiation</option><option value="won">Won</option><option value="lost">Lost</option></select></label>
    <label className="bh-field"><span>Valor</span><input aria-label="Valor da oportunidade" value={values.amount} onChange={(event) => setValues({ ...values, amount: event.target.value })} /></label><label className="bh-field"><span>Data de fechamento</span><input aria-label="Data de fechamento" type="date" value={values.closeDate} onChange={(event) => setValues({ ...values, closeDate: event.target.value })} /></label>
    <label className="bh-field"><span>Decisor</span><input aria-label="Decisor" value={values.decisionMaker} onChange={(event) => setValues({ ...values, decisionMaker: event.target.value })} /></label><label className="bh-field"><span>Contrato</span><input aria-label="Contrato" value={values.contractId} onChange={(event) => setValues({ ...values, contractId: event.target.value })} /></label><label className="bh-field"><span>Motivo da perda</span><input aria-label="Motivo da perda" value={values.lossReason} onChange={(event) => setValues({ ...values, lossReason: event.target.value })} /></label>
    <Button disabled={missing.length > 0 || moved} onClick={() => setMoved(true)}>Mover oportunidade</Button>
  </Layout>;
}

function SafePublicationRetry() {
  const [publication, setPublication] = useState<FailedPublication>({ payload: '{"channel":"linkedin","assetId":"asset-44","body":"Launch Q3"}', idempotencyKey: "publication-atlas-44", attempts: 1, status: "provider_error" });
  return <Layout title="Retry seguro de publicacao" status={<><strong>{publication.status === "queued" ? "Retry enfileirado" : "Falha do provider"}</strong><p>Tentativa {publication.attempts}; mesma chave idempotente e payload preservado.</p></>}>
    <label className="bh-field"><span>Payload preservado</span><textarea aria-label="Payload preservado" readOnly value={publication.payload} /></label><p>Idempotency-Key: <code>{publication.idempotencyKey}</code></p>
    <Button disabled={publication.status !== "provider_error"} onClick={() => setPublication(retryPublication(publication))}>Repetir publicacao</Button>
  </Layout>;
}

function IndicatorDrilldown({ tenantId, drilldowns }: { tenantId: string; drilldowns: AnalyticsDrilldown[] }) {
  const [dimension, setDimension] = useState<string | null>(null);
  const [record, setRecord] = useState<string | null>(null);
  const [pagedRecordIds, setPagedRecordIds] = useState<string[] | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [pageLoaded, setPageLoaded] = useState(false);
  const [loadingPage, setLoadingPage] = useState(false);
  const selectedDrilldown = drilldowns.find((item) => item.card === "total" && item.dimension === dimension);
  const componentRecords = pagedRecordIds ?? selectedDrilldown?.recordIds ?? [];
  async function loadRecordPage() {
    if (!selectedDrilldown || loadingPage) return;
    setLoadingPage(true);
    const query = new URLSearchParams({ dimension: selectedDrilldown.dimension, from: selectedDrilldown.periodFrom, to: selectedDrilldown.periodTo, limit: "100" });
    if (nextCursor) query.set("cursor", nextCursor);
    const response = await fetch(`/api/analytics/summary/records?${query.toString()}`);
    if (response.ok) {
      const page = await response.json() as { items?: Array<{ id?: string }>; nextCursor?: string | null };
      const ids = (page.items ?? []).map((item) => item.id).filter((id): id is string => Boolean(id));
      setPagedRecordIds((current) => [...new Set([...(current ?? selectedDrilldown.recordIds), ...ids])]);
      setNextCursor(page.nextCursor ?? null);
      setPageLoaded(true);
    }
    setLoadingPage(false);
  }
  return <Layout title="Rastreabilidade de indicadores" status={<><strong>{record ? "Registro componente" : dimension ? "Componentes do indicador total" : "Resumo executivo"}</strong><p>Fonte: tasks.created_at | periodo: 30d | timezone: America/Sao_Paulo | freshness: 5 min</p></>}>
    <div className="bh-inline">{drilldowns.filter((item) => item.card === "total").map((item) => <Button key={item.dimension} onClick={() => { setDimension(item.dimension); setRecord(null); setPagedRecordIds(null); setNextCursor(null); setPageLoaded(false); }}>Status {item.dimension} ({item.value})</Button>)}</div>
    {dimension ? <ul className="bh-list" aria-label="Registros componentes">{componentRecords.map((id) => <li key={id}><Button className="bh-row-button" onClick={() => setRecord(id)} type="button"><strong>{id}</strong><span>Status {selectedDrilldown?.dimension}</span></Button></li>)}</ul> : null}
    {selectedDrilldown ? <div data-testid="drilldown-coverage"><p>Exibindo {componentRecords.length} de {selectedDrilldown.recordCount} registros.{!selectedDrilldown.recordsTruncated || (pageLoaded && !nextCursor) ? " Cobertura integral." : " Ha mais paginas."}</p>{selectedDrilldown.recordsTruncated && (!pageLoaded || nextCursor) ? <Button disabled={loadingPage} onClick={() => void loadRecordPage()}>{loadingPage ? "Carregando registros" : "Carregar proximos registros"}</Button> : null}</div> : null}
    {record ? <div data-testid="component-record"><strong>{record}</strong><p>Tenant {tenantId} | referencia UUID retornada pelo contrato AnalyticsSummaryDrilldown.recordIds</p></div> : null}
  </Layout>;
}
