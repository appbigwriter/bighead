import { describe, expect, it } from "vitest";

import { mutationResultFromError } from "./mutation-error";

describe("mutationResultFromError", () => {
  it("maps a backend dependency cycle to the dependencies field", () => {
    const error = Object.assign(new Error("Task dependency cycle"), { status: 409 });
    expect(mutationResultFromError(error)).toEqual({
      ok: false,
      status: 409,
      message: "Corrija as dependencias destacadas antes de salvar.",
      data: { fieldErrors: { dependencies: "Dependencia circular detectada." } }
    });
  });
});
