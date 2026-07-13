import { describe, expect, it } from "vitest";

import { allowedTaskTransitions } from "./task-transitions";

describe("allowedTaskTransitions", () => {
  it("offers only destinations accepted by the backend state machine", () => {
    expect(allowedTaskTransitions("new")).toEqual(["triaged", "canceled"]);
    expect(allowedTaskTransitions("triaged")).toEqual(["in_progress", "waiting_human", "canceled"]);
    expect(allowedTaskTransitions("ready_for_review")).toEqual(["approved", "in_progress", "canceled"]);
    expect(allowedTaskTransitions("done")).toEqual([]);
    expect(allowedTaskTransitions("unknown")).toEqual([]);
  });
});
