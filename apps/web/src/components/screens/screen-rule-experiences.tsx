"use client";

import { useState, type FormEvent } from "react";

import { Button, Card } from "@bighead/ui";
import type { ScreenCode } from "@/lib/screen-catalog";

export type ScreenRuleCommand = {
  code: ScreenRuleCode;
  operation: string;
  payload: Record<string, string | number | boolean>;
};

export type ScreenRuleBoundary = (command: ScreenRuleCommand) => Promise<{ ok: boolean; message?: string }>;

export type ScreenRule = {
  title: string;
  label: string;
  inputType?: "text" | "email" | "number" | "date";
  invalidValue: string;
  safeValue: string;
  operation: string;
  action: string;
  effect: string;
  validate: (value: string) => string | null;
  payload: (value: string) => Record<string, string | number | boolean>;
};

const futureDate = (value: string) => {
  const [date, reason] = value.split("|");
  const today = new Date().toISOString().slice(0, 10);
  const parsed = new Date(`${date ?? ""}T00:00:00Z`);
  const validDate = !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === date;
  return validDate && date > today && (reason?.length ?? 0) >= 8
    ? null
    : "Informe data futura e justificativa com ao menos 8 caracteres.";
};
const jsonObject = (value: string) => { try { return typeof JSON.parse(value) === "object" ? null : "Schema JSON invalido."; } catch { return "Schema JSON invalido."; } };
const draftBaseVersion = (value: string) => {
  const parsed: unknown = JSON.parse(value);
  if (typeof parsed !== "object" || parsed === null || !("baseVersion" in parsed)) return 0;
  return Number(parsed.baseVersion);
};

