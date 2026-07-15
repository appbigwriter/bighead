# BigHead Interface Redesign Plan

## Product Direction

**Visual thesis:** Quiet mission control. Warm-neutral operational canvas, near-black type, crisp white surfaces, restrained teal action color, amber/red reserved for risk. Dense, cardless, scan-first.

**Content plan:** Start in role-aware operational inbox; make every real capability reachable through a clear module map, contextual navigation, global search, and command palette. Configuration and administration remain fully accessible to authorized users.

**Interaction thesis:** Selection keeps context through a persistent inspector; reversible changes feel immediate and offer undo; live runs update with restrained motion and explicit provenance.

## Current Problems

- Three visual systems compete: cream/orange legacy globals, teal workspace shell, lime home accents. `DESIGN_STANDARDS.md` describes a fourth partial contract.
- `--canvas` is referenced by shell CSS but absent from global tokens.
- About 30 routes sit inside `Mais`; IA follows backend modules instead of daily jobs.
- Most catalog routes use generic `ScreenExperience`, exposing QA/prototype language, screen codes, endpoints, contracts, simulated states, implementation checklists, and action consoles to operators.
- Core relationship, conversation -> task -> run -> approval -> artifact, is split across separate surfaces.
- Shared `Button`, `Card`, and state primitives use pill/large-radius styling that conflicts with dense product UI.
- Status, risk, SLA, AI provenance, and cost lack one consistent semantic presentation.

## Target Information Architecture

### Desktop rail

1. **Inbox**: work needing current user now; at-risk tasks, reviews, failed runs, next actions.
2. **Conversas**: rooms and threads with linked tasks.
3. **Trabalho**: task inbox, calendar/SLA, runs and failures.
4. **Revisoes**: approvals and Sentinel QA.
5. **Comercial**: leads, pipeline, campaigns and content.
6. **Automacao**: agents, workflows, skills, prompts, models and playbooks.
7. **Conhecimento**: documents, ingestion, memory and semantic search.
8. **Analises**: executive results, operations/SLA, agent performance, cost, funnel and experiments.
9. **Administracao**: organization, members, roles, policies, integrations, privacy and audit; anchored at rail bottom.

Remove `Criar tarefa` from primary navigation. Put creation in global `+` action and command palette. Replace `Mais` with searchable categorized module switcher. All resources remain reachable; permission changes visibility and enabled actions, never creates an unexplained dead end.

### Full Resource Map

- **Acesso:** login, recovery, invite, onboarding, organization selection. These are contextual flows, not workspace menu items.
- **Operacao:** inbox, search, notifications, profile/sessions, rooms, messages, room members/files, tasks, task creation/detail, run monitor, failures, SLA calendar.
- **Governanca:** approval queue/detail, quality scorecards, approval policies, external portal.
- **Automacao:** agent catalog/config, skill catalog/test, providers/models, prompt versions, workflow list/editor/versions, playbooks.
- **Conhecimento:** library, document/ingestion, operational memory, semantic search.
- **Comercial:** accounts/contacts, leads/detail, pipeline, campaigns, content studio, editorial calendar.
- **Analises:** experiments/detail, executive dashboard, operations/SLA, agent/skill performance, costs/budgets, funnel/attribution.
- **Administracao:** organization/branding, members/invites/roles, integrations/webhooks, privacy/retention/audit.

Each area gets landing index, local secondary navigation, breadcrumbs, and direct command-palette access. No resource depends only on knowing its URL.

### QA Boundary

- Move `/catalogo`, screen codes, endpoint lists, state simulators, acceptance checklists, component catalog, and action console behind development-only tooling.
- Production UI consumes same contracts silently through tests and Storybook/catalog tooling; users see domain language and real data only.
- Sentinel QA remains a product feature because it evaluates business deliverables. Rename visible copy to `Qualidade` where technical QA wording would confuse nontechnical users.

### Mobile

Bottom destinations: Inbox, Conversas, Tarefas, Revisoes. Center or top-level `+` opens creation menu. More opens categorized drawer. Detail views use full-height sheets and preserve back-stack/filter state.

## Canonical Workspace Pattern

- Compact page toolbar: title, scope/freshness, active filters, view control, primary action.
- Main work surface: list, table, timeline, canvas, or compare view.
- Right inspector: selected item state, owner, risk, SLA, agent, cost, linked context, next actions.
- URL stores selection and view state. Back restores filters, cursor, selection, and scroll.
- Tabs only for deep history: audit, cost ledger, version history, raw execution detail.
- Every surface covers loading, empty, recoverable error with `trace_id`, offline, denied, removed, partial, and success states.

## Visual System

### Tokens

- Canvas: `#F5F6F2`; dark `#111411`.
- Surface: `#FFFFFF`; dark `#191D19`.
- Elevated: `#EEF1EC`; dark `#202520`.
- Ink: `#17201B`; dark `#F2F5EF`.
- Muted: `#667169`; dark `#A3ACA5`.
- Action: `#087F75`; hover `#06685F`.
- Success/live: semantic green; AI/high-attention lime `#B9FF5A` only in small signals.
- Warning `#B68A27`; danger `#B43D3D`.
- Radius: 6/8/12px; 16px only for modal/sheet.
- Spacing: 4/8/12/16/24/32/48px. Controls: 32/36/40/44px.

Use Inter/Geist for UI and optional Outfit only for BigHead wordmark. Maximum two typefaces. Typography and dividers create hierarchy; shadows only on overlays. No decorative gradients, glass panels, nested cards, or oversized app headings.

### Motion

