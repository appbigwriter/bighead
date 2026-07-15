"use client";

import { Button, StatePanel } from "@bighead/ui";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import styles from "./agents-workspace.module.css";

type Agent = {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  ownerUserId?: string | null;
  riskLevel: string;
  trustScore: number;
  isEnabled: boolean;
  lifecycle: "active" | "archived" | "draft";
  updatedAt?: string | null;
};
type AgentVersion = {
  id: string;
  version: number;
  modelId?: string | null;
  systemPrompt: string;
  configuration: Record<string, unknown>;
  skillIds: string[];
  publishedAt?: string | null;
  createdAt?: string | null;
};
type AgentDetail = {
  agent: Agent;
  versions: AgentVersion[];
  consumers: Array<Record<string, unknown>>;
  confidence: number;
};
type LoadState = "loading" | "ready" | "error";

class ResponseError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
  }
}
function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
function string(value: unknown, fallback = "") {
  return typeof value === "string" ? value : fallback;
}
function boolean(value: unknown, fallback = false) {
  return typeof value === "boolean" ? value : fallback;
}
function number(value: unknown, fallback = 0) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}
function normalizeAgent(value: unknown): Agent {
  const item = record(value);
  return {
    id: string(item.id),
    name: string(item.name, "Agente sem nome"),
    slug: string(item.slug),
    description: string(item.description) || null,
    ownerUserId: string(item.ownerUserId ?? item.owner_user_id) || null,
    riskLevel: string(item.riskLevel ?? item.risk_level, "low"),
    trustScore: number(item.trustScore ?? item.trust_score),
    isEnabled: boolean(item.isEnabled ?? item.is_enabled, true),
    lifecycle:
      item.lifecycle === "draft" || item.lifecycle === "archived"
        ? item.lifecycle
        : "active",
    updatedAt: string(item.updatedAt ?? item.updated_at) || null
  };
}
function normalizeVersion(value: unknown): AgentVersion {
  const item = record(value);
  const rawSkillIds = item.skillIds ?? item.skill_ids;
  return {
    id: string(item.id),
    version: number(item.version),
    modelId: string(item.modelId ?? item.model_id) || null,
    systemPrompt: string(item.systemPrompt ?? item.system_prompt),
    configuration: record(item.configuration),
    skillIds: Array.isArray(rawSkillIds)
      ? rawSkillIds.filter(
          (id: unknown): id is string => typeof id === "string"
        )
      : [],
    publishedAt: string(item.publishedAt ?? item.published_at) || null,
    createdAt: string(item.createdAt ?? item.created_at) || null
  };
}
function normalizeDetail(value: unknown): AgentDetail {
  const item = record(value);
  const versions = Array.isArray(item.versions)
    ? item.versions.map(normalizeVersion)
    : [];
  return {
    agent: normalizeAgent(item.agent),
    versions,
    consumers: Array.isArray(item.consumers)
      ? item.consumers.filter(
          (consumer): consumer is Record<string, unknown> =>
            Boolean(consumer) && typeof consumer === "object"
        )
      : [],
    confidence: number(
      item.confidence ??
        record(item.agent).trustScore ??
        record(item.agent).trust_score
    )
  };
}
async function responseJson<T>(response: Response): Promise<T> {
  const body = (await response.json().catch(() => ({}))) as T & {
    detail?: unknown;
  };
  if (!response.ok)
    throw new ResponseError(
      response.status,
      typeof body.detail === "string" ? body.detail : "Operacao nao concluida."
    );
  return body;
}
function parseIds(raw: FormDataEntryValue | null) {
  return typeof raw === "string"
    ? raw
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean)
    : [];
}
function parseLimits(raw: FormDataEntryValue | null) {
  if (typeof raw !== "string" || !raw.trim()) return {};
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Limites devem ser um objeto JSON.");
  return value;
}
function compactId(value?: string | null) {
  return value ? `${value.slice(0, 8)}...` : "Nao atribuido";
}

