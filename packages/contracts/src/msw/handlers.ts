import { http, HttpResponse } from "msw";

import { fixtureTask, fixtureTenant } from "../fixtures/seed";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const handlers = [
  http.post(`${apiBase}/v1/auth/login`, () =>
    HttpResponse.json({
      userId: "b69cb1f0-a85c-4aa8-ad75-f789c5ac2500",
      memberships: [
        {
          organizationId: fixtureTenant.organizationId,
          organizationName: fixtureTenant.name,
          role: "owner"
        }
      ]
    })
  ),
  http.get(`${apiBase}/v1/tasks`, () =>
    HttpResponse.json({
      data: [fixtureTask],
      page: { nextCursor: null }
    })
  ),
  http.get(`${apiBase}/v1/rooms`, () =>
    HttpResponse.json({
      data: [{ id: "9fd72ae3-d98d-4897-bc0e-671dc8759297", name: "Operacoes", visibility: "public" }],
      page: { nextCursor: null }
    })
  ),
  http.get(`${apiBase}/v1/approvals`, () =>
    HttpResponse.json({
      data: [{ id: "885cdca5-f030-40fd-8369-8a283ee8bf27", status: "pending", requestedAt: "2026-07-12T15:30:00.000Z" }]
    })
  )
];
