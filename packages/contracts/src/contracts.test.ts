import { describe, expect, it } from "vitest";

import { fixtureTask } from "./fixtures/seed";
import { taskStateSchema } from "./schemas/common";

describe("contracts", () => {
  it("keeps task fixtures aligned with task state schema", () => {
    expect(taskStateSchema.parse(fixtureTask.state)).toBe("new");
  });
});
