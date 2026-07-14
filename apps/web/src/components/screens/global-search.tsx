"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { Button, StatePanel } from "@bighead/ui";

import styles from "./global-search.module.css";

type SearchScope = "rooms" | "messages" | "tasks";
type SearchItem = { id: string; title: string; description?: string; status?: string; roomId?: string };
type SearchGroup = { scope: SearchScope; items: SearchItem[] };
type SearchResponse = { groups?: unknown; shortcuts?: unknown; removedCount?: unknown };

const scopeOptions: Array<{ value: SearchScope; label: string }> = [
  { value: "tasks", label: "Tarefas" },
  { value: "rooms", label: "Salas" },
  { value: "messages", label: "Mensagens" }
];
const scopeLabels: Record<SearchScope, string> = { tasks: "Tarefas", rooms: "Salas", messages: "Mensagens" };

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function normalizeGroups(value: unknown): SearchGroup[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((rawGroup) => {
    const group = record(rawGroup);
    if (!group) return [];
    const scope = group?.scope;
    if (scope !== "rooms" && scope !== "messages" && scope !== "tasks") return [];
    const items = Array.isArray(group.items) ? group.items.flatMap((rawItem) => {
      const item = record(rawItem);
      if (!item) return [];
      const id = typeof item?.id === "string" ? item.id : "";
      const title = typeof item?.title === "string" ? item.title : "";
      if (!id || !title) return [];
      const description = typeof item.description === "string" ? item.description : undefined;
      const status = typeof item.status === "string" ? item.status : undefined;
      const roomIdValue = item.roomId ?? item.room_id;
      const roomId = typeof roomIdValue === "string" ? roomIdValue : undefined;
      return [{
        id,
        title,
        ...(description ? { description } : {}),
        ...(status ? { status } : {}),
        ...(roomId ? { roomId } : {})
      }];
    }) : [];
    return [{ scope, items }];
  });
}

function resultHref(scope: SearchScope, item: SearchItem) {
  if (scope === "tasks") return `/tarefas/detalhe?taskId=${encodeURIComponent(item.id)}`;
  if (scope === "rooms") return `/colaboracao/sala?roomId=${encodeURIComponent(item.id)}`;
  if (!item.roomId) return null;
  return `/colaboracao/sala?roomId=${encodeURIComponent(item.roomId)}&messageId=${encodeURIComponent(item.id)}`;
}

