"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Button, Card } from "@bighead/ui";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { WorkspaceSnapshot } from "@/lib/mock-workspace";
import type { ScreenDefinition } from "@/lib/screen-catalog";
import { getScreenPlaybook, transitionPlaybook, type PlaybookState } from "./screen-playbooks";
import { CriticalJourney, criticalJourneyCodes } from "./critical-journey";
import { TaskOperationalPanels } from "./task-operational-panels";
import { Sprint2DomainExperience, sprint2DomainCodes } from "./sprint2-domain-experiences";

type ChecklistState = Record<string, boolean>;

type AdminMember = { name: string; role: "owner" | "reviewer" | "member" };

const workflowNodes: Node[] = [
  { id: "1", position: { x: 0, y: 40 }, data: { label: "Briefing" }, type: "input" },
  { id: "2", position: { x: 210, y: 40 }, data: { label: "Agente SDR" } },
  { id: "3", position: { x: 430, y: 40 }, data: { label: "Aprovacao" } },
  { id: "4", position: { x: 650, y: 40 }, data: { label: "Publicar" }, type: "output" }
];

const workflowEdges: Edge[] = [
  { id: "e1-2", source: "1", target: "2", label: "input" },
  { id: "e2-3", source: "2", target: "3", label: "score >= 0.8" },
  { id: "e3-4", source: "3", target: "4", label: "approved" }
];

function toneClass(tone?: "risk" | "accent" | "neutral") {
  if (tone === "risk") return "bh-metric bh-metric-risk";
  if (tone === "accent") return "bh-metric bh-metric-accent";
  return "bh-metric";
}

function slugValue(screen: ScreenDefinition) {
  return `/${screen.slug.join("/")}`;
}

function itemTone(text: string) {
  return text.toLowerCase().includes("risco") || text.toLowerCase().includes("falha")
    ? "bh-badge bh-badge-risk"
    : "bh-badge";
}

