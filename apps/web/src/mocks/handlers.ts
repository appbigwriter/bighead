import { http, HttpResponse } from "msw";

import { getWorkspaceSnapshot } from "@/lib/mock-workspace";

export const handlers = [
  http.post("/api/screen-rules", async ({ request }) => {
    const command = await request.json() as { operation?: unknown };
    if (typeof command.operation !== "string" || command.operation.length === 0) {
      return HttpResponse.json({ message: "Operacao invalida." }, { status: 400 });
    }
    return HttpResponse.json({ message: "Operacao aceita pela fronteira mock." });
  }),
  http.get("/api/mock/workspace", () => HttpResponse.json(getWorkspaceSnapshot())),
  http.get("/api/mock/portal/:token", ({ params }) =>
    HttpResponse.json({
      token: params.token,
      state:
        params.token === "expired"
          ? "expired"
          : params.token === "used"
            ? "used"
            : params.token === "revoked"
              ? "revoked"
              : "valid"
    })
  )
];
