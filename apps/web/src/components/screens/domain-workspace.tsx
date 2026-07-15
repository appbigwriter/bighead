"use client";

import { Button } from "@bighead/ui";
import Link from "next/link";
import { useMemo, useState } from "react";

import type { WorkspaceSnapshot } from "@/lib/mock-workspace";
import type { ScreenDefinition } from "@/lib/screen-catalog";
import styles from "./domain-workspace.module.css";

type DomainConfig = {
  eyebrow: string;
  feedTitle: string;
  emptyCopy: string;
  primaryAction: { href: string; label: string };
};

type AdminMember = { id: string; name: string; email: string; role: "owner" | "admin" | "manager" | "member"; status: "active" | "inactive" };
type AdminInvite = { id: string; email: string; role: AdminMember["role"]; expiresInHours: number; status: "pending" | "sent" };
type AdminTeam = { id: string; name: string; executorKind: "agent" | "team"; executorId: string };
type AdminOrganization = { name: string; timezone: string; domain: string; brandColor: string };
type AdminIntegration = { id: string; name: string; kind: "webhook" | "sso" | "crm"; status: "connected" | "failed" | "pending"; secretPreview: string };
type AdminPrivacyRequest = { id: string; kind: "export" | "deletion" | "legal_hold"; subject: string; status: "open" | "running" | "done" };
type AreaAction = { label: string; href: string; note: string };

const domainConfig: Record<ScreenDefinition["area"], DomainConfig> = {
  Acesso: { eyebrow: "Conta e acesso", feedTitle: "Atividade de acesso", emptyCopy: "Nenhuma atividade de acesso requer atencao.", primaryAction: { href: "/operacao/perfil", label: "Abrir perfil" } },
  Operacao: { eyebrow: "Operacao", feedTitle: "Trabalho recente", emptyCopy: "Nenhum trabalho recente nesta organizacao.", primaryAction: { href: "/tarefas/inbox", label: "Abrir tarefas" } },
  Governanca: { eyebrow: "Governanca", feedTitle: "Decisoes e riscos", emptyCopy: "Nenhuma decisao ou risco requer atencao.", primaryAction: { href: "/governanca/aprovacoes", label: "Abrir aprovacoes" } },
  Automacao: { eyebrow: "Automacao", feedTitle: "Saude da automacao", emptyCopy: "Nenhuma alteracao recente em agentes ou workflows.", primaryAction: { href: "/automacao/agentes", label: "Abrir agentes" } },
  Conhecimento: { eyebrow: "Conhecimento", feedTitle: "Fontes e memoria", emptyCopy: "Nenhuma atualizacao recente nas fontes de conhecimento.", primaryAction: { href: "/conhecimento/busca-semantica", label: "Buscar conhecimento" } },
  Comercial: { eyebrow: "Comercial", feedTitle: "Movimentos comerciais", emptyCopy: "Nenhum movimento comercial recente.", primaryAction: { href: "/comercial/leads", label: "Abrir leads" } },
  Aprendizado: { eyebrow: "Analise", feedTitle: "Sinais do periodo", emptyCopy: "Nenhum sinal novo disponivel para este periodo.", primaryAction: { href: "/operacao/home", label: "Ver operacao" } },
  Administracao: { eyebrow: "Administracao", feedTitle: "Alteracoes recentes", emptyCopy: "Nenhuma alteracao administrativa recente.", primaryAction: { href: "/administracao/organizacao", label: "Abrir organizacao" } }
};

function feedForArea(area: ScreenDefinition["area"], snapshot: WorkspaceSnapshot) {
  switch (area) {
    case "Acesso": return snapshot.accessMoments;
    case "Governanca": return snapshot.governanceMoments;
    case "Automacao": return snapshot.automationMoments;
    case "Conhecimento": return snapshot.knowledgeMoments;
    case "Comercial": return snapshot.commercialMoments;
    case "Aprendizado": return snapshot.analyticsMoments;
    case "Administracao": return snapshot.adminMoments;
    default: return [...snapshot.taskMoments, ...snapshot.roomMoments];
  }
}