- Route entrance: content rises 6px and fades, 180-240ms, once.
- Inspector/sheet: right-side transition, 220ms; mobile full-height sheet.
- Row feedback: stable 3px state edge, soft background, 2px icon shift without layout movement.
- Realtime change: one brief background pulse plus timestamp/status update.
- Respect `prefers-reduced-motion` and existing `data-motion="reduced"`.

Use CSS transitions first. Add Framer Motion only when shared-layout behavior proves necessary.

## Priority Experiences

### 1. Inbox/Home

- Keep current ranked priority list as structural base; reduce heading scale and remove isolated lime dominance.
- KPI strip links to filtered records; no dashboard card mosaic.
- Dominant area: `Precisa de voce` ranked by risk, deadline, and dependency.
- Secondary rail: SLA exceptions, failed runs, cost freshness, recent decisions.
- Replace `Indisponivel` dead ends with setup, permission, or freshness action.
- Display human names/account context, not raw owner IDs.

### 2. Tasks

- Segmented Table/Kanban views, saved views, sortable columns, active-filter chips, authorized bulk actions.
- Task selection opens canonical inspector without losing inbox context.
- Inspector summary: state, SLA, owner, agent/workflow, risk, cost, source conversation, approvals, artifact preview.
- Valid transitions only. Guarded transitions open impact sheet and require reason when policy demands it.
- Reversible moves update optimistically with undo; failures restore state and preserve input.

### 3. Conversations

- Desktop three-pane layout: room list, message timeline, context inspector.
- Inline message action `Transformar em tarefa`; linked task status remains visible in thread.
- Composer uses icon toolbar for files/audio/mentions with tooltips.
- Agent output shows agent, model, sources, confidence, cost, approval state.
- Mobile progression: rooms -> thread -> details; no compressed three-column layout.

### 4. Reviews

- Reviewer split view: prioritized queue, artifact/version comparison, sticky decision rail.
- Decision rail shows impact, policy route, Sentinel score, requester, deadline, audit consequence.
- Keyboard next/previous and explicit approve/request changes/reject commands.
- Immutable decision warning only at commitment point; next item loads without returning to list.

### 5. Commercial

- Dense lead table with explained score, owner, next action, SLA, account and signals.
- Pipeline supports drag with accessible stage menu fallback.
- Stage guard sheet appears only when required fields, justification, or risk changes demand it.
- Lead detail reuses canonical inspector/timeline pattern instead of isolated cards.

## Delivery Phases

### Phase A: Foundation

- Canonicalize theme variables in `apps/web/src/app/globals.css`; fix `--canvas` mismatch.
- Update `DESIGN_STANDARDS.md` to match implemented product direction.
- Configure fonts in root layout.
- Rebuild shared Button, Card, Dialog, StatePanel semantics; retain API compatibility where practical.
- Inventory and replace hardcoded teal/lime/purple and legacy `.bh-*` dependencies.

**Done:** light/dark tokens render consistently; shared primitives pass existing tests; no screen mixes legacy and new tokens.

### Phase B: Shell and Navigation

- Icon+label rail using Lucide; tooltips on unfamiliar icon-only controls.
- Role-aware navigation and categorized module switcher.
- Real Radix command palette for search, navigation, and creation.
- Compact tenant switcher; notification/profile icon actions.
- Mobile bottom navigation and accessible drawer.

**Done:** full keyboard path, correct active route, focus restore, tenant context safe, no overflow at 360px.

### Phase C: Core Work Loop

- Build shared toolbar, data list/table, status token, inspector, impact sheet, and provenance components.
- Redesign Tasks first, then Conversations, then Reviews.
- Preserve existing API contracts, RLS behavior, idempotency, and mutation error recovery.

**Done:** conversation -> task -> run -> review -> completion works without losing context; critical actions remain audited and guarded.

### Phase D: Operational Overview and Commercial

- Refine Home/Inbox using new primitives.
- Apply workspace pattern to Leads and Pipeline.
- Add consistent freshness, source, risk, SLA, cost, and empty-state behavior.

**Done:** operator can identify highest-priority next action within one scan and drill into source records.

### Phase E: Complete Resource Coverage

- Replace every production use of generic `ScreenExperience` with domain templates: catalog/list, detail/editor, analytics, settings, calendar, canvas, compare, or timeline.
- Productize all automation, knowledge, analytics, administration, access, and commercial resources from the full resource map.
- Give each area an index and local navigation so no capability lives only in `Mais` or command search.
- Move endpoint/test/contract language and state simulation to development-only catalog.
- Track coverage with a T01-T56 migration matrix: route, user job, production component, data source, permissions, states, responsive behavior, and acceptance test.

**Done:** all 56 product capabilities have intentional, usable access paths; every production route supports a real user job; QA scaffolding is absent from production UI.

## Verification Gates

- Playwright visual snapshots at 1440, 1024, 768, and 390px in light/dark themes.
- Axe: zero serious/critical violations; WCAG 2.2 AA contrast.
- Keyboard-only journeys for shell, command palette, tasks, conversations, reviews, and guarded actions.
- 200% zoom; no horizontal overflow, overlap, clipped controls, or layout shift.
- Reduced-motion verification for both OS preference and app setting.
- State matrix tests for loading, empty, offline, denied, removed, partial, error/retry, and success.
- AI output always exposes required provenance; tenant isolation and permission behavior unchanged.
- Separate reviewer/verifier pass after each phase.

## Non-Goals

- No marketing landing page or decorative hero inside authenticated product.
- No big-bang release. All 56 capabilities are in scope, delivered area by area behind verified migration gates.
- No backend contract changes unless a required operator field is genuinely absent.
- No drag-only interaction, color-only status, ornamental animation, or new component framework.
