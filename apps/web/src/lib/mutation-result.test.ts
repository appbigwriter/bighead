import { describe, expect, it } from "vitest";

import { mutationFailure } from "./mutation-result";

describe("mutation error UX", () => {
  it.each([
    [401, "sessao expirou"],
    [403, "nao tem permissao"],
    [409, "registro mudou"],
    [503, "sem repetir a operacao"]
  ])("maps HTTP %i to an actionable message", (status, message) => {
    expect(mutationFailure(status).message).toContain(message);
  });

  it("preserves validation detail without exposing it for server failures", () => {
    expect(mutationFailure(422, "Campo obrigatorio").message).toBe("Campo obrigatorio");
    expect(mutationFailure(500, "stack trace").message).not.toContain("stack trace");
  });
});
