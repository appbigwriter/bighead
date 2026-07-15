import { randomUUID } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";

const apiURL = process.env.BIGHEAD_REAL_API_URL ?? "http://127.0.0.1:8010";
const atlasOrganization = "a7100000-0000-0000-0000-000000000001";
const beaconOrganization = "b7200000-0000-0000-0000-000000000001";
const atlasEmail = process.env.BIGHEAD_E2E_EMAIL ?? "owner@atlas.bighead.dev";
const beaconEmail = process.env.BIGHEAD_E2E_BEACON_EMAIL ?? "owner@beacon.bighead.dev";
const e2ePassword = process.env.BIGHEAD_E2E_PASSWORD ?? "BigHeadLocalOnly!2026";

type Session = { accessToken: string };
type LoginResponse = {
  session: Session;
  user: { id: string };
  memberships: Array<{ organizationId: string }>;
};

async function login(request: APIRequestContext, email = atlasEmail) {
  const response = await request.post(`${apiURL}/v1/auth/login`, {
    data: { email, passwordOrMagicLink: e2ePassword }
  });
  expect(response.status(), await response.text()).toBe(200);
  expect(response.headers()["x-request-id"]).toBeTruthy();
  const body = (await response.json()) as LoginResponse;
  expect(body.session.accessToken).toBeTruthy();
  return body;
}

function headers(token: string, organizationId = atlasOrganization) {
  return {
    authorization: `Bearer ${token}`,
    "x-organization-id": organizationId,
    "x-request-id": `e2e-${randomUUID()}`
  };
}

async function expectOk(response: Awaited<ReturnType<APIRequestContext["get"]>>) {
  expect(response.status(), await response.text()).toBeGreaterThanOrEqual(200);
  expect(response.status(), await response.text()).toBeLessThan(300);
  expect(response.headers()["x-request-id"]).toBeTruthy();
  return response.json();
}