function areaActions(area: ScreenDefinition["area"]): AreaAction[] {
  switch (area) {
    case "Acesso":
      return [
        { label: "Trocar organizacao", href: "/acesso/organizacoes", note: "Seleciona tenant e limpa contexto." },
        { label: "Onboarding", href: "/acesso/onboarding", note: "Completa owner e politicas." },
        { label: "Convite", href: "/acesso/convite", note: "Aceita ou recusa acesso." }
      ];
    case "Operacao":
      return [
        { label: "Tarefas", href: "/tarefas/inbox", note: "Fila do trabalho vivo." },
        { label: "Criar tarefa", href: "/tarefas/criar", note: "Executor, SLA e origem." },
        { label: "Notificacoes", href: "/operacao/notificacoes", note: "Atribuicoes e alertas." }
      ];
    case "Governanca":
      return [
        { label: "Aprovacoes", href: "/governanca/aprovacoes", note: "Decisoes pendentes." },
        { label: "Portal externo", href: "/governanca/portal-externo", note: "Resposta via token." },
        { label: "Politicas", href: "/governanca/politicas", note: "Regras e segregacao." }
      ];
    case "Automacao":
      return [
        { label: "Agentes", href: "/automacao/agentes", note: "Catalogo versionado." },
        { label: "Skills", href: "/automacao/skills", note: "Health e schema." },
        { label: "Workflows", href: "/automacao/workflows", note: "Fluxos e grafo." }
      ];
    case "Conhecimento":
      return [
        { label: "Biblioteca", href: "/conhecimento/biblioteca", note: "Documentos e ingestao." },
        { label: "Busca", href: "/conhecimento/busca-semantica", note: "Score e fonte." },
        { label: "Memoria", href: "/conhecimento/memoria", note: "Fatos e contestacao." }
      ];
    case "Comercial":
      return [
        { label: "Leads", href: "/comercial/leads", note: "Owner e score." },
        { label: "Pipeline", href: "/comercial/pipeline", note: "Forecast e etapas." },
        { label: "Conteudo", href: "/comercial/conteudo", note: "Brief e publicacao." }
      ];
    case "Aprendizado":
      return [
        { label: "Dashboard", href: "/aprendizado/dashboard-executivo", note: "KPI e drilldown." },
        { label: "Custos", href: "/aprendizado/custos", note: "Budget e quotas." },
        { label: "Funil", href: "/aprendizado/funil", note: "Atribuicao declarada." }
      ];
    case "Administracao":
      return [
        { label: "Organizacao", href: "/administracao/organizacao", note: "Branding e defaults." },
        { label: "Membros", href: "/administracao/membros", note: "Convites e papeis." },
        { label: "Auditoria", href: "/administracao/privacidade-auditoria", note: "LGPD e append-only." }
      ];
    default:
      return [];
  }
}

function utilityMeta(meta: string) {
  return meta.split(/[â€¢·•]/).map((part) => part.trim()).filter((part) => part && !/^T\d{2}(?:\s*->\s*T\d{2})?$/i.test(part)).join(" · ");
}

