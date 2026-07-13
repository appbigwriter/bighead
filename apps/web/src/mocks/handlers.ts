import { http, HttpResponse } from "msw";

import { getWorkspaceSnapshot } from "@/lib/mock-workspace";

export const handlers = [
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