export function ScreenExperience({
  screen,
  snapshot
}: {
  screen: ScreenDefinition;
  snapshot: WorkspaceSnapshot;
}) {
  const [activeState, setActiveState] = useState(screen.states[0] ?? "default");
  const [query, setQuery] = useState("");
  const [feedback, setFeedback] = useState("");
  const [decision, setDecision] = useState("pending");
  const [wizardStep, setWizardStep] = useState(0);
  const [commandResult, setCommandResult] = useState("Nenhuma acao executada.");
  const [selectedRun, setSelectedRun] = useState("run-244");
  const [selectedFilter, setSelectedFilter] = useState("todas");
  const [webhookSecretPhase, setWebhookSecretPhase] = useState<"hidden" | "revealed" | "consumed">("hidden");
  const [webhookSecretValue, setWebhookSecretValue] = useState<string | null>(null);
  const [adminMembers, setAdminMembers] = useState<AdminMember[]>([
    { name: "Camila Moura", role: "owner" },
    { name: "Rafael Costa", role: "owner" },
    { name: "Time Conteudo", role: "reviewer" }
  ]);
  const [homePeriod, setHomePeriod] = useState("7d");
  const [homeRisk, setHomeRisk] = useState("all");
  const [sentMessages, setSentMessages] = useState<Array<{ id: string; text: string; status: "sending" | "failed" | "sent" }>>([]);
  const [taskPage, setTaskPage] = useState(1);
  const [decisionLocked, setDecisionLocked] = useState(false);
  const [mergePreviewed, setMergePreviewed] = useState(false);
  const [checklistState, setChecklistState] = useState<ChecklistState>(() =>
    Object.fromEntries(screen.checklist.map((item) => [item, false]))
  );
  const [playbookState, setPlaybookState] = useState<PlaybookState>({ phase: "blocked", revision: 0 });

  const searchableItems = useMemo(
    () =>
      [
        ...snapshot.inboxItems,
        ...snapshot.roomMoments,
        ...snapshot.taskMoments,
        ...snapshot.knowledgeMoments,
        ...snapshot.commercialMoments
      ].filter((item) =>
        `${item.title} ${item.description} ${item.meta}`.toLowerCase().includes(query.toLowerCase())
      ),
    [query, snapshot]
  );

  const currentDomainFeed = useMemo(() => {
    switch (screen.area) {
      case "Acesso":
        return snapshot.accessMoments;
      case "Governanca":
        return snapshot.governanceMoments;
      case "Automacao":
        return snapshot.automationMoments;
      case "Conhecimento":
        return snapshot.knowledgeMoments;
      case "Comercial":
        return snapshot.commercialMoments;
      case "Aprendizado":
        return snapshot.analyticsMoments;
      case "Administracao":
        return snapshot.adminMoments;
      default:
        return [...snapshot.roomMoments, ...snapshot.taskMoments];
    }
  }, [screen.area, snapshot]);

  const commandItems = useMemo(
    () =>
      snapshot.commandShortcuts.filter((shortcut) =>
        shortcut.toLowerCase().includes(query.toLowerCase())
      ),
    [query, snapshot.commandShortcuts]
  );

  useEffect(() => {
    if (screen.code === "T55" && window.sessionStorage.getItem("bighead-webhook-secret-consumed") === "true") {
      setWebhookSecretPhase("consumed");
    }
  }, [screen.code]);

  useEffect(() => {
    if (screen.code !== "T07") return;
    function executeKeyboardShortcut(event: KeyboardEvent) {
      if (!event.altKey || !/^[1-9]$/.test(event.key)) return;
      const item = commandItems[Number(event.key) - 1];
      if (!item) return;
      event.preventDefault();
      setCommandResult(`Atalho executado: ${item}.`);
    }
    window.addEventListener("keydown", executeKeyboardShortcut);
    return () => window.removeEventListener("keydown", executeKeyboardShortcut);
  }, [commandItems, screen.code]);

  function toggleChecklist(item: string) {
    setChecklistState((current) => ({ ...current, [item]: !current[item] }));
  }

  function renderScreenPlaybook() {
    const playbook = getScreenPlaybook(screen.code);
    if (!playbook) {
      throw new Error(`A tela ${screen.code} precisa de uma experiencia especifica.`);
    }
    const completed = Object.values(checklistState).filter(Boolean).length;

    return (
      <div className="bh-columns" data-testid={`screen-playbook-${screen.code}`}>
        <Card>
          <div className="bh-card-title">
            <h3>{playbook.heading}</h3>
            <span className="bh-label">{screen.module} · operacao especifica</span>
          </div>
          <p>{screen.summary}</p>
          <div className="bh-state-panel" data-domain={playbook.domain} data-testid={`playbook-state-${screen.code}`}>
            <strong>Precondicao</strong>
            <p>{playbook.precondition}</p>
            <span className="bh-badge">{playbookState.phase}</span>
            <div className="bh-inline">
              <Button onClick={() => setPlaybookState(transitionPlaybook(playbook, playbookState, "satisfy").state)} tone="secondary">
                Confirmar precondicao
              </Button>
              <Button onClick={() => {
                const transition = transitionPlaybook(playbook, playbookState, "reset");
                setPlaybookState(transition.state);
                setCommandResult(playbook.guard);
              }} tone="secondary">
                Simular guard
              </Button>
            </div>
          </div>
          <div className="bh-list-panel" aria-label={`Regras de ${screen.title}`}>
            {screen.checklist.map((item) => (
              <button
                aria-pressed={checklistState[item]}
                className="bh-row-button"
                key={item}
                onClick={() => {
                  toggleChecklist(item);
                  setCommandResult(`${item}: ${checklistState[item] ? "reaberto" : "validado"} em ${screen.code}.`);
                }}
                type="button"
              >
                <strong>{item}</strong>
                <span>{checklistState[item] ? "Validado nesta simulacao" : "Executar verificacao da regra"}</span>
              </button>
            ))}
          </div>
          <div className="bh-inline">
            <span className="bh-badge">{completed}/{screen.checklist.length} regras verificadas</span>
            <Button
              data-testid={`screen-playbook-action-${screen.code}`}
              onClick={() => {
                const transition = transitionPlaybook(playbook, playbookState, "apply");
                setPlaybookState(transition.state);
                setCommandResult(transition.effect ?? transition.error ?? playbook.guard);
              }}
            >
              {playbook.action}
            </Button>
          </div>
        </Card>
        <Card>
          <div className="bh-card-title">
            <h3>Contrato e estados</h3>
            <span className="bh-label">troca de transporte sem alterar a tela</span>
          </div>
          <div className="bh-inline" aria-label="Estados suportados">
            {screen.states.map((state) => (
              <Button
                key={state}
                onClick={() => setActiveState(state)}
                tone={activeState === state ? "primary" : "secondary"}
              >
                {state}
              </Button>
            ))}
          </div>
          {renderStatePanel()}
          <ul className="bh-list" aria-label="Endpoints da tela">
            {screen.endpoints.map((endpoint) => (
              <li key={endpoint}>
                <strong>{endpoint}</strong>
                <span>Resposta tipada e adaptada na fronteira de servico</span>
              </li>
            ))}
          </ul>
          <ul className="bh-list">
            {currentDomainFeed.slice(0, 2).map((item) => (
              <li key={item.title}>
                <strong>{item.title}</strong>
                <span>{item.description}</span>
                <small>{item.meta}</small>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    );
  }

  function renderStatePanel() {
    if (activeState.includes("empty")) {
      return (
        <div className="bh-state-panel">
          <strong>Estado vazio</strong>
          <p>Nenhum registro encontrado no tenant atual. A UI mantem a proxima acao visivel.</p>
        </div>
      );
    }

    if (
      activeState.includes("error") ||
      activeState.includes("invalid") ||
      activeState.includes("expired") ||
      activeState.includes("conflict")
    ) {
      return (
        <div className="bh-state-panel bh-state-panel-risk" role="status">
          <strong>Estado critico simulado</strong>
          <p>O fluxo mostra mensagem clara, preserva contexto e oferece retry seguro.</p>
        </div>
      );
    }

    if (activeState.includes("offline")) {
      return (
        <div className="bh-state-panel" role="status">
          <strong>Operacao offline</strong>
          <p>O rascunho permanece neste dispositivo e sera reenviado com a mesma chave idempotente ao reconectar.</p>
        </div>
      );
    }

    if (activeState.includes("permission")) {
      return (
        <div className="bh-state-panel" role="status">
          <strong>Acesso nao autorizado</strong>
          <p>Dados, contagens e acoes do recurso foram ocultados; solicite acesso ao administrador do tenant.</p>
        </div>
      );
    }

    return (
      <div className="bh-state-panel">
        <strong>Estado ativo</strong>
        <p>Fluxo conectado aos contratos da API e pronto para operacao no tenant atual.</p>
      </div>
    );
  }

  function renderAccessProductivity() {
    if (screen.code === "T01") {
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Acesso seguro</h3>
              <span className="bh-label">senha ou magic link sem enumeracao</span>
            </div>
            <div className="bh-inline">
              <Button
                tone={activeState === "default" ? "primary" : "secondary"}
                onClick={() => setActiveState("default")}
              >
                Senha
              </Button>
              <Button
                tone={activeState === "magic_link_sent" ? "primary" : "secondary"}
                onClick={() => setActiveState("magic_link_sent")}
              >
                Magic link
              </Button>
            </div>
            <div className="bh-form-grid">
              <label className="bh-field">
                <span>Email corporativo</span>
                <input defaultValue="camila@acme.ai" />
              </label>
              <label className="bh-field">
                <span>Senha</span>
                <input defaultValue="********" type="password" />
              </label>
            </div>
            <div className="bh-inline">
              <Button onClick={() => setCommandResult("Resposta anonima enviada sem revelar existencia do email.")}>
                Entrar
              </Button>
              <Button tone="secondary" onClick={() => setActiveState("invalid_credentials")}>
                Simular erro
              </Button>
            </div>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    if (screen.code === "T04") {
      const steps = ["Perfil", "Organizacao", "Objetivos", "Politicas"];
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Wizard de onboarding</h3>
              <span className="bh-label">progresso salvo entre sessoes</span>
            </div>
            <div className="bh-stepper" aria-label="Etapas do onboarding">
              {steps.map((step, index) => (
                <button
                  className={`bh-step ${index === wizardStep ? "bh-step-active" : ""}`}
                  key={step}
                  onClick={() => setWizardStep(index)}
                  type="button"
                >
                  {index + 1}. {step}
                </button>
              ))}
            </div>
            <div className="bh-state-panel">
              <strong>{steps[wizardStep]}</strong>
              <p>
                {wizardStep === 0 &&
                  "Captura nome, cargo e preferencias de trabalho com autosave local."}
                {wizardStep === 1 &&
                  "Define tenant, branding inicial e ownership sem perder o progresso."}
                {wizardStep === 2 &&
                  "Seleciona objetivos operacionais e playbooks de partida."}
                {wizardStep === 3 &&
                  "Aplica politica inicial de aprovacao e canais de notificacao."}
              </p>
            </div>
            <div className="bh-inline">
              <Button
                disabled={wizardStep === 0}
                onClick={() => setWizardStep((current) => Math.max(0, current - 1))}
              >
                Voltar
              </Button>
              <Button
                onClick={() =>
                  wizardStep === steps.length - 1
                    ? setCommandResult("Onboarding concluido e pronto para criar owner atomico.")
                    : setWizardStep((current) => Math.min(steps.length - 1, current + 1))
                }
              >
                {wizardStep === steps.length - 1 ? "Concluir" : "Proximo"}
              </Button>
            </div>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    if (screen.code === "T05") {
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Troca de organizacao</h3>
              <span className="bh-label">limpeza de cache e contexto visual</span>
            </div>
            <div className="bh-list-panel">
              {snapshot.organizations.map((organization) => (
                <button
                  className="bh-row-button"
                  key={organization}
                  onClick={() =>
                    setCommandResult(`Contexto trocado para ${organization}. Cache anterior invalidado.`)
                  }
                  type="button"
                >
                  <strong>{organization}</strong>
                  <span>Trocar tenant e limpar subscriptions</span>
                </button>
              ))}
            </div>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    if (screen.code === "T06") {
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Drill-down operacional</h3>
              <span className="bh-label">cartoes acionaveis preservando filtro</span>
            </div>
            <div className="bh-form-grid" aria-label="Filtros do dashboard">
              <label className="bh-field">
                <span>Periodo</span>
                <select aria-label="Periodo do dashboard" onChange={(event) => setHomePeriod(event.target.value)} value={homePeriod}>
                  <option value="7d">7 dias</option>
                  <option value="30d">30 dias</option>
                </select>
              </label>
              <label className="bh-field">
                <span>Risco</span>
                <select aria-label="Risco do dashboard" onChange={(event) => setHomeRisk(event.target.value)} value={homeRisk}>
                  <option value="all">Todos</option>
                  <option value="high">Alto</option>
                </select>
              </label>
            </div>
            <div className="bh-metric-grid">
              {screen.metrics.map((metric, index) => (
                <Link
                  className="bh-metric-card-button"
                  data-testid={`home-drilldown-${index}`}
                  href={`/operacao/home?period=${homePeriod}&risk=${homeRisk}&metric=${encodeURIComponent(metric.label)}`}
                  key={metric.label}
                >
                  <div className={toneClass(metric.tone)}>
                    <span>{metric.label}</span>
                    <strong>{metric.value}</strong>
                  </div>
                </Link>
              ))}
            </div>
          </Card>
          <Card>
            <div className="bh-card-title">
              <h3>Fila priorizada</h3>
              <span className="bh-label">falhas, SLA e aprovacoes criticas</span>
            </div>
            <ul className="bh-list">
              {snapshot.inboxItems.map((item) => (
                <li key={item.title}>
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                  <small>{item.meta}</small>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      );
    }

    if (screen.code === "T07") {
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Command palette</h3>
              <span className="bh-label">busca por atalhos e recursos</span>
            </div>
            <label className="bh-field">
              <span>Pesquisar</span>
              <input
                aria-label="Pesquisar no command palette"
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "ArrowDown") {
                    event.preventDefault();
                    document.querySelector<HTMLElement>("[data-command-index='0']")?.focus();
                  }
                }}
                placeholder="Buscar sala, tarefa, lead ou memoria"
                value={query}
              />
            </label>
            <div className="bh-columns">
              <div>
                <span className="bh-label">Atalhos</span>
                <ul className="bh-list">
                  {commandItems.map((item, index) => (
                    <li key={item}>
                      <button
                        aria-keyshortcuts={`Alt+${index + 1}`}
                        className="bh-row-button"
                        data-command-index={index}
                        onClick={() => setCommandResult(`Atalho executado: ${item}.`)}
                        type="button"
                      >
                        <strong>{item}</strong>
                        <span>Disponivel por teclado</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <span className="bh-label">Resultados</span>
                <ul className="bh-list">
                  {searchableItems.slice(0, 4).map((item) => (
                    <li key={item.title}>
                      <strong>{item.title}</strong>
                      <span>{item.description}</span>
                      <small>{item.meta}</small>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    if (screen.code === "T08") {
      const notifications = snapshot.inboxItems.filter((item) =>
        selectedFilter === "nao-lidas" ? item.meta.includes("vence") : true
      );
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Central de notificacoes</h3>
              <span className="bh-label">agrupamento e marcacao em lote</span>
            </div>
            <div className="bh-inline">
              <Button
                tone={selectedFilter === "todas" ? "primary" : "secondary"}
                onClick={() => setSelectedFilter("todas")}
              >
                Todas
              </Button>
              <Button
                tone={selectedFilter === "nao-lidas" ? "primary" : "secondary"}
                onClick={() => setSelectedFilter("nao-lidas")}
              >
                Nao lidas
              </Button>
              <Button tone="secondary" onClick={() => setCommandResult("11 notificacoes marcadas como lidas.")}>
                Marcar em lote
              </Button>
            </div>
            <ul className="bh-list">
              {notifications.map((item) => (
                <li key={item.title}>
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                  <small>{item.meta}</small>
                </li>
              ))}
            </ul>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    return renderScreenPlaybook();
  }

  function renderCollaborationAndTasks() {
    if (screen.code === "T11") {
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Sala conversacional</h3>
              <span className="bh-label">timeline, contexto e virar tarefa</span>
            </div>
            <div className="bh-chat">
              {snapshot.roomMoments.map((item, index) => (
                <button
                  className="bh-chat-message"
                  key={item.title}
                  onClick={() =>
                    setCommandResult(
                      index === 2
                        ? "Mensagem convertida em tarefa com origem, thread e anexos preservados."
                        : `Contexto aberto para ${item.title}.`
                    )
                  }
                  type="button"
                >
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                  <small>{item.meta}</small>
                </button>
              ))}
              {sentMessages.map((message) => (
                <div className="bh-chat-message" data-message-id={message.id} key={message.id}>
                  <strong>Voce</strong>
                  <span>{message.text}</span>
                  <small>{message.status === "sending" ? "Enviando com ID temporario" : message.status === "failed" ? "Falha no envio; pronta para retry" : "Entregue e reconciliada"}</small>
                </div>
              ))}
            </div>
          </Card>
          <Card data-testid="room-message-composer">
            <div className="bh-card-title">
              <h3>Composer operacional</h3>
              <span className="bh-label">realtime com reconciliacao de IDs temporarios</span>
            </div>
            <label className="bh-field">
              <span>Nova mensagem</span>
              <textarea
                aria-label="Nova mensagem da sala"
                onChange={(event) => setFeedback(event.target.value)}
                placeholder="Registrar contexto ou pedir acao ao agente"
                value={feedback}
              />
            </label>
            <div className="bh-inline">
              <Button
                disabled={!feedback.trim() || activeState.includes("offline")}
                onClick={() => {
                  const text = feedback.trim();
                  const temporaryId = `temp-${sentMessages.length + 1}`;
                  setSentMessages((current) => [...current, { id: temporaryId, text, status: "sending" }]);
                  setFeedback("");
                  setCommandResult(`Mensagem otimista inserida como ${temporaryId}; aguardando confirmacao.`);
                }}
              >
                Enviar
              </Button>
              <Button tone="secondary" onClick={() => setActiveState("offline")}>
                Simular offline
              </Button>
            </div>
            {sentMessages.some((message) => message.status !== "sent") && (
              <div className="bh-inline">
                <Button onClick={() => {
                  setSentMessages((current) => current.map((message, index) => message.status === "sending" ? { ...message, id: `msg-${index + 101}`, status: "sent" } : message));
                  setCommandResult("Confirmacao recebida; ID temporario reconciliado sem duplicacao.");
                }}>Confirmar entrega</Button>
                <Button tone="secondary" onClick={() => setSentMessages((current) => current.map((message) => message.status === "sending" ? { ...message, status: "failed" } : message))}>Simular falha de envio</Button>
                <Button tone="secondary" disabled={!sentMessages.some((message) => message.status === "failed")} onClick={() => {
                  setSentMessages((current) => current.map((message) => message.status === "failed" ? { ...message, status: "sending" } : message));
                  setCommandResult("Retry reutiliza a mensagem existente e a mesma chave idempotente.");
                }}>Tentar novamente</Button>
              </div>
            )}
          </Card>
        </div>
      );
    }

    if (screen.code === "T14") {
      const filteredTasks = snapshot.taskMoments.filter((item) =>
        `${item.title} ${item.description}`.toLowerCase().includes(query.toLowerCase())
      );
      const pageSize = 2;
      const visibleTasks = filteredTasks.slice(0, taskPage * pageSize);
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Inbox de tarefas</h3>
              <span className="bh-label">filtro, views e retorno por cursor</span>
            </div>
            <label className="bh-field">
              <span>Filtrar</span>
              <input
                aria-label="Filtrar tarefas"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Buscar por owner, risco ou workflow"
                value={query}
              />
            </label>
            <div className="bh-data-table">
              {visibleTasks.map((item) => (
                  <div className="bh-data-row" key={item.title}>
                    <strong>{item.title}</strong>
                    <span>{item.description}</span>
                    <small>{item.meta}</small>
                  </div>
                ))}
            </div>
            <Button
              disabled={visibleTasks.length >= filteredTasks.length}
              onClick={() => setTaskPage((page) => page + 1)}
              tone="secondary"
            >
              Carregar proxima pagina · cursor {taskPage}
            </Button>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    if (screen.code === "T15") {
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Criacao de tarefa</h3>
              <span className="bh-label">objetivo, risco e preview de roteamento</span>
            </div>
            <div className="bh-form-grid">
              <label className="bh-field">
                <span>Objetivo</span>
                <input defaultValue="Publicar campanha enterprise com aprovacao externa." />
              </label>
              <label className="bh-field">
                <span>Workflow</span>
                <input defaultValue="content.approval.publish" />
              </label>
              <label className="bh-field">
                <span>SLA</span>
                <input defaultValue="Hoje, 18:00" />
              </label>
              <label className="bh-field">
                <span>Risco</span>
                <input defaultValue="Moderado" />
              </label>
            </div>
            <div className="bh-inline">
              <Button onClick={() => setCommandResult("Preview: rotear para agente Content QA + aprovacao externa.")}>
                Prever roteamento
              </Button>
              <Button tone="secondary" onClick={() => setActiveState("validation_error")}>
                Simular validacao
              </Button>
            </div>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    if (screen.code === "T16") {
      return (
        <div className="bh-columns">
          <Card data-testid="task-transition-control">
            <div className="bh-card-title">
              <h3>Detalhe da tarefa</h3>
              <span className="bh-label">transicoes validas e conflito 409</span>
            </div>
            <div className="bh-state-machine">
              {["triaged", "in_progress", "ready_for_review", "approved", "done"].map((state) => (
                <button
                  className="bh-machine-node bh-machine-button"
                  key={state}
                  onClick={() =>
                    state === "approved"
                      ? setActiveState("conflict_409")
                      : setCommandResult(`Transicao aplicada: ${state}.`)
                  }
                  type="button"
                >
                  {state}
                </button>
              ))}
            </div>
            <p className="bh-footnote">
              O comentario do revisor e preservado mesmo quando a transicao devolve conflito de versao.
            </p>
            <label className="bh-field">
              <span>Comentario do revisor</span>
              <textarea aria-label="Comentario da transicao" onChange={(event) => setFeedback(event.target.value)} value={feedback} />
            </label>
            {activeState === "conflict_409" && (
              <Button onClick={() => { setActiveState("default"); setCommandResult("Versao recarregada; comentario local preservado."); }}>
                Recarregar versao
              </Button>
            )}
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    if (screen.code === "T17") {
      const runs = ["run-244", "run-245", "run-246"];
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Monitor de execucao</h3>
              <span className="bh-label">run, heartbeat, tokens e tentativas</span>
            </div>
            <div className="bh-inline">
              {runs.map((run) => (
                <Button
                  disabled={decisionLocked}
                  key={run}
                  tone={selectedRun === run ? "primary" : "secondary"}
                  onClick={() => setSelectedRun(run)}
                >
                  {run}
                </Button>
              ))}
            </div>
            <div className="bh-state-panel">
              <strong>{selectedRun}</strong>
              <p>Heartbeat 22s • tokens 18k • ultima tentativa com latencia estavel.</p>
            </div>
            <TaskOperationalPanels taskTitle={selectedRun} />
            <div className="bh-inline">
              <Button onClick={() => setCommandResult(`Retry solicitado para ${selectedRun}.`)}>
                Retry
              </Button>
              <Button tone="secondary" onClick={() => setCommandResult(`Cancelamento solicitado para ${selectedRun}.`)}>
                Cancelar
              </Button>
            </div>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    return renderScreenPlaybook();
  }

  function renderGovernance() {
    if (screen.code === "T21") {
      return (
        <div className="bh-columns">
          <Card data-testid="approval-decision-control">
            <div className="bh-card-title">
              <h3>Decisao de aprovacao</h3>
              <span className="bh-label">contexto, scorecard e decisao imutavel</span>
            </div>
            <div className="bh-inline">
              {["approved", "changes_requested", "rejected"].map((value) => (
                <Button
                  disabled={decisionLocked}
                  key={value}
                  tone={decision === value ? "primary" : "secondary"}
                  onClick={() => setDecision(value)}
                >
                  {value}
                </Button>
              ))}
            </div>
            <label className="bh-field">
              <span>Comentario do revisor</span>
              <textarea
                aria-label="Comentario da aprovacao"
                onChange={(event) => setFeedback(event.target.value)}
                placeholder="Explique o motivo da decisao"
                value={feedback}
                disabled={decisionLocked}
              />
            </label>
            <Button
              disabled={decision === "pending" || decisionLocked}
              onClick={() => {
                setDecisionLocked(true);
                setCommandResult(`Decisao ${decision} registrada, imutavel e auditavel.`);
              }}
            >
              Registrar decisao
            </Button>
          </Card>
          <Card>
            <div className="bh-card-title">
              <h3>Impacto da decisao</h3>
              <span className="bh-label">nova rodada, bloqueio ou liberacao</span>
            </div>
            {renderStatePanel()}
          </Card>
        </div>
      );
    }

    if (screen.code === "T23") {
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Simulador de politica</h3>
              <span className="bh-label">risco, segregacao e lacunas</span>
            </div>
            <div className="bh-form-grid">
              <label className="bh-field">
                <span>Risco</span>
                <input defaultValue="alto" />
              </label>
              <label className="bh-field">
                <span>Acao</span>
                <input defaultValue="publicar conteudo externo" />
              </label>
            </div>
            <Button onClick={() => setCommandResult("Simulacao: dupla aprovacao exigida e autoaprovacao bloqueada.")}>
              Simular impacto
            </Button>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    return renderScreenPlaybook();
  }

  function renderAutomation() {
    if (screen.code === "T28") {
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Teste de skill</h3>
              <span className="bh-label">schema, timeout e retries</span>
            </div>
            <label className="bh-field">
              <span>Payload de validacao</span>
              <textarea defaultValue='{"company":"Atlas Logistics","tenantId":"acme-growth"}' />
            </label>
            <div className="bh-inline">
              <Button onClick={() => setCommandResult("Validacao concluida: 1 warning, 0 leaks, 812ms.")}>
                Executar teste
              </Button>
              <Button tone="secondary" onClick={() => setActiveState("timeout")}>
                Simular timeout
              </Button>
            </div>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    if (screen.code === "T32") {
      return (
        <div className="bh-columns">
          <Card className="bh-flow-card">
            <div className="bh-card-title">
              <h3>Editor visual de workflow</h3>
              <span className="bh-label">canvas real com validacao de grafo</span>
            </div>
            <div className="bh-flow-canvas" role="img" aria-label="Canvas do workflow outbound">
              <ReactFlow fitView nodes={workflowNodes} edges={workflowEdges}>
                <MiniMap />
                <Controls />
                <Background />
              </ReactFlow>
            </div>
            <div className="bh-inline">
              <Button onClick={() => setCommandResult("Workflow validado: 2 warnings e nenhum ciclo critico.")}>
                Validar grafo
              </Button>
              <Button tone="secondary" onClick={() => setActiveState("invalid_graph")}>
                Simular grafo invalido
              </Button>
            </div>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    return renderScreenPlaybook();
  }

  function renderKnowledge() {
    if (screen.code === "T38") {
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Busca semantica</h3>
              <span className="bh-label">score, fonte e debug RAG</span>
            </div>
            <label className="bh-field">
              <span>Consulta</span>
              <input
                aria-label="Consulta semantica"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Ex.: onboarding enterprise"
                value={query}
              />
            </label>
            <ul className="bh-list">
              {searchableItems.slice(0, 3).map((item) => (
                <li key={item.title}>
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                  <small>{item.meta}</small>
                </li>
              ))}
            </ul>
            <Button onClick={() => setCommandResult("Resultados atualizados com score e fonte auditavel.")}>
              Executar busca
            </Button>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    return renderScreenPlaybook();
  }

  function renderCommercial() {
    if (screen.code === "T40") {
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title"><h3>Deduplicacao assistida</h3><span className="bh-label">preview obrigatorio antes do merge</span></div>
            <ul className="bh-list" aria-label="Preview do merge">
              <li><strong>Registro principal</strong><span>Camila Moura · consentimento valido</span></li>
              <li><strong>Registro duplicado</strong><span>Camila M. · 12 atividades preservadas</span></li>
            </ul>
            <div className="bh-inline">
              <Button onClick={() => { setMergePreviewed(true); setCommandResult("Preview calculado: origem, consentimento e 12 atividades serao preservados."); }}>Gerar preview</Button>
              <Button disabled={!mergePreviewed} onClick={() => { setMergePreviewed(false); setCommandResult("Merge confirmado com trilha de auditoria; registros de origem preservados."); }}>Confirmar merge</Button>
            </div>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    if (screen.code === "T42") {
      const columns = [
        { title: "Discovery", items: ["Atlas Logistics", "Northwind Cloud"] },
        { title: "Proposal", items: ["Acme Enterprise"] },
        { title: "Negotiation", items: ["FBR Ventures"] }
      ];
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Pipeline e oportunidades</h3>
              <span className="bh-label">board com guard rails por etapa</span>
            </div>
            <div className="bh-board">
              {columns.map((column) => (
                <div className="bh-board-column" key={column.title}>
                  <strong>{column.title}</strong>
                  {column.items.map((item) => (
                    <button
                      className="bh-row-button"
                      key={item}
                      onClick={() =>
                        setCommandResult(
                          `${item} movida com validacao de campos obrigatorios e forecast preservado.`
                        )
                      }
                      type="button"
                    >
                      <span>{item}</span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    if (screen.code === "T45") {
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Calendario editorial</h3>
              <span className="bh-label">agendamento, falha de provider e retry</span>
            </div>
            <ul className="bh-list">
              {snapshot.commercialMoments.map((item) => (
                <li key={item.title}>
                  <button
                    className="bh-row-button"
                    onClick={() => setCommandResult(`Retry seguro solicitado para ${item.title}.`)}
                    type="button"
                  >
                    <strong>{item.title}</strong>
                    <span>{item.description}</span>
                    <small>{item.meta}</small>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    return renderScreenPlaybook();
  }

  function renderAnalytics() {
    if (screen.code === "T47") {
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Configuracao e resultado do experimento</h3>
              <span className="bh-label">variantes, janela e lock apos start</span>
            </div>
            <div className="bh-form-grid">
              <label className="bh-field">
                <span>Hipotese</span>
                <input defaultValue="CTA contextual aumenta SQL rate." />
              </label>
              <label className="bh-field">
                <span>Janela</span>
                <input defaultValue="14 dias" />
              </label>
            </div>
            <div className="bh-inline">
              <Button onClick={() => setCommandResult("Experimento iniciado. Campos criticos agora estao bloqueados.")}>
                Iniciar experimento
              </Button>
              <Button tone="secondary" onClick={() => setActiveState("locked")}>
                Simular lock
              </Button>
            </div>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    return renderScreenPlaybook();
  }

  function renderAdministration() {
    if (screen.code === "T54") {
      const ownerCount = adminMembers.filter((member) => member.role === "owner").length;
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Membros e papeis</h3>
              <span className="bh-label">guard rail do ultimo owner</span>
            </div>
            <ul className="bh-list">
              {adminMembers.map((member) => {
                const isProtectedLastOwner = member.role === "owner" && ownerCount === 1;
                return (
                <li key={member.name}>
                  <button
                    aria-label={`Rebaixar ou remover ${member.name}`}
                    className="bh-row-button"
                    disabled={isProtectedLastOwner}
                    onClick={() => {
                      setAdminMembers((current) => current.map((candidate) =>
                        candidate.name === member.name ? { ...candidate, role: "member" } : candidate
                      ));
                      setCommandResult(`Papel de ${member.name} alterado; ao menos um owner foi preservado.`);
                    }}
                    type="button"
                  >
                    <strong>{member.name} · {member.role}</strong>
                    <span>{isProtectedLastOwner ? "Ultimo owner protegido" : "Alterar papel ou remover"}</span>
                  </button>
                </li>
              );})}
            </ul>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    if (screen.code === "T55") {
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Integracoes e webhooks</h3>
              <span className="bh-label">secret exibido uma vez</span>
            </div>
            <div className="bh-state-panel">
              <strong>Webhook primary-social</strong>
              <p data-testid="webhook-secret-value">
                {webhookSecretPhase === "hidden" && "Clique para revelar o secret uma unica vez."}
                {webhookSecretPhase === "revealed" && webhookSecretValue}
                {webhookSecretPhase === "consumed" && "Secret consumido; gere uma rotacao para obter outro."}
              </p>
            </div>
            <div className="bh-inline">
              {webhookSecretPhase === "hidden" ? (
                <Button onClick={() => {
                  setWebhookSecretValue(`whsec_${crypto.randomUUID().replaceAll("-", "")}`);
                  setWebhookSecretPhase("revealed");
                }}>Revelar secret</Button>
              ) : webhookSecretPhase === "revealed" ? (
                <Button onClick={() => {
                  setWebhookSecretValue(null);
                  setWebhookSecretPhase("consumed");
                  window.sessionStorage.setItem("bighead-webhook-secret-consumed", "true");
                }}>Ocultar definitivamente</Button>
              ) : (
                <Button disabled>Secret ja consumido</Button>
              )}
              <Button tone="secondary" onClick={() => setCommandResult("Delivery de teste enfileirada com sucesso.")}>
                Testar entrega
              </Button>
            </div>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    if (screen.code === "T56") {
      return (
        <div className="bh-columns">
          <Card>
            <div className="bh-card-title">
              <h3>Privacidade e auditoria</h3>
              <span className="bh-label">jobs LGPD e trilha append-only</span>
            </div>
            <div className="bh-list-panel" aria-label="Jobs LGPD">
              {[
                { title: "Exportacao de dados pessoais", scope: "Perfil, memberships e auditoria do titular", impact: "Gera arquivo criptografado; nenhuma exclusao", status: "running · 62%" },
                { title: "Exclusao de titular", scope: "Dados pessoais sem legal hold", impact: "Anonimizacao irreversivel apos aprovacao", status: "awaiting_approval" }
              ].map((item) => (
                <button
                  className="bh-row-button"
                  key={item.title}
                  onClick={() => setCommandResult(`Job auditado: ${item.title}.`)}
                  type="button"
                >
                  <strong>{item.title}</strong>
                  <span>Escopo: {item.scope}</span>
                  <span>Impacto: {item.impact}</span>
                  <small>Status: {item.status}</small>
                </button>
              ))}
            </div>
            <div aria-label="Eventos de auditoria append-only">
              <h4>Eventos de auditoria append-only</h4>
              <ul className="bh-list">
                {snapshot.adminMoments.slice(0, 2).map((item) => (
                  <li data-testid="audit-event" key={item.title}>
                    <strong>{item.title}</strong>
                    <span>{item.description}</span>
                    <small>{item.meta}</small>
                  </li>
                ))}
              </ul>
              <p className="bh-label">Somente leitura · sem editar ou excluir</p>
            </div>
          </Card>
          <Card>{renderStatePanel()}</Card>
        </div>
      );
    }

    return renderScreenPlaybook();
  }

  function renderPrimaryExperience() {
    if (sprint2DomainCodes.has(screen.code)) {
      return <Sprint2DomainExperience
        analyticsDrilldowns={snapshot.analyticsDrilldowns}
        code={screen.code}
        tenantId={snapshot.currentOrganizationId ?? snapshot.currentOrganization}
      />;
    }
    if (criticalJourneyCodes.has(screen.code)) {
      return <CriticalJourney code={screen.code} snapshot={snapshot} />;
    }
    if (screen.area === "Acesso" || (screen.area === "Operacao" && screen.code <= "T09")) {
      return renderAccessProductivity();
    }

    if (screen.area === "Operacao") {
      return renderCollaborationAndTasks();
    }

    if (screen.area === "Governanca") {
      return renderGovernance();
    }

    if (screen.area === "Automacao") {
      return renderAutomation();
    }

    if (screen.area === "Conhecimento") {
      return renderKnowledge();
    }

    if (screen.area === "Comercial") {
      return renderCommercial();
    }

    if (screen.area === "Aprendizado") {
      return renderAnalytics();
    }

    return renderAdministration();
  }

  if (activeState.includes("permission")) {
    return (
      <section className="bh-screen" data-testid="permission-boundary">
        <Card>
          <span className="bh-eyebrow">{screen.code} · {screen.area}</span>
          <h2>{screen.title}</h2>
          {renderStatePanel()}
        </Card>
      </section>
    );
  }

  return (
    <section className="bh-screen">
      <div className="bh-screen-hero">
        <Card className="bh-screen-hero-card">
          <div className="bh-screen-heading">
            <div>
              <span className="bh-eyebrow">
                {screen.code} • {screen.area} • {screen.module}
              </span>
              <h2>{screen.title}</h2>
              <p>{screen.summary}</p>
            </div>
            <div className="bh-screen-actions">
              <span className="bh-badge">{screen.states.join(" • ")}</span>
              <Link className="bh-chip" href="/catalogo">
                Ver componentes
              </Link>
            </div>
          </div>
        </Card>
      </div>

      <div className="bh-metric-grid">
        {screen.metrics.map((metric) => (
          <Card key={metric.label}>
            <button
              className="bh-metric-card-button"
              onClick={() => setCommandResult(`Filtro aplicado em ${metric.label}.`)}
              type="button"
            >
              <div className={toneClass(metric.tone)}>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
              </div>
            </button>
          </Card>
        ))}
      </div>

      <div className="bh-columns">
        <Card>
          <div className="bh-card-title">
            <h3>Estados previstos</h3>
            <span className="bh-label">loading, vazio, erro, offline, sem permissao</span>
          </div>
          <div className="bh-state-machine">
            {screen.states.map((state) => (
              <button
                className={`bh-machine-node bh-machine-button ${activeState === state ? "bh-machine-node-active" : ""}`}
                key={state}
                onClick={() => setActiveState(state)}
                type="button"
              >
                {state}
              </button>
            ))}
          </div>
          {renderStatePanel()}
        </Card>

        <Card>
          <div className="bh-card-title">
            <h3>Contratos backend</h3>
            <span className="bh-label">Snapshot OpenAPI e handoff</span>
          </div>
          <ul className="bh-list">
            {screen.endpoints.map((endpoint) => (
              <li key={endpoint}>{endpoint}</li>
            ))}
          </ul>
          <Link className="bh-chip" href="/catalogo">
            Ver catalogo e docs
          </Link>
        </Card>
      </div>

      {renderPrimaryExperience()}

      <div className="bh-columns">
        <Card>
          <div className="bh-card-title">
            <h3>Checklist de implementacao</h3>
            <span className="bh-label">criterios de aceite visual e de contrato</span>
          </div>
          <ul className="bh-list bh-checklist">
            {screen.checklist.map((item) => (
              <li key={item}>
                <label className="bh-check-item">
                  <input
                    checked={Boolean(checklistState[item])}
                    onChange={() => toggleChecklist(item)}
                    type="checkbox"
                  />
                  <span>{item}</span>
                </label>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <div className="bh-card-title">
            <h3>Contexto cruzado</h3>
            <span className="bh-label">itens operacionais do dominio</span>
          </div>
          <div className="bh-list-panel">
            {currentDomainFeed.map((item) => (
              <button
                className="bh-row-button"
                key={item.title}
                onClick={() => setCommandResult(`Contexto aberto: ${item.title}.`)}
                type="button"
              >
                <strong>{item.title}</strong>
                <span>{item.description}</span>
                <small>{item.meta}</small>
              </button>
            ))}
          </div>
        </Card>
      </div>

      <div className="bh-columns">
        <Card>
          <div className="bh-card-title">
            <h3>Console de acao</h3>
            <span className="bh-label">resultado do fluxo simulado</span>
          </div>
          <div className="bh-state-panel" role="status">
            <strong>Ultimo evento</strong>
            <p>{commandResult}</p>
          </div>
          <div className="bh-inline">
            {screen.checklist.slice(0, 3).map((item) => (
              <span className={itemTone(item)} key={item}>
                {item}
              </span>
            ))}
          </div>
        </Card>

        <Card>
          <div className="bh-card-title">
            <h3>Rota atual</h3>
            <span className="bh-label">navegacao e acessibilidade</span>
          </div>
          <ul className="bh-list">
            <li>
              <strong>URL</strong>
              <span>{slugValue(screen)}</span>
            </li>
            <li>
              <strong>Teclado</strong>
              <span>Todos os CTAs principais sao focaveis e acionaveis por Enter/Espaco.</span>
            </li>
            <li>
              <strong>Reduced motion</strong>
              <span>Componentes mantem legibilidade sem depender de animacao.</span>
            </li>
          </ul>
        </Card>
      </div>
    </section>
  );
}
