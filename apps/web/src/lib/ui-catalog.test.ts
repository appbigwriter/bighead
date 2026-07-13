import { describe, expect, it } from "vitest";
import { catalogCoversUniversalPrimitives, uiCatalog } from "./ui-catalog";

describe("internal UI catalog", () => {
  it("documents universal actions, dialogs and transverse states", () => {
    expect(catalogCoversUniversalPrimitives()).toBe(true);
    expect(uiCatalog.flatMap((entry) => entry.variants)).toEqual(expect.arrayContaining(["error", "permission", "offline", "destructive", "pending"]));
    expect(uiCatalog.every((entry) => entry.accessibility.length > 20)).toBe(true);
  });
});
