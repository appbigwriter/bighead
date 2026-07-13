import { describe, expect, it } from "vitest";

import { screens } from "@/lib/screen-catalog";
import { getScreenPlaybook, screenPlaybooks, transitionPlaybook } from "./screen-playbooks";

describe("screen playbook contracts", () => {
  it.each(Object.keys(screenPlaybooks))("proves precondition, effect and guard for %s", (code) => {
    const definition = screens.find((item) => item.code === code)!;
    const playbook = getScreenPlaybook(definition.code)!;
    const initial = { phase: "blocked" as const, revision: 0 };

    const guarded = transitionPlaybook(playbook, initial, "apply");
    expect(guarded.state).toEqual(initial);
    expect(guarded.error).toBe(playbook.guard);
    expect(guarded.effect).toBeUndefined();

    const ready = transitionPlaybook(playbook, initial, "satisfy");
    expect(ready.state.phase).toBe("ready");

    const applied = transitionPlaybook(playbook, ready.state, "apply");
    expect(applied.state).toEqual({ phase: "applied", revision: 1 });
    expect(applied.effect).toBe(playbook.effect);
    expect(applied.error).toBeUndefined();
  });

  it("keeps every contract behaviorally distinct", () => {
    const contracts = Object.keys(screenPlaybooks).map((code) => getScreenPlaybook(code as never)!);
    expect(new Set(contracts.map(({ precondition }) => precondition)).size).toBe(contracts.length);
    expect(new Set(contracts.map(({ effect }) => effect)).size).toBe(contracts.length);
    expect(new Set(contracts.map(({ guard }) => guard)).size).toBe(contracts.length);
  });
});
