import { describe, expect, it, vi } from "vitest";

import { currentTheme, persistTheme, persistVisualPreferences, storedTheme, storedVisualPreferences, THEME_BOOTSTRAP_SCRIPT, visualPreferencesBootstrapScript } from "./theme-preference";

describe("theme preference", () => {
  it("bootstraps the persisted theme before the body is rendered", () => {
    expect(storedTheme("radar-dark")).toBe("radar-dark");
    expect(storedTheme(null)).toBe("aurora-light");
    expect(THEME_BOOTSTRAP_SCRIPT).toContain("localStorage.getItem('bighead-theme')");
    expect(THEME_BOOTSTRAP_SCRIPT).toContain("e.dataset.theme");
    expect(THEME_BOOTSTRAP_SCRIPT).toContain("e.dataset.density");
    expect(THEME_BOOTSTRAP_SCRIPT).toContain("e.dataset.motion");
    expect(visualPreferencesBootstrapScript({ theme: "radar-dark", density: "compact", motion: "reduced" })).toContain('"theme":"radar-dark"');
    expect(THEME_BOOTSTRAP_SCRIPT).toContain("t=r?p.theme:(localStorage.getItem('bighead-theme')||d.theme)");
  });

  it("persists a toggle and reads it from the document without mount-time correction", () => {
    const documentElement = { dataset: { theme: "aurora-light" } as DOMStringMap };
    const setItem = vi.fn();
    persistTheme("radar-dark", documentElement, { setItem });
    expect(currentTheme(documentElement)).toBe("radar-dark");
    expect(setItem).toHaveBeenCalledWith("bighead-theme", "radar-dark");
  });

  it("persists every visual preference in one pre-paint payload", () => {
    const documentElement = { dataset: {} as DOMStringMap };
    const setItem = vi.fn();
    const preferences = { theme: "radar-dark", density: "compact", motion: "reduced" } as const;
    persistVisualPreferences(preferences, documentElement, { setItem });
    expect(storedVisualPreferences(JSON.stringify(preferences))).toEqual(preferences);
    expect(documentElement.dataset).toMatchObject(preferences);
    expect(storedVisualPreferences("invalid")).toEqual({ theme: "aurora-light", density: "comfortable", motion: "full" });
  });
});