export const screenRuleDefinitions = {
  T02: { title: "Recuperacao sem enumeracao", label: "Email corporativo", inputType: "email", invalidValue: "email-invalido", safeValue: "camila@acme.ai", operation: "auth.recovery.request", action: "Enviar link seguro", effect: "Link opaco solicitado com resposta anonima.", validate: (v) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.trim()) ? null : "Informe um email valido.", payload: (v) => ({ normalizedEmail: v.trim().toLowerCase() }) },
  T03: { title: "Convite vinculado a identidade", label: "Token e emails (token|autenticado|convidado)", invalidValue: "expired|ana@acme.ai|bia@acme.ai", safeValue: "invite-live|ana@acme.ai|ana@acme.ai", operation: "invites.accept", action: "Aceitar convite", effect: "Membership criada uma unica vez.", validate: (v) => { const [token, auth, invited] = v.split("|"); return token?.startsWith("invite-") && token !== "invite-expired" && auth === invited ? null : "Token vigente e emails correspondentes sao obrigatorios."; }, payload: (v) => { const [token, email] = v.split("|"); return { token: token!, authenticatedEmail: email! }; } },
  T09: { title: "Revogacao segura de sessao", label: "ID da sessao alvo", invalidValue: "current", safeValue: "session-mobile-42", operation: "sessions.revoke", action: "Encerrar outra sessao", effect: "Outro dispositivo revogado; sessao atual preservada.", validate: (v) => v.startsWith("session-") && v !== "session-current" ? null : "Selecione outra sessao pertencente ao usuario.", payload: (v) => ({ sessionId: v, preserveCurrent: true }) },
  T12: { title: "Moderacao sem sala orfa", label: "Moderadores restantes", inputType: "number", invalidValue: "0", safeValue: "1", operation: "rooms.members.remove", action: "Remover membro", effect: "Membro removido com moderacao preservada.", validate: (v) => Number.isInteger(Number(v)) && Number(v) >= 1 ? null : "A sala precisa manter ao menos um moderador.", payload: (v) => ({ remainingModeratorCount: Number(v) }) },
  T18: { title: "Retry de grupo de falhas", label: "Falhas selecionadas (retryable:ID, separadas por virgula)", invalidValue: "fatal:run-1", safeValue: "retryable:run-1,retryable:run-2", operation: "runs.retry_group", action: "Reprocessar grupo", effect: "Tentativa idempotente criada para falhas retryable.", validate: (v) => v.split(",").every((x) => /^retryable:[\w-]+$/.test(x)) ? null : "Selecione somente falhas retryable ineditas.", payload: (v) => ({ failureIds: v, idempotencyKey: `retry-${v}` }) },
  T19: { title: "Reagendamento auditavel", label: "Prazo e justificativa (AAAA-MM-DD|motivo)", invalidValue: "2020-01-01|curto", safeValue: "2027-08-20|Dependencia externa atrasou", operation: "tasks.reschedule", action: "Confirmar reagendamento", effect: "SLA reagendado com justificativa auditavel.", validate: futureDate, payload: (v) => { const [dueAt, reason] = v.split("|"); return { dueAt: dueAt!, reason: reason! }; } },
  T22: { title: "Scorecard com evidencia", label: "IDs criterio|politica|evidencia", invalidValue: "criterion-1||", safeValue: "criterion-1|policy-7|evidence-9", operation: "scorecards.explain", action: "Explicar falha critica", effect: "Falha explicada com politica e evidencia rastreaveis.", validate: (v) => v.split("|").filter(Boolean).length === 3 ? null : "Criterio, politica e evidencia sao obrigatorios.", payload: (v) => { const [criterionId, policyId, evidenceId] = v.split("|"); return { criterionId: criterionId!, policyId: policyId!, evidenceId: evidenceId! }; } },
  T24: { title: "Portal externo isolado", label: "Token opaco", invalidValue: "expired", safeValue: "portal_4f9e_scope_item", operation: "portal.item.read", action: "Abrir item externo", effect: "Item autorizado carregado sem shell interno.", validate: (v) => /^portal_[a-z0-9]+_scope_item$/.test(v) ? null : "Token vigente com escopo do item e obrigatorio.", payload: (v) => ({ token: v, includeInternalShell: false }) },
  T25: { title: "Consumers por versao de agente", label: "Versao imutavel", invalidValue: "draft", safeValue: "agent-sdr@12", operation: "agents.consumers.list", action: "Abrir consumers", effect: "Consumers carregados somente para a versao selecionada.", validate: (v) => /^agent-[\w-]+@\d+$/.test(v) ? null : "Selecione uma versao publicada do agente.", payload: (v) => { const [agentId, version] = v.split("@"); return { agentId: agentId!, version: Number(version) }; } },
  T26: { title: "Impacto antes da publicacao", label: "Draft JSON com baseVersion", invalidValue: "{}", safeValue: "{\"baseVersion\":12,\"model\":\"gpt\"}", operation: "agents.impact.analyze", action: "Gerar analise de impacto", effect: "Consumers, limites e skills impactados calculados.", validate: (v) => { const syntax = jsonObject(v); if (syntax) return syntax; return draftBaseVersion(v) > 0 ? null : "baseVersion publicada e obrigatoria."; }, payload: (v) => ({ draft: v, baseVersion: draftBaseVersion(v) }) },
  T31: { title: "Workflows pelo owner do tenant", label: "Owner (tenant:ID)", invalidValue: "foreign:owner-1", safeValue: "tenant:owner-7", operation: "workflows.filter", action: "Filtrar workflows", effect: "Workflows do owner exibidos com risco operacional.", validate: (v) => /^tenant:owner-[\w-]+$/.test(v) ? null : "Owner precisa pertencer ao tenant atual.", payload: (v) => ({ ownerId: v.slice(7), tenantScoped: true }) },
  T34: { title: "Comparacao causal de tentativas", label: "Tentativas (run:attempt,run:attempt)", invalidValue: "run-1:1,run-2:2", safeValue: "run-7:1,run-7:2", operation: "runs.attempts.compare", action: "Comparar tentativas", effect: "Duracao, erro e correlacao comparados.", validate: (v) => { const attempts = v.split(","); const parsed = attempts.map((item) => /^(run-[\w-]+):(\d+)$/.exec(item)); return parsed.length === 2 && parsed.every(Boolean) && parsed[0]![1] === parsed[1]![1] && Number(parsed[0]![2]) !== Number(parsed[1]![2]) ? null : "Escolha duas tentativas distintas do mesmo run."; }, payload: (v) => ({ attempts: v, runId: v.split(":")[0]! }) },
  T35: { title: "Fontes autorizadas", label: "Escopo de acesso", invalidValue: "unresolved", safeValue: "tenant:member:active", operation: "knowledge.sources.list", action: "Listar fontes ativas", effect: "Somente fontes autorizadas exibidas com freshness.", validate: (v) => v === "tenant:member:active" ? null : "Resolva a politica de acesso antes da consulta.", payload: () => ({ activeOnly: true, applyAccessPolicy: true }) },
  T36: { title: "Documento versionado sem overwrite", label: "Base atual|changelog", invalidValue: "v3|", safeValue: "v4|Atualiza politica de retencao", operation: "documents.version.create", action: "Salvar nova versao", effect: "Nova versao criada sem alterar a publicada.", validate: (v) => /^v\d+\|.{8,}$/.test(v) ? null : "Base atual e changelog sao obrigatorios.", payload: (v) => { const [baseVersion, changelog] = v.split("|"); return { baseVersion: baseVersion!, changelog: changelog! }; } },
  T37: { title: "Ingestao retomada na etapa segura", label: "Checkpoint retryable", invalidValue: "completed:chunk", safeValue: "retryable:embedding:checkpoint-9", operation: "ingestion.resume", action: "Reprocessar documento", effect: "Pipeline retomado sem duplicar chunks.", validate: (v) => /^retryable:[\w-]+:checkpoint-[\w-]+$/.test(v) ? null : "Selecione a etapa retryable e seu checkpoint.", payload: (v) => ({ checkpoint: v, preserveCompletedSteps: true }) },
  T39: { title: "Memoria governada", label: "Owner|motivo", invalidValue: "|", safeValue: "owner-7|Informacao desatualizada", operation: "memories.review.request", action: "Marcar para revisao", effect: "Revisao aberta com auditoria imutavel.", validate: (v) => /^[\w-]+\|.{8,}$/.test(v) ? null : "Owner e motivo auditavel sao obrigatorios.", payload: (v) => { const [ownerId, reason] = v.split("|"); return { ownerId: ownerId!, reason: reason! }; } },
  T41: { title: "Stakeholders da mesma conta", label: "Tenant da conta|tenant do contato", invalidValue: "atlas|beta", safeValue: "atlas|atlas", operation: "accounts.stakeholders.update", action: "Atualizar mapa de poder", effect: "Mapa de poder versionado dentro do tenant.", validate: (v) => { const [a, b] = v.split("|"); return a && a === b ? null : "Conta e stakeholder precisam compartilhar o tenant."; }, payload: (v) => ({ tenantId: v.split("|")[0]!, versioned: true }) },
  T43: { title: "Atividade comercial consentida", label: "Owner|consentimento", invalidValue: "owner-4|missing", safeValue: "owner-4|granted", operation: "opportunities.activities.create", action: "Registrar interacao", effect: "Interacao adicionada a timeline da oportunidade.", validate: (v) => /^owner-[\w-]+\|granted$/.test(v) ? null : "Owner valido e consentimento sao obrigatorios.", payload: (v) => ({ ownerId: v.split("|")[0]!, consent: true }) },
  T46: { title: "Direitos de uso do ativo", label: "Validade|canal", invalidValue: "expired|linkedin", safeValue: "active|linkedin", operation: "assets.license.release", action: "Liberar ativo", effect: "Ativo liberado somente no canal licenciado.", validate: (v) => /^active\|(linkedin|email|web)$/.test(v) ? null : "Licenca vigente precisa cobrir o canal.", payload: (v) => ({ licenseStatus: "active", channel: v.split("|")[1]! }) },
  T49: { title: "Custo com freshness explicita", label: "Periodo|freshnessMin", invalidValue: "open|", safeValue: "2026-06|5", operation: "costs.deviation.explain", action: "Detalhar desvio de custo", effect: "Desvio explicado por agente, modelo e tokens.", validate: (v) => /^\d{4}-\d{2}\|\d+$/.test(v) ? null : "Periodo fechado e freshness sao obrigatorios.", payload: (v) => ({ period: v.split("|")[0]!, freshnessMinutes: Number(v.split("|")[1]) }) },
  T50: { title: "Tendencia com amostra minima", label: "Tamanho da amostra", inputType: "number", invalidValue: "9", safeValue: "50", operation: "quality.trend.read", action: "Abrir tendencia de score", effect: "Tendencia exibida com tamanho da amostra.", validate: (v) => Number(v) >= 30 ? null : "Amostra minima de 30 observacoes e obrigatoria.", payload: (v) => ({ sampleSize: Number(v), includeConfidenceInterval: true }) },
  T51: { title: "Notificacao sem duplicata", label: "Canal verificado|fingerprint", invalidValue: "pending|rule-1", safeValue: "verified|rule-unique-7", operation: "notifications.preference.test", action: "Testar preferencia", effect: "Teste enviado uma vez sem duplicar regra.", validate: (v) => /^verified\|rule-unique-[\w-]+$/.test(v) ? null : "Canal verificado e fingerprint unico sao obrigatorios.", payload: (v) => ({ channelVerified: true, fingerprint: v.split("|")[1]! }) },
  T52: { title: "Auditoria append-only", label: "Correlation id do tenant", invalidValue: "foreign:corr-1", safeValue: "tenant:corr-8", operation: "audit.events.filter", action: "Filtrar eventos", effect: "Eventos append-only correlacionados carregados.", validate: (v) => /^tenant:corr-[\w-]+$/.test(v) ? null : "Correlation id precisa pertencer ao tenant.", payload: (v) => ({ correlationId: v.slice(7), readOnly: true }) },
  T53: { title: "Politica do tenant com concorrencia", label: "Versao|dominio", invalidValue: "stale|invalid", safeValue: "v12|acme.ai", operation: "organization.policy.update", action: "Salvar politica", effect: "Politica versionada e registrada na auditoria.", validate: (v) => /^v\d+\|[a-z0-9.-]+\.[a-z]{2,}$/.test(v) ? null : "Versao atual e dominio valido sao obrigatorios.", payload: (v) => ({ version: Number(v.split("|")[0]!.slice(1)), domain: v.split("|")[1]! }) }
} satisfies Partial<Record<ScreenCode, ScreenRule>>;