async function signInBrowser(page: Page, email = atlasEmail) {
  await page.goto("/login");
  await page.getByLabel("E-mail", { exact: true }).fill(email);
  await page.locator("#password").fill(e2ePassword);
  const submitted = page.waitForResponse((response) => response.url().endsWith("/login") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  const response = await submitted;
  expect(response.status()).toBe(303);
  const authCookies = (await page.context().cookies()).filter((cookie) => cookie.name.startsWith("sb-"));
  expect(authCookies.map((cookie) => cookie.name), "Supabase auth cookies must persist after login").not.toHaveLength(0);
  await page.goto("/operacao/home");
  await expect(page).toHaveURL(/\/operacao\/home$/);
}

async function createFreshOnboardingUser() {
  const supabase = createSupabaseClient(
    process.env.BIGHEAD_REAL_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
    { auth: { autoRefreshToken: false, persistSession: false } }
  );
  const email = `onboarding-${randomUUID()}@e2e.bighead.dev`;
  const { data, error } = await supabase.auth.admin.createUser({
    email,
    password: e2ePassword,
    email_confirm: true
  });
  expect(error?.message).toBeUndefined();
  expect(data.user?.id).toBeTruthy();
  return email;
}

async function expectRealScreen(page: Page, path: string) {
  await page.goto(path);
  await expect(page.locator("main").getByRole("heading").first()).toBeVisible();
  await expect(page.locator("#shell-organization option:checked")).toHaveText("Atlas Local");
  const serviceWorkers = await page.evaluate(async () =>
    "serviceWorker" in navigator ? (await navigator.serviceWorker.getRegistrations()).length : 0
  );
  expect(serviceWorkers, "real suite must not install MSW/service workers").toBe(0);

  const scan = await new AxeBuilder({ page }).analyze();
  expect(
    scan.violations.filter((violation) =>
      violation.impact === "critical" || violation.impact === "serious"
    )
  ).toHaveLength(0);
}

async function createApproval(
  request: APIRequestContext,
  session: LoginResponse,
  taskId: string
) {
  const response = await request.post(
    `${process.env.BIGHEAD_REAL_SUPABASE_URL!}/rest/v1/approval_requests`,
    {
      headers: {
        apikey: process.env.SUPABASE_PUBLISHABLE_KEY!,
        authorization: `Bearer ${session.session.accessToken}`,
        prefer: "return=representation"
      },
      data: {
        organization_id: atlasOrganization,
        task_id: taskId,
        requested_by: session.user.id,
        risk_level: "high"
      }
    }
  );
  expect(response.status(), await response.text()).toBe(201);
  const approvals = (await response.json()) as Array<{ id: string }>;
  expect(approvals).toHaveLength(1);
  return approvals[0];
}

async function installRealtimeProbe(page: Page) {
  await page.addInitScript(() => {
    Object.assign(window, { __bigheadReadyCount: 0, __bigheadEventIds: [] as string[] });
    window.addEventListener("bighead:realtime-ready", () => {
      (window as Window & { __bigheadReadyCount: number }).__bigheadReadyCount += 1;
    });
    window.addEventListener("bighead:realtime-event", ((event: CustomEvent<{ entityId: string }>) => {
      (window as Window & { __bigheadEventIds: string[] }).__bigheadEventIds.push(event.detail.entityId);
    }) as EventListener);
  });
}

async function waitForRealtime(page: Page, minimumReadyCount = 1) {
  await page.waitForFunction(
    (minimum) => (window as Window & { __bigheadReadyCount?: number }).__bigheadReadyCount! >= minimum,
    minimumReadyCount
  );
}

test.beforeEach(async ({ page }) => signInBrowser(page));

test("real 1/10: Auth autentica e resolve tenancy sem MSW", async ({ page, request }) => {
  const session = await login(request);
  const organizations = await expectOk(
    await request.get(`${apiURL}/v1/organizations`, {
      headers: headers(session.session.accessToken)
    })
  );
  expect(organizations.organizations.map((item: { id: string }) => item.id)).toContain(
    atlasOrganization
  );
  await expectRealScreen(page, "/acesso/organizacoes");
  await page.getByRole("button", { name: "Trocar tenant" }).click();
  await expect(page.getByTestId("mutation-feedback")).toContainText("Contexto da organizacao alterado");

  const onboardingEmail = await createFreshOnboardingUser();
  await page.getByRole("button", { name: "Sair", exact: true }).click();
  await expect(page).toHaveURL(/\/login\?status=signed_out$/);
  await signInBrowser(page, onboardingEmail);
  const onboardingSuffix = randomUUID().slice(0, 8);
  const organizationName = `Onboarding E2E ${onboardingSuffix}`;
  await page.goto("/acesso/onboarding");
  await expect(page.getByRole("heading", { name: "Configure sua organizacao" })).toBeVisible();
  const onboardingScan = await new AxeBuilder({ page }).analyze();
  expect(onboardingScan.violations.filter((violation) => violation.impact === "critical" || violation.impact === "serious")).toHaveLength(0);
  await page.getByLabel("Seu nome").fill("Owner E2E");
  await page.getByLabel("Organizacao", { exact: true }).fill(organizationName);
  await page.getByLabel("Slug da organizacao").fill(`onboarding-e2e-${onboardingSuffix}`);
  await page.getByLabel("Metas").fill("qualidade, velocidade");
  await page.getByRole("button", { name: "Criar organizacao e entrar" }).click();
  await expect(page).toHaveURL(/\/operacao\/home$/);
  await expect(page.locator("#shell-organization option:checked")).toHaveText(organizationName);
  const serviceWorkers = await page.evaluate(async () =>
    "serviceWorker" in navigator ? (await navigator.serviceWorker.getRegistrations()).length : 0
  );
  expect(serviceWorkers, "authenticated onboarding must remain outside the MSW boundary").toBe(0);
});

test("real 2/10: Storage assinado recebe bytes e entra em quarentena", async ({ page }) => {
  const content = Buffer.from(`BigHead E2E ${randomUUID()}\n`);
  await expectRealScreen(page, "/colaboracao/arquivos");
  await page.locator('input[type="file"]').setInputFiles({ name: `e2e-${randomUUID()}.txt`, mimeType: "text/plain", buffer: content });
  await page.getByRole("button", { name: "Enviar e confirmar" }).click();
  await expect(page.getByTestId("mutation-feedback")).toContainText("quarentena pending");
});

test("real 3/10: conversa cria mensagem, tarefa idempotente e transicao", async ({ page, request }) => {
  const session = await login(request);
  const auth = headers(session.session.accessToken);
  const roomName = `E2E room UI ${randomUUID()}`;
  const room = await expectOk(await request.post(`${apiURL}/v1/rooms`, {
    headers: auth,
    data: { name: roomName, isPrivate: true }
  }));
  await expectRealScreen(page, `/colaboracao/sala?roomId=${encodeURIComponent(room.id)}`);
  await expect(page.getByRole("heading", { name: roomName })).toBeVisible();
  await page.getByLabel("Mensagem").fill("Mensagem persistida pela interface");
  await page.getByRole("button", { name: "Enviar", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Mensagem enviada");

  const idempotencyKey = randomUUID();
  const taskPayload = {
    title: `Tarefa E2E ${randomUUID()}`,
    goal: "Tarefa persistida e repetida com a mesma chave",
    risk: "low",
    roomId: room.id,
    dependencies: []
  };
  const firstTask = await expectOk(await request.post(`${apiURL}/v1/tasks`, {
    headers: { ...auth, "Idempotency-Key": idempotencyKey }, data: taskPayload
  }));
  const replayedTask = await expectOk(await request.post(`${apiURL}/v1/tasks`, {
    headers: { ...auth, "Idempotency-Key": idempotencyKey }, data: taskPayload
  }));
  expect(replayedTask.task.id).toBe(firstTask.task.id);
  expect(replayedTask.replayed).toBe(true);

  await expectRealScreen(page, `/tarefas/detalhe?taskId=${encodeURIComponent(firstTask.task.id)}`);
  await expect(page.getByRole("heading", { name: taskPayload.title })).toBeVisible();
  await page.getByLabel("Motivo").fill("Transicao confirmada pela interface");
  await page.getByRole("button", { name: "Confirmar alteração" }).click();
  await expect(page.getByRole("status")).toContainText("movida para triaged");
});

test("real 4/10: governanca consulta aprovacoes e politica do tenant", async ({
  page,
  request
}) => {
  const session = await login(request);
  const auth = headers(session.session.accessToken);
  const task = await expectOk(await request.post(`${apiURL}/v1/tasks`, {
    headers: { ...auth, "Idempotency-Key": randomUUID() },
    data: { title: `Governanca E2E ${randomUUID()}`, goal: "Validar segregacao real", risk: "high", dependencies: [] }
  }));
  const approval = await createApproval(request, session, task.task.id);
  const approvalPage = await expectOk(await request.get(`${apiURL}/v1/approvals`, { headers: auth }));
  expect(approvalPage.items.map((item: { id: string }) => item.id)).toContain(approval.id);
  await expectOk(await request.get(`${apiURL}/v1/policies/approvals`, { headers: auth }));
  await expectRealScreen(page, `/governanca/aprovacao-detalhe?approvalId=${encodeURIComponent(approval.id)}`);
  await expect(page.getByText("Decisão bloqueada", { exact: true })).toBeVisible();
  await expect(page.getByText(/Outra pessoa deve decidir/)).toBeVisible();
});

test("real 5/10: automacao consulta agentes, skills e modelos reais", async ({
  page,
  request
}) => {
  const session = await login(request);
  const auth = headers(session.session.accessToken);
  await expectOk(await request.get(`${apiURL}/v1/agents`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/skills`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/models`, { headers: auth }));
  await expectRealScreen(page, "/automacao/agentes");
});

test("real 6/10: conhecimento e memoria respeitam fronteira autenticada", async ({
  page,
  request
}) => {
  const session = await login(request);
  const auth = headers(session.session.accessToken);
  await expectOk(await request.get(`${apiURL}/v1/knowledge/documents`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/memory/items`, { headers: auth }));
  await expectRealScreen(page, "/conhecimento/biblioteca");
});

test("real 7/10: CRM, campanhas e conteudo usam persistencia real", async ({
  page,
  request
}) => {
  const session = await login(request);
  const auth = headers(session.session.accessToken);
  await expectOk(await request.get(`${apiURL}/v1/crm/leads`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/content/campaigns`, { headers: auth }));
  await expectRealScreen(page, "/comercial/conteudo");
  await page.getByLabel("Briefing").fill(`Conteudo criado pela UI ${randomUUID()}`);
  await page.getByRole("button", { name: "Criar ativo" }).click();
  await expect(page.getByTestId("mutation-feedback")).toContainText("Conteudo criado");
});

test("real 8/10: analytics, experimentos, integracoes e auditoria respondem", async ({
  page,
  request
}) => {
  const session = await login(request);
  const auth = headers(session.session.accessToken);
  const experimentPage = await expectOk(await request.get(`${apiURL}/v1/experiments`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/analytics/summary`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/integrations`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/audit/events`, { headers: auth }));
  await page.goto("/aprendizado/experimento-detalhe");
  const configure = page.getByRole("button", { name: "Configurar e iniciar" });
  if (await configure.isEnabled()) {
    await configure.click();
    await expect(page.getByTestId("mutation-feedback")).toContainText("Experimento configurado e iniciado");
  } else {
    await expect(page.getByText(/Experimentos em execucao mantem hipotese e variantes bloqueadas/i)).toBeVisible();
  }
  const candidate = experimentPage.items.find((item: { status: string }) => item.status === "draft") ?? experimentPage.items.find((item: { status: string }) => item.status === "running");
  expect(candidate).toBeTruthy();
  const detail = await expectOk(await request.get(`${apiURL}/v1/experiments/${candidate.id}`, { headers: auth }));
  expect(detail.experiment.status).toBe("running");
  expect(detail.immutableFields).toEqual(expect.arrayContaining(["hypothesis", "variants"]));
  const immutablePatch = await request.patch(`${apiURL}/v1/experiments/${candidate.id}`, {
    headers: auth,
    data: { hypothesis: "Nao pode mudar depois do start", expectedUpdatedAt: detail.experiment.updated_at ?? detail.experiment.updatedAt }
  });
  expect(immutablePatch.status()).toBe(409);
  await expectRealScreen(page, "/administracao/privacidade-auditoria");
});

test("real 9/10: RLS impede que Beacon veja sala Atlas", async ({ page, request }) => {
  test.setTimeout(90_000);
  const atlas = await login(request);
  const atlasRoom = await expectOk(
    await request.post(`${apiURL}/v1/rooms`, {
      headers: headers(atlas.session.accessToken),
      data: { name: `Atlas private ${randomUUID()}`, isPrivate: true }
    })
  );
  const beacon = await login(request, beaconEmail);
  const beaconRooms = await expectOk(
    await request.get(`${apiURL}/v1/rooms`, {
      headers: headers(beacon.session.accessToken, beaconOrganization)
    })
  );
  expect(beaconRooms.rooms.map((item: { id: string }) => item.id)).not.toContain(atlasRoom.id);
  const direct = await request.get(`${apiURL}/v1/rooms/${atlasRoom.id}/messages`, {
    headers: headers(beacon.session.accessToken, beaconOrganization)
  });
  expect(direct.status()).toBe(404);

  await installRealtimeProbe(page);
  await page.goto("/tarefas/inbox");
  await waitForRealtime(page);
  const beaconTaskTitle = `Beacon realtime ${randomUUID()}`;
  await expectOk(await request.post(`${apiURL}/v1/tasks`, {
    headers: { ...headers(beacon.session.accessToken, beaconOrganization), "Idempotency-Key": randomUUID() },
    data: { title: beaconTaskTitle, goal: "Nao pode invalidar nem aparecer em Atlas", risk: "low", dependencies: [] }
  }));
  await page.waitForTimeout(1_000);
  await expect(page.getByText(beaconTaskTitle, { exact: true })).toHaveCount(0);

  const atlasTaskTitle = `Atlas realtime ${randomUUID()}`;
  await expectOk(await request.post(`${apiURL}/v1/tasks`, {
    headers: { ...headers(atlas.session.accessToken), "Idempotency-Key": randomUUID() },
    data: { title: atlasTaskTitle, goal: "Deve reconciliar por Realtime SSE", risk: "low", dependencies: [] }
  }));
  await expect(page.getByText(atlasTaskTitle, { exact: true }).first()).toBeVisible({ timeout: 15_000 });
  await expectRealScreen(page, "/administracao/membros");
});

test("real 10/10: reconnect Realtime reconcilia mensagem sem duplicar e preserva tenant", async ({ page, request }) => {
  test.setTimeout(90_000);
  const atlas = await login(request);
  const beacon = await login(request, beaconEmail);
  const room = await expectOk(await request.post(`${apiURL}/v1/rooms`, {
    headers: headers(atlas.session.accessToken),
    data: { name: `Realtime reconnect ${randomUUID()}`, isPrivate: true }
  }));

  await installRealtimeProbe(page);
  await page.goto(`/colaboracao/sala?roomId=${encodeURIComponent(room.id)}`);
  await waitForRealtime(page);
  await expect(page.getByRole("heading", { name: /Realtime reconnect/ })).toBeVisible();

  const beaconRealtime = createSupabaseClient(
    process.env.BIGHEAD_REAL_SUPABASE_URL!,
    process.env.SUPABASE_PUBLISHABLE_KEY!
  );
  const beaconAuth = await beaconRealtime.auth.signInWithPassword({ email: beaconEmail, password: e2ePassword });
  expect(beaconAuth.error).toBeNull();
  const beaconEventIds: string[] = [];
  const beaconChannel = beaconRealtime.channel(`beacon-isolation-${randomUUID()}`).on(
    "postgres_changes",
    { event: "INSERT", schema: "public", table: "messages", filter: `organization_id=eq.${beaconOrganization}` },
    (payload) => { if (typeof payload.new.id === "string") beaconEventIds.push(payload.new.id); }
  );
  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error("Beacon Realtime subscription timed out")), 10_000);
    beaconChannel.subscribe((status) => {
      if (status === "SUBSCRIBED") { clearTimeout(timeout); resolve(); }
      if (status === "CHANNEL_ERROR" || status === "TIMED_OUT") { clearTimeout(timeout); reject(new Error(`Beacon Realtime ${status}`)); }
    });
  });

  const clientId = `reconnect-${randomUUID()}`;
  const body = `Mensagem unica ${randomUUID()}`;
  await page.evaluate(() => window.dispatchEvent(new Event("offline")));
  const first = await expectOk(await request.post(`${apiURL}/v1/rooms/${room.id}/messages`, {
    headers: headers(atlas.session.accessToken),
    data: { body, clientId }
  }));
  await page.waitForTimeout(500);
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await waitForRealtime(page, 2);
  await expect(page.getByText(body, { exact: true })).toHaveCount(1, { timeout: 15_000 });

  const replay = await expectOk(await request.post(`${apiURL}/v1/rooms/${room.id}/messages`, {
    headers: headers(atlas.session.accessToken),
    data: { body, clientId }
  }));
  expect(replay.id).toBe(first.id);

  const reconciled = await expectOk(await request.get(`${apiURL}/v1/rooms/${room.id}/messages`, {
    headers: headers(atlas.session.accessToken)
  }));
  expect(reconciled.messages.filter((message: { id: string; metadata?: { client_id?: string } }) =>
    message.id === first.id || message.metadata?.client_id === clientId
  )).toHaveLength(1);
  await expect(page.getByText(body, { exact: true })).toHaveCount(1);

  const crossTenant = await request.get(`${apiURL}/v1/rooms/${room.id}/messages`, {
    headers: headers(beacon.session.accessToken, beaconOrganization)
  });
  expect(crossTenant.status()).toBe(404);
  expect(beaconEventIds).not.toContain(first.id);
  const beaconRoom = await expectOk(await request.post(`${apiURL}/v1/rooms`, {
    headers: headers(beacon.session.accessToken, beaconOrganization),
    data: { name: `Beacon realtime control ${randomUUID()}`, isPrivate: false }
  }));
  const beaconControl = await expectOk(await request.post(`${apiURL}/v1/rooms/${beaconRoom.id}/messages`, {
    headers: headers(beacon.session.accessToken, beaconOrganization),
    data: { body: `Beacon liveness ${randomUUID()}`, clientId: `beacon-control-${randomUUID()}` }
  }));
  await expect.poll(() => beaconEventIds, { timeout: 10_000 }).toContain(beaconControl.id);
  expect(beaconEventIds).not.toContain(first.id);
  await beaconRealtime.removeChannel(beaconChannel);
  await beaconRealtime.auth.signOut();
});