export function DomainWorkspace({ screen, snapshot }: { screen: ScreenDefinition; snapshot: WorkspaceSnapshot }) {
  const config = domainConfig[screen.area];
  const items = feedForArea(screen.area, snapshot).slice(0, 5);
  const actions = areaActions(screen.area);
  const currentPath = `/${screen.slug.join("/")}`;
  const related = snapshot.screens.filter((item) => item.area === screen.area && `/${item.slug.join("/")}` !== currentPath).slice(0, 6);
  const [members, setMembers] = useState<AdminMember[]>([
    { id: "mem-1", name: "Camila Moura", email: "camila@acme.ai", role: "owner", status: "active" },
    { id: "mem-2", name: "Rafael Costa", email: "rafael@acme.ai", role: "admin", status: "active" },
    { id: "mem-3", name: "Time Conteudo", email: "conteudo@acme.ai", role: "manager", status: "active" }
  ]);
  const [invites, setInvites] = useState<AdminInvite[]>([
    { id: "inv-1", email: "ana@acme.ai", role: "member", expiresInHours: 72, status: "sent" }
  ]);
  const [teams, setTeams] = useState<AdminTeam[]>([
    { id: "team-1", name: "Time Comercial", executorKind: "team", executorId: "team-comercial" },
    { id: "team-2", name: "Agente SDR", executorKind: "agent", executorId: "agent-sdr-01" }
  ]);
  const [organization, setOrganization] = useState<AdminOrganization>({
    name: snapshot.currentOrganization,
    timezone: "America/Sao_Paulo",
    domain: "acme.ai",
    brandColor: "#0f766e"
  });
  const [integrations, setIntegrations] = useState<AdminIntegration[]>([
    { id: "int-1", name: "Slack", kind: "webhook", status: "connected", secretPreview: "shk_1a2b…" },
    { id: "int-2", name: "Salesforce", kind: "crm", status: "pending", secretPreview: "cr_7f8e…" }
  ]);
  const [privacyRequests] = useState<AdminPrivacyRequest[]>([
    { id: "pr-1", kind: "export", subject: "camila@acme.ai", status: "open" },
    { id: "pr-2", kind: "deletion", subject: "rafael@acme.ai", status: "running" }
  ]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<AdminMember["role"]>("member");
  const [teamName, setTeamName] = useState("");
  const [teamExecutorKind, setTeamExecutorKind] = useState<AdminTeam["executorKind"]>("team");
  const [teamExecutorId, setTeamExecutorId] = useState("");
  const [integrationName, setIntegrationName] = useState("");
  const [integrationKind, setIntegrationKind] = useState<AdminIntegration["kind"]>("webhook");
  const [integrationSecret, setIntegrationSecret] = useState("");
  const ownerCount = useMemo(() => members.filter((member) => member.role === "owner" && member.status === "active").length, [members]);

  function updateMember(memberId: string, nextRole?: AdminMember["role"], nextStatus?: AdminMember["status"]) {
    setMembers((current) => current.map((member) => {
      if (member.id !== memberId) return member;
      return {
        ...member,
        role: nextRole ?? member.role,
        status: nextStatus ?? member.status
      };
    }));
  }

  function addInvite() {
    const email = inviteEmail.trim();
    if (!email) return;
    setInvites((current) => [{ id: crypto.randomUUID(), email, role: inviteRole, expiresInHours: 72, status: "sent" }, ...current]);
    setInviteEmail("");
  }

  function addTeam() {
    const name = teamName.trim();
    const executorId = teamExecutorId.trim();
    if (!name || !executorId) return;
    setTeams((current) => [{ id: crypto.randomUUID(), name, executorKind: teamExecutorKind, executorId }, ...current]);
    setTeamName("");
    setTeamExecutorId("");
  }

  function addIntegration() {
    const name = integrationName.trim();
    const secret = integrationSecret.trim();
    if (!name || !secret) return;
    setIntegrations((current) => [{ id: crypto.randomUUID(), name, kind: integrationKind, status: "pending", secretPreview: `${secret.slice(0, 6)}…` }, ...current]);
    setIntegrationName("");
    setIntegrationSecret("");
  }

  if (screen.area === "Administracao") {
    return (
      <section className={styles.page} aria-labelledby="domain-workspace-title">
        <header className={styles.heading}>
          <div>
            <span>{config.eyebrow}</span>
            <h1 id="domain-workspace-title">{screen.title}</h1>
            <p>{screen.summary}</p>
          </div>
          <Link className={styles.primaryAction} href={config.primaryAction.href}>{config.primaryAction.label}</Link>
        </header>
        <div className={styles.context} aria-label="Contexto atual"><span>Organizacao</span><strong>{snapshot.currentOrganization}</strong><small>Dados e acoes limitados ao contexto atual.</small></div>
        <div className={styles.actionStrip} aria-label={`Acoes de ${screen.area}`}>
          {actions.map((action) => <Link className={styles.actionLink} href={action.href} key={action.href}><strong>{action.label}</strong><span>{action.note}</span></Link>)}
        </div>
        <div className={styles.adminLayout}>
          <section className={styles.adminMain} aria-labelledby="members-title">
            <section aria-labelledby="org-title">
              <div className={styles.sectionHeading}><h2 id="org-title">Configuracao da organizacao</h2><span>{organization.domain}</span></div>
              <form className={styles.orgForm} onSubmit={(event) => { event.preventDefault(); }}>
                <label>Nome<input value={organization.name} onChange={(event) => setOrganization((current) => ({ ...current, name: event.target.value }))} /></label>
                <label>Timezone<input value={organization.timezone} onChange={(event) => setOrganization((current) => ({ ...current, timezone: event.target.value }))} /></label>
                <label>Dominio<input value={organization.domain} onChange={(event) => setOrganization((current) => ({ ...current, domain: event.target.value }))} /></label>
                <label>Cor da marca<input type="color" value={organization.brandColor} onChange={(event) => setOrganization((current) => ({ ...current, brandColor: event.target.value }))} /></label>
                <Button type="submit">Salvar organizacao</Button>
              </form>
            </section>
            <div className={styles.sectionHeading}><h2 id="members-title">Membros, convites e papeis</h2><span>{members.filter((member) => member.status === "active").length} ativos</span></div>
            <form className={styles.memberForm} onSubmit={(event) => { event.preventDefault(); addInvite(); }}>
              <label>
                Email
                <input value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} placeholder="nome@empresa.com" />
              </label>
              <label>
                Papel
                <select value={inviteRole} onChange={(event) => setInviteRole(event.target.value as AdminMember["role"])}>
                  <option value="member">Member</option>
                  <option value="manager">Manager</option>
                  <option value="admin">Admin</option>
                  <option value="owner">Owner</option>
                </select>
              </label>
              <Button type="submit">Enviar convite</Button>
            </form>
            <ul className={styles.memberList} aria-label="Lista de membros">
              {members.map((member) => {
                const protectedOwner = member.role === "owner" && ownerCount === 1;
                return (
                  <li key={member.id} className={styles.memberRow}>
                    <div>
                      <strong>{member.name}</strong>
                      <span>{member.email}</span>
                    </div>
                    <div className={styles.memberActions}>
                      <select
                        aria-label={`Papel de ${member.name}`}
                        disabled={member.status !== "active"}
                        value={member.role}
                        onChange={(event) => updateMember(member.id, event.target.value as AdminMember["role"])}
                      >
                        <option value="member">Member</option>
                        <option value="manager">Manager</option>
                        <option value="admin">Admin</option>
                        <option value="owner">Owner</option>
                      </select>
                      <Button
                        disabled={protectedOwner}
                        onClick={() => updateMember(member.id, undefined, member.status === "active" ? "inactive" : "active")}
                        type="button"
                      >
                        {member.status === "active" ? "Excluir" : "Reativar"}
                      </Button>
                    </div>
                    <small>{member.status === "active" ? (protectedOwner ? "Ultimo owner protegido" : "Editar papel ou excluir acesso") : "Acesso inativo"}</small>
                  </li>
                );
              })}
            </ul>
          </section>
          <aside className={styles.adminSide}>
            <section aria-labelledby="invite-title">
              <div className={styles.sectionHeading}><h2 id="invite-title">Convites</h2><span>{invites.length}</span></div>
              <ul className={styles.sideList}>
                {invites.map((invite) => <li key={invite.id}><strong>{invite.email}</strong><span>{invite.role} · expira em {invite.expiresInHours}h</span><small>{invite.status}</small></li>)}
              </ul>
            </section>
            <section aria-labelledby="integration-title">
              <div className={styles.sectionHeading}><h2 id="integration-title">Integracoes</h2><span>{integrations.length}</span></div>
              <form className={styles.integrationForm} onSubmit={(event) => { event.preventDefault(); addIntegration(); }}>
                <label>Nome<input value={integrationName} onChange={(event) => setIntegrationName(event.target.value)} placeholder="Webhook fiscal" /></label>
                <label>Tipo<select value={integrationKind} onChange={(event) => setIntegrationKind(event.target.value as AdminIntegration["kind"])}><option value="webhook">Webhook</option><option value="sso">SSO</option><option value="crm">CRM</option></select></label>
                <label>Secret<input value={integrationSecret} onChange={(event) => setIntegrationSecret(event.target.value)} placeholder="chave secreta" /></label>
                <Button type="submit">Adicionar</Button>
              </form>
              <ul className={styles.sideList}>
                {integrations.map((integration) => <li key={integration.id}><strong>{integration.name}</strong><span>{integration.kind} · {integration.status}</span><small>Secret {integration.secretPreview}</small></li>)}
              </ul>
            </section>
            <section aria-labelledby="team-title">
              <div className={styles.sectionHeading}><h2 id="team-title">Times de executores</h2><span>{teams.length}</span></div>
              <form className={styles.teamForm} onSubmit={(event) => { event.preventDefault(); addTeam(); }}>
                <label>
                  Nome do time
                  <input value={teamName} onChange={(event) => setTeamName(event.target.value)} placeholder="Time SDR" />
                </label>
                <label>
                  Tipo de executor
                  <select value={teamExecutorKind} onChange={(event) => setTeamExecutorKind(event.target.value as AdminTeam["executorKind"])}>
                    <option value="team">Time</option>
                    <option value="agent">Agente</option>
                  </select>
                </label>
                <label>
                  Executor ID
                  <input value={teamExecutorId} onChange={(event) => setTeamExecutorId(event.target.value)} placeholder={teamExecutorKind === "team" ? "team-uuid" : "agent-uuid"} />
                </label>
                <Button type="submit">Salvar time</Button>
              </form>
              <ul className={styles.sideList}>
                {teams.map((team) => <li key={team.id}><strong>{team.name}</strong><span>{team.executorKind} · {team.executorId}</span></li>)}
              </ul>
            </section>
            <section aria-labelledby="privacy-title">
              <div className={styles.sectionHeading}><h2 id="privacy-title">Privacidade e auditoria</h2><span>{privacyRequests.length}</span></div>
              <ul className={styles.sideList}>
                {privacyRequests.map((request) => <li key={request.id}><strong>{request.kind}</strong><span>{request.subject}</span><small>{request.status}</small></li>)}
              </ul>
            </section>
          </aside>
        </div>
        <div className={styles.workspace}>
          <section aria-labelledby="domain-feed-title">
            <div className={styles.sectionHeading}><h2 id="domain-feed-title">{config.feedTitle}</h2><span>{items.length} itens</span></div>
            {items.length ? <ol className={styles.feed}>{items.map((item) => <li key={`${item.title}-${item.meta}`}><div><strong>{item.title}</strong><p>{item.description}</p></div>{utilityMeta(item.meta) ? <small>{utilityMeta(item.meta)}</small> : null}</li>)}</ol> : <p className={styles.empty}>{config.emptyCopy}</p>}
          </section>
          <aside aria-labelledby="related-destinations-title">
            <div className={styles.sectionHeading}><h2 id="related-destinations-title">Nesta area</h2></div>
            <nav className={styles.related} aria-label={`Destinos de ${screen.area}`}>{related.map((item) => <Link href={`/${item.slug.join("/")}`} key={item.code}><strong>{item.title}</strong><span>{item.summary}</span></Link>)}</nav>
          </aside>
        </div>
      </section>
    );
  }

  return (
    <section className={styles.page} aria-labelledby="domain-workspace-title">
      <header className={styles.heading}>
        <div><span>{config.eyebrow}</span><h1 id="domain-workspace-title">{screen.title}</h1><p>{screen.summary}</p></div>
        <Link className={styles.primaryAction} href={config.primaryAction.href}>{config.primaryAction.label}</Link>
      </header>
      <div className={styles.context} aria-label="Contexto atual"><span>Organizacao</span><strong>{snapshot.currentOrganization}</strong><small>Dados e acoes limitados ao contexto atual.</small></div>
      <div className={styles.actionStrip} aria-label={`Acoes de ${screen.area}`}>
        {actions.map((action) => <Link className={styles.actionLink} href={action.href} key={action.href}><strong>{action.label}</strong><span>{action.note}</span></Link>)}
      </div>
      <div className={styles.workspace}>
        <section aria-labelledby="domain-feed-title">
          <div className={styles.sectionHeading}><h2 id="domain-feed-title">{config.feedTitle}</h2><span>{items.length} itens</span></div>
          {items.length ? <ol className={styles.feed}>{items.map((item) => <li key={`${item.title}-${item.meta}`}><div><strong>{item.title}</strong><p>{item.description}</p></div>{utilityMeta(item.meta) ? <small>{utilityMeta(item.meta)}</small> : null}</li>)}</ol> : <p className={styles.empty}>{config.emptyCopy}</p>}
        </section>
        <aside aria-labelledby="related-destinations-title">
          <div className={styles.sectionHeading}><h2 id="related-destinations-title">Nesta area</h2></div>
          <nav className={styles.related} aria-label={`Destinos de ${screen.area}`}>{related.map((item) => <Link href={`/${item.slug.join("/")}`} key={item.code}><strong>{item.title}</strong><span>{item.summary}</span></Link>)}</nav>
        </aside>
      </div>
    </section>
  );
}