export function AgentsWorkspace({ mode }: { mode: "catalog" | "detail" }) {
  const router = useRouter();
  const params = useSearchParams();
  const agentId = params.get("agentId") ?? "";
  const [state, setState] = useState<LoadState>("loading");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [feedback, setFeedback] = useState("");
  const [pending, setPending] = useState(false);
  const [creating, setCreating] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);

  const load = useCallback(async () => {
    setState("loading");
    setFeedback("");
    try {
      if (mode === "catalog") {
        const page = await responseJson<{ items?: unknown[] }>(
          await fetch("/api/agents", { cache: "no-store" })
        );
        setAgents((page.items ?? []).map(normalizeAgent));
      } else if (agentId) {
        setDetail(
          normalizeDetail(
            await responseJson<unknown>(
              await fetch(`/api/agents/${encodeURIComponent(agentId)}`, {
                cache: "no-store"
              })
            )
          )
        );
      }
      setState("ready");
    } catch (error) {
      setState("error");
      setFeedback(
        error instanceof Error ? error.message : "Agentes indisponiveis."
      );
    }
  }, [agentId, mode]);

  useEffect(() => {
    void load();
  }, [load]);

  async function createAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setFeedback("");
    const form = new FormData(event.currentTarget);
    try {
      const response = await responseJson<unknown>(
        await fetch("/api/agents", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            name: form.get("name"),
            slug: form.get("slug"),
            description: form.get("description"),
            riskLevel: form.get("riskLevel"),
            prompt: form.get("prompt"),
            modelId: form.get("modelId"),
            limits: parseLimits(form.get("limits")),
            skillIds: parseIds(form.get("skillIds"))
          })
        })
      );
      const envelope = record(response);
      const created = normalizeAgent(envelope.agent ?? response);
      if (!created.id) throw new Error("A API nao retornou o agente criado.");
      router.push(
        `/automacao/agente-config?agentId=${encodeURIComponent(created.id)}`
      );
    } catch (error) {
      setFeedback(
        error instanceof Error
          ? error.message
          : "Nao foi possivel criar o agente."
      );
    } finally {
      setPending(false);
    }
  }

  async function updateAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail) return;
    setPending(true);
    setFeedback("");
    const form = new FormData(event.currentTarget);
    try {
      const updated = normalizeDetail(
        await responseJson<unknown>(
          await fetch(`/api/agents/${encodeURIComponent(detail.agent.id)}`, {
            method: "PATCH",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
              name: form.get("name"),
              description: form.get("description"),
              riskLevel: form.get("riskLevel"),
              isEnabled: form.get("isEnabled") === "on",
              prompt: form.get("prompt"),
              modelId: form.get("modelId"),
              limits: parseLimits(form.get("limits")),
              skillIds: parseIds(form.get("skillIds")),
              expectedVersion: currentVersion
            })
          })
        )
      );
      setDetail(updated);
      setFeedback("Agente atualizado e nova versao registrada.");
      setConfirmArchive(false);
    } catch (error) {
      setFeedback(
        error instanceof ResponseError && error.status === 409
          ? "O agente mudou ou possui consumidores ativos. Recarregue antes de continuar."
          : error instanceof Error
            ? error.message
            : "Nao foi possivel atualizar o agente."
      );
    } finally {
      setPending(false);
    }
  }

  async function archiveAgent() {
    if (!detail) return;
    setPending(true);
    setFeedback("");
    try {
      await responseJson<unknown>(
        await fetch(
          `/api/agents/${encodeURIComponent(detail.agent.id)}?expectedVersion=${currentVersion}`,
          { method: "DELETE" }
        )
      );
      router.push("/automacao/agentes");
    } catch (error) {
      setFeedback(
        error instanceof Error
          ? error.message
          : "Nao foi possivel arquivar o agente."
      );
    } finally {
      setPending(false);
    }
  }

  const latestVersion = useMemo(
    () =>
      detail?.versions.reduce<AgentVersion | null>(
        (latest, item) =>
          !latest || item.version > latest.version ? item : latest,
        null
      ) ?? null,
    [detail]
  );
  const currentVersion = latestVersion?.version ?? 0;
  const limits = record(latestVersion?.configuration.limits);

  if (mode === "catalog")
    return (
      <section className={styles.page} aria-labelledby="agents-title">
        <header className={styles.heading}>
          <div>
            <span>Automacao</span>
            <h1 id="agents-title">Agentes</h1>
            <p>
              Gerencie agentes versionados, confianca e disponibilidade no
              tenant atual.
            </p>
          </div>
          <Button onClick={() => setCreating((value) => !value)} type="button">
            {creating ? "Fechar criacao" : "Criar agente"}
          </Button>
        </header>
        {feedback ? (
          <p className={styles.feedback} role="status">
            {feedback}
          </p>
        ) : null}
        {creating ? (
          <form
            className={styles.createForm}
            onSubmit={(event) => {
              void createAgent(event);
            }}
          >
            <h2>Novo agente</h2>
            <div className={styles.formGrid}>
              <label>
                Nome
                <input maxLength={160} name="name" required />
              </label>
              <label>
                Slug
                <input
                  maxLength={160}
                  name="slug"
                  pattern="[a-z0-9]+(-[a-z0-9]+)*"
                  required
                />
              </label>
              <label>
                Risco
                <select defaultValue="low" name="riskLevel">
                  <option value="low">Baixo</option>
                  <option value="medium">Medio</option>
                  <option value="high">Alto</option>
                  <option value="critical">Critico</option>
                </select>
              </label>
              <label>
                Modelo (UUID)
                <input name="modelId" />
              </label>
            </div>
            <label>
              Descricao
              <textarea maxLength={2000} name="description" />
            </label>
            <label>
              Prompt inicial
              <textarea maxLength={100000} name="prompt" required />
            </label>
            <div className={styles.formGrid}>
              <label>
                Limites (JSON)
                <textarea defaultValue="{}" name="limits" />
              </label>
              <label>
                Skills (UUIDs separados por virgula)
                <textarea name="skillIds" />
              </label>
            </div>
            <Button disabled={pending} type="submit">
              {pending ? "Criando..." : "Criar e configurar"}
            </Button>
          </form>
        ) : null}
        {state === "loading" ? (
          <div className={styles.empty}>Carregando agentes...</div>
        ) : null}
        {state === "error" ? (
          <ErrorState message={feedback} retry={load} />
        ) : null}
        {state === "ready" ? (
          <div className={styles.agentList} aria-label="Catalogo de agentes">
            {agents.map((agent) => (
              <Link
                href={`/automacao/agente-config?agentId=${encodeURIComponent(agent.id)}`}
                key={agent.id}
                prefetch={false}
              >
                <span className={styles.trust}>
                  {Math.round(agent.trustScore)}%
                </span>
                <span>
                  <strong>{agent.name}</strong>
                  <small>
                    {agent.slug} · owner {compactId(agent.ownerUserId)}
                  </small>
                </span>
                <span>
                  <em data-enabled={agent.isEnabled}>
                    {agent.lifecycle === "draft"
                      ? "Rascunho"
                      : agent.lifecycle === "archived"
                        ? "Arquivado"
                        : "Ativo"}
                  </em>
                  <small>Risco {agent.riskLevel}</small>
                </span>
              </Link>
            ))}
            {agents.length === 0 ? (
              <div className={styles.empty}>
                <strong>Nenhum agente configurado</strong>
                <span>Crie o primeiro agente para iniciar a automacao.</span>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
    );

  if (!agentId)
    return (
      <section className={styles.page}>
        <div className={styles.empty}>
          <strong>Selecione um agente</strong>
          <Link href="/automacao/agentes">Abrir catalogo</Link>
        </div>
      </section>
    );
  if (state === "loading")
    return (
      <section className={styles.page}>
        <div className={styles.empty}>Carregando agente...</div>
      </section>
    );
  if (state === "error" || !detail)
    return (
      <section className={styles.page}>
        <ErrorState
          message={feedback || "Agente nao encontrado."}
          retry={load}
        />
      </section>
    );

  return (
    <section className={styles.page} aria-labelledby="agent-detail-title">
      <header className={styles.heading}>
        <div>
          <Link href="/automacao/agentes">Agentes</Link>
          <h1 id="agent-detail-title">{detail.agent.name}</h1>
          <p>
            {detail.agent.slug} · versao {currentVersion}
          </p>
        </div>
        <span className={styles.trustLarge}>
          {Math.round(detail.confidence)}%
        </span>
      </header>
      {feedback ? (
        <p className={styles.feedback} role="status">
          {feedback}
        </p>
      ) : null}
      <div className={styles.detailGrid}>
        <main>
          <section className={styles.summary}>
            <dl>
              <div>
                <dt>Estado</dt>
                <dd>
                  {detail.agent.isEnabled
                    ? "Ativo"
                    : latestVersion?.publishedAt
                      ? "Arquivado"
                      : "Rascunho"}
                </dd>
              </div>
              <div>
                <dt>Risco</dt>
                <dd>{detail.agent.riskLevel}</dd>
              </div>
              <div>
                <dt>Owner</dt>
                <dd>{compactId(detail.agent.ownerUserId)}</dd>
              </div>
              <div>
                <dt>Consumidores</dt>
                <dd>{detail.consumers.length}</dd>
              </div>
            </dl>
          </section>
          <section className={styles.versions}>
            <h2>Historico de versoes</h2>
            {detail.versions.map((version) => (
              <article key={version.id || version.version}>
                <strong>Versao {version.version}</strong>
                <span>Modelo {compactId(version.modelId)}</span>
                <small>{version.publishedAt ? "Publicada" : "Draft"}</small>
              </article>
            ))}
            {detail.versions.length === 0 ? (
              <p>Nenhuma versao registrada.</p>
            ) : null}
          </section>
        </main>
        <form
          className={styles.editor}
          onSubmit={(event) => {
            void updateAgent(event);
          }}
        >
          <h2>Nova configuracao</h2>
          <p>Salvar cria uma versao sobre a base {currentVersion}.</p>
          <label>
            Nome
            <input
              defaultValue={detail.agent.name}
              maxLength={160}
              name="name"
              required
            />
          </label>
          <label>
            Descricao
            <textarea
              defaultValue={detail.agent.description ?? ""}
              maxLength={2000}
              name="description"
            />
          </label>
          <label>
            Risco
            <select defaultValue={detail.agent.riskLevel} name="riskLevel">
              <option value="low">Baixo</option>
              <option value="medium">Medio</option>
              <option value="high">Alto</option>
              <option value="critical">Critico</option>
            </select>
          </label>
          <label>
            Prompt
            <textarea
              defaultValue={latestVersion?.systemPrompt ?? ""}
              maxLength={100000}
              name="prompt"
              required
            />
          </label>
          <label>
            Modelo (UUID)
            <input defaultValue={latestVersion?.modelId ?? ""} name="modelId" />
          </label>
          <label>
            Limites (JSON)
            <textarea
              defaultValue={JSON.stringify(limits, null, 2)}
              name="limits"
            />
          </label>
          <label>
            Skills (UUIDs separados por virgula)
            <textarea
              defaultValue={latestVersion?.skillIds.join(", ") ?? ""}
              name="skillIds"
            />
          </label>
          <label className={styles.check}>
            <input
              defaultChecked={detail.agent.isEnabled}
              name="isEnabled"
              type="checkbox"
            />{" "}
            Agente habilitado
          </label>
          <Button disabled={pending} type="submit">
            {pending ? "Salvando..." : "Salvar nova versao"}
          </Button>
          {confirmArchive ? (
            <StatePanel
              action={
                <>
                  <Button
                    disabled={pending}
                    onClick={() => {
                      void archiveAgent();
                    }}
                    tone="secondary"
                    type="button"
                  >
                    Confirmar arquivamento
                  </Button>
                  <Button
                    onClick={() => setConfirmArchive(false)}
                    tone="secondary"
                    type="button"
                  >
                    Cancelar
                  </Button>
                </>
              }
              className={styles.archiveConfirm}
              kind="error"
              title="Confirmar arquivamento"
            >
              O arquivamento falhara se houver consumidores ativos.
            </StatePanel>
          ) : (
            <Button
              onClick={() => setConfirmArchive(true)}
              tone="secondary"
              type="button"
            >
              Arquivar agente
            </Button>
          )}
        </form>
      </div>
    </section>
  );
}

function ErrorState({
  message,
  retry
}: {
  message: string;
  retry: () => Promise<void>;
}) {
  return (
    <div className={styles.empty}>
      <strong>Agentes indisponiveis</strong>
      <span>{message}</span>
      <Button
        onClick={() => {
          void retry();
        }}
        type="button"
      >
        Tentar novamente
      </Button>
    </div>
  );
}