export function GlobalSearch() {
  const [query, setQuery] = useState("");
  const [scopes, setScopes] = useState<SearchScope[]>(["tasks", "rooms", "messages"]);
  const [groups, setGroups] = useState<SearchGroup[]>([]);
  const [removedCount, setRemovedCount] = useState(0);
  const [state, setState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [message, setMessage] = useState("");
  const results = useRef<HTMLDivElement>(null);
  const activeRequest = useRef<AbortController | null>(null);

  useEffect(() => () => activeRequest.current?.abort(), []);

  const resultCount = groups.reduce((total, group) => total + group.items.filter((item) => resultHref(group.scope, item)).length, 0);

  function toggleScope(scope: SearchScope) {
    setScopes((current) => current.includes(scope) ? current.filter((item) => item !== scope) : [...current, scope]);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = query.trim();
    if (normalized.length < 2 || scopes.length === 0) {
      setState("error");
      setMessage(scopes.length === 0 ? "Selecione ao menos uma categoria." : "Digite ao menos dois caracteres.");
      return;
    }
    setState("loading");
    setMessage("");
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    try {
      const response = await fetch("/api/search/global", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ query: normalized, scopes }),
        signal: controller.signal
      });
      const payload = await response.json().catch(() => ({})) as SearchResponse & { detail?: unknown };
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Nao foi possivel concluir a busca.");
      if (controller.signal.aborted) return;
      setGroups(normalizeGroups(payload.groups));
      setRemovedCount(typeof payload.removedCount === "number" && payload.removedCount > 0 ? payload.removedCount : 0);
      setState("ready");
    } catch (error) {
      if (controller.signal.aborted) return;
      setGroups([]);
      setRemovedCount(0);
      setState("error");
      setMessage(error instanceof Error ? error.message : "Nao foi possivel concluir a busca.");
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null;
    }
  }

  function focusFirstResult(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "ArrowDown") return;
    const first = results.current?.querySelector<HTMLElement>("[data-search-result]");
    if (!first) return;
    event.preventDefault();
    first.focus();
  }

  function moveBetweenResults(event: KeyboardEvent<HTMLAnchorElement>) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const links = Array.from(results.current?.querySelectorAll<HTMLElement>("[data-search-result]") ?? []);
    const current = links.indexOf(event.currentTarget);
    if (current < 0) return;
    event.preventDefault();
    const next = event.key === "ArrowDown" ? (current + 1) % links.length : (current - 1 + links.length) % links.length;
    links[next]?.focus();
  }

  return (
    <section className={styles.searchPage} aria-labelledby="global-search-title">
      <header className={styles.heading}>
        <div>
          <span className={styles.eyebrow}>Busca global</span>
          <h1 id="global-search-title">Encontre trabalho e contexto</h1>
          <p>Pesquise tarefas, salas e mensagens disponíveis na organização atual.</p>
        </div>
      </header>

      <form className={styles.searchForm} onSubmit={(event) => { void submit(event); }}>
        <label htmlFor="global-search-query">O que você procura?</label>
        <div className={styles.searchRow}>
          <input
            autoComplete="off"
            id="global-search-query"
            maxLength={200}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={focusFirstResult}
            placeholder="Nome da tarefa, sala ou trecho de mensagem"
            type="search"
            value={query}
          />
          <Button disabled={state === "loading"} type="submit">{state === "loading" ? "Buscando..." : "Buscar"}</Button>
        </div>
        <fieldset className={styles.scopes}>
          <legend>Buscar em</legend>
          {scopeOptions.map((option) => (
            <label key={option.value}>
              <input checked={scopes.includes(option.value)} onChange={() => toggleScope(option.value)} type="checkbox" />
              <span>{option.label}</span>
            </label>
          ))}
        </fieldset>
      </form>

      <div aria-busy={state === "loading"} aria-live="polite" className={styles.results} ref={results}>
        {state === "idle" ? <div className={styles.guidance}><strong>Comece com uma palavra-chave</strong><span>Use dois ou mais caracteres para buscar.</span></div> : null}
        {state === "loading" ? <div className={styles.guidance}><strong>Buscando na organização...</strong><span>Os resultados serão agrupados por categoria.</span></div> : null}
        {state === "error" ? <StatePanel action={<Button onClick={() => setState("idle")} type="button">Tentar novamente</Button>} className={styles.error} kind="error" title="Busca não concluída"><span>{message}</span></StatePanel> : null}
        {state === "ready" && resultCount === 0 ? <div className={styles.guidance}><strong>Nenhum resultado encontrado</strong><span>Ajuste o termo ou amplie as categorias selecionadas.</span></div> : null}
        {state === "ready" && resultCount > 0 ? (
          <div className={styles.resultGroups}>
            <div className={styles.resultSummary}><strong>{resultCount} {resultCount === 1 ? "resultado" : "resultados"}</strong><span>Use as setas para percorrer a lista.</span></div>
            {groups.map((group) => {
              const linkedItems = group.items.flatMap((item) => {
                const href = resultHref(group.scope, item);
                return href ? [{ item, href }] : [];
              });
              if (!linkedItems.length) return null;
              return (
                <section className={styles.group} key={group.scope} aria-labelledby={`search-group-${group.scope}`}>
                  <h2 id={`search-group-${group.scope}`}>{scopeLabels[group.scope]}</h2>
                  <div className={styles.list}>
                    {linkedItems.map(({ item, href }) => (
                      <Link data-search-result href={href} key={`${group.scope}-${item.id}`} onKeyDown={moveBetweenResults} prefetch={false}>
                        <span><strong>{item.title}</strong>{item.description ? <small>{item.description}</small> : null}</span>
                        {item.status ? <em>{item.status.replaceAll("_", " ")}</em> : <em>Abrir</em>}
                      </Link>
                    ))}
                  </div>
                </section>
              );
            })}
            {removedCount > 0 ? <p className={styles.removed}>Alguns resultados não estão mais disponíveis para esta conta.</p> : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