export type ScreenRuleCode = keyof typeof screenRuleDefinitions;
export const screenRuleCodes = new Set<ScreenCode>(Object.keys(screenRuleDefinitions) as ScreenCode[]);

export const screenRuleHttpBoundary: ScreenRuleBoundary = async (command) => {
  const response = await fetch("/api/screen-rules", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(command)
  });
  const result = await response.json() as { message?: string };
  return result.message ? { ok: response.ok, message: result.message } : { ok: response.ok };
};

function requireScreenRule(code: ScreenCode): ScreenRule {
  const rule = screenRuleDefinitions[code as ScreenRuleCode] as ScreenRule | undefined;
  if (!rule) throw new Error(`Regra especifica ausente para ${code}.`);
  return rule;
}

export function ScreenRuleExperience({ code, boundary = screenRuleHttpBoundary }: { code: ScreenCode; boundary?: ScreenRuleBoundary }) {
  const rule = requireScreenRule(code);
  const [value, setValue] = useState(rule.invalidValue);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = rule.validate(value);
    if (validationError) { setFeedback(validationError); return; }
    setPending(true); setFeedback(null);
    try {
      const result = await boundary({ code: code as ScreenRuleCode, operation: rule.operation, payload: rule.payload(value) });
      setFeedback(result.ok ? rule.effect : result.message ?? "A operacao foi rejeitada pelo servico.");
    } catch {
      setFeedback("Falha de transporte; os dados informados foram preservados.");
    } finally { setPending(false); }
  }

  return <div className="bh-columns" data-testid={`screen-rule-${code}`}>
    <Card>
      <div className="bh-card-title"><h3>{rule.title}</h3><span className="bh-label">regra critica {code}</span></div>
      <form noValidate onSubmit={(event) => void submit(event)}>
        <label className="bh-field"><span>{rule.label}</span><input aria-label={rule.label} type={rule.inputType ?? "text"} value={value} onChange={(event) => { setValue(event.target.value); setFeedback(null); }} /></label>
        <Button disabled={pending} type="submit">{pending ? "Processando operacao" : rule.action}</Button>
      </form>
      <div aria-live="polite" className="bh-state-panel" role="status"><strong>{pending ? "Validando no servico" : feedback ? "Resultado" : "Preencha os dados da operacao"}</strong><p>{feedback ?? "A validacao ocorre antes de enviar qualquer payload."}</p></div>
    </Card>
    <Card><div className="bh-card-title"><h3>Contrato da operacao</h3><span className="bh-label">boundary injetavel</span></div><p><code>{rule.operation}</code></p><p>{rule.effect}</p></Card>
  </div>;
}
