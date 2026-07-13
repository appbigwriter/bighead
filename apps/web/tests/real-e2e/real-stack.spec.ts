import { createHash, randomUUID } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const apiURL = process.env.BIGHEAD_REAL_API_URL ?? "http://127.0.0.1:8010";
const atlasOrganization = "a7100000-0000-0000-0000-000000000001";
const beaconOrganization = "b7200000-0000-0000-0000-000000000001";
const atlasEmail = process.env.BIGHEAD_E2E_EMAIL ?? "owner@atlas.bighead.dev";
const beaconEmail = process.env.BIGHEAD_E2E_BEACON_EMAIL ?? "owner@beacon.bighead.dev";

type Session = { accessToken: string };
type LoginResponse = { session: Session; memberships: Array<{ organizationId: string }> };

async function login(request: APIRequestContext, email = atlasEmail) {
  const response = await request.post(`${apiURL}/v1/auth/login`, {
    data: { email, passwordOrMagicLink: "BigHeadLocalOnly!2026" }
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

async function expectRealScreen(page: Page, path: string, token: string) {
  await page.goto(path);
  await expect(page.locator("h2").first()).toBeVisible();
  await expect(page.getByText("Atlas Local", { exact: true }).first()).toBeVisible();
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

test("real 1/9: Auth autentica e resolve tenancy sem MSW", async ({ page, request }) => {
  const session = await login(request);
  const organizations = await expectOk(
    await request.get(`${apiURL}/v1/organizations`, {
      headers: headers(session.session.accessToken)
    })
  );
  expect(organizations.organizations.map((item: { id: string }) => item.id)).toContain(
    atlasOrganization
  );
  await expectRealScreen(page, "/acesso/organizacoes", session.session.accessToken);
});

test("real 2/9: Storage assinado recebe bytes e entra em quarentena", async ({
  page,
  request
}) => {
  const session = await login(request);
  const content = Buffer.from(`BigHead E2E ${randomUUID()}\n`);
  const checksum = createHash("sha256").update(content).digest("hex");
  const initiated = await request.post(`${apiURL}/v1/artifacts/uploads`, {
    headers: headers(session.session.accessToken),
    data: {
      filename: `e2e-${randomUUID()}.txt`,
      mimeType: "text/plain",
      sizeBytes: content.length,
      checksumSha256: checksum
    }
  });
  expect(initiated.status(), await initiated.text()).toBe(201);
  const upload = await initiated.json();
  const stored = await request.put(upload.uploadUrl, {
    headers: upload.requiredHeaders,
    data: content
  });
  expect(stored.status(), await stored.text()).toBe(200);
  const confirmed = await request.post(
    `${apiURL}/v1/artifacts/${upload.artifactId}/confirm`,
    { headers: headers(session.session.accessToken), data: { checksumSha256: checksum } }
  );
  expect(confirmed.status(), await confirmed.text()).toBe(202);
  expect((await confirmed.json()).quarantineStatus).toBe("pending");
  await expectRealScreen(page, "/colaboracao/arquivos", session.session.accessToken);
});

test("real 3/9: conversa cria mensagem, tarefa idempotente e transicao", async ({
  page,
  request
}) => {
  const session = await login(request);
  const auth = headers(session.session.accessToken);
  const roomResponse = await request.post(`${apiURL}/v1/rooms`, {
    headers: auth,
    data: { name: `E2E room ${randomUUID()}`, isPrivate: false }
  });
  expect(roomResponse.status(), await roomResponse.text()).toBe(201);
  const room = await roomResponse.json();
  const message = await expectOk(
    await request.post(`${apiURL}/v1/rooms/${room.id}/messages`, {
      headers: auth,
      data: { body: "Mensagem real para tarefa", clientId: randomUUID() }
    })
  );
  const taskResponse = await request.post(`${apiURL}/v1/tasks`, {
    headers: { ...auth, "Idempotency-Key": randomUUID() },
    data: {
      goal: "Converter conversa real em tarefa",
      roomId: room.id,
      sourceMessageId: message.id,
      dependencies: []
    }
  });
  expect(taskResponse.status(), await taskResponse.text()).toBe(201);
  const task = (await taskResponse.json()).task;
  const transitioned = await expectOk(
    await request.post(`${apiURL}/v1/tasks/${task.id}/transition`, {
      headers: auth,
      data: { targetState: "triaged", expectedVersion: task.version, reason: "E2E" }
    })
  );
  expect(transitioned.task.status).toBe("triaged");
  await expectRealScreen(page, "/colaboracao/sala", session.session.accessToken);
});

test("real 4/9: governanca consulta aprovacoes e politica do tenant", async ({
  page,
  request
}) => {
  const session = await login(request);
  const auth = headers(session.session.accessToken);
  await expectOk(await request.get(`${apiURL}/v1/approvals`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/policies/approvals`, { headers: auth }));
  await expectRealScreen(page, "/governanca/aprovacoes", session.session.accessToken);
});

test("real 5/9: automacao consulta agentes, skills e modelos reais", async ({
  page,
  request
}) => {
  const session = await login(request);
  const auth = headers(session.session.accessToken);
  await expectOk(await request.get(`${apiURL}/v1/agents`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/skills`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/models`, { headers: auth }));
  await expectRealScreen(page, "/automacao/agentes", session.session.accessToken);
});

test("real 6/9: conhecimento e memoria respeitam fronteira autenticada", async ({
  page,
  request
}) => {
  const session = await login(request);
  const auth = headers(session.session.accessToken);
  await expectOk(await request.get(`${apiURL}/v1/knowledge/documents`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/memory/items`, { headers: auth }));
  await expectRealScreen(page, "/conhecimento/biblioteca", session.session.accessToken);
});

test("real 7/9: CRM, campanhas e conteudo usam persistencia real", async ({
  page,
  request
}) => {
  const session = await login(request);
  const auth = headers(session.session.accessToken);
  await expectOk(await request.get(`${apiURL}/v1/crm/leads`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/content/campaigns`, { headers: auth }));
  const asset = await request.post(`${apiURL}/v1/content/assets`, {
    headers: { ...auth, "Idempotency-Key": randomUUID() },
    data: { brief: "Conteudo criado pelo E2E real", channels: ["email"], variants: [] }
  });
  expect(asset.status(), await asset.text()).toBe(201);
  await expectRealScreen(page, "/comercial/conteudo", session.session.accessToken);
});

test("real 8/9: analytics, experimentos, integracoes e auditoria respondem", async ({
  page,
  request
}) => {
  const session = await login(request);
  const auth = headers(session.session.accessToken);
  await expectOk(await request.get(`${apiURL}/v1/experiments`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/analytics/summary`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/integrations`, { headers: auth }));
  await expectOk(await request.get(`${apiURL}/v1/audit/events`, { headers: auth }));
  await expectRealScreen(
    page,
    "/administracao/privacidade-auditoria",
    session.session.accessToken
  );
});

test("real 9/9: RLS impede que Beacon veja sala Atlas", async ({ page, request }) => {
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
  await expectRealScreen(page, "/administracao/membros", atlas.session.accessToken);
});
