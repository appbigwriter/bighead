export type BigHeadTheme = "aurora-light" | "radar-dark";
export type BigHeadDensity = "comfortable" | "compact";
export type BigHeadMotion = "full" | "reduced";
export type VisualPreferences = { theme: BigHeadTheme; density: BigHeadDensity; motion: BigHeadMotion };

export const THEME_STORAGE_KEY = "bighead-theme";
export const PREFERENCES_STORAGE_KEY = "bighead-visual-preferences";
export const DEFAULT_VISUAL_PREFERENCES: VisualPreferences = { theme: "aurora-light", density: "comfortable", motion: "full" };

export function visualPreferencesBootstrapScript(serverPreferences: VisualPreferences) {
  const fallback = JSON.stringify(serverPreferences);
  return `try{var d=${fallback},r=localStorage.getItem('bighead-visual-preferences'),p=r?JSON.parse(r):d,t=r?p.theme:(localStorage.getItem('bighead-theme')||d.theme),e=document.documentElement;e.dataset.theme=t==='radar-dark'?'radar-dark':'aurora-light';e.dataset.density=p.density==='compact'?'compact':'comfortable';e.dataset.motion=p.motion==='reduced'?'reduced':'full'}catch(e){}`;
}

export const THEME_BOOTSTRAP_SCRIPT = visualPreferencesBootstrapScript(DEFAULT_VISUAL_PREFERENCES);

export function storedTheme(value: string | null): BigHeadTheme {
  return value === "radar-dark" ? "radar-dark" : "aurora-light";
}

export function currentTheme(documentElement: Pick<HTMLElement, "dataset">): BigHeadTheme {
  return documentElement.dataset.theme === "radar-dark" ? "radar-dark" : "aurora-light";
}

export function storedVisualPreferences(value: string | null): VisualPreferences {
  if (!value) return DEFAULT_VISUAL_PREFERENCES;
  try {
    const parsed = JSON.parse(value) as Partial<VisualPreferences>;
    return {
      theme: parsed.theme === "radar-dark" ? "radar-dark" : "aurora-light",
      density: parsed.density === "compact" ? "compact" : "comfortable",
      motion: parsed.motion === "reduced" ? "reduced" : "full"
    };
  } catch {
    return DEFAULT_VISUAL_PREFERENCES;
  }
}

export function currentVisualPreferences(documentElement: Pick<HTMLElement, "dataset">): VisualPreferences {
  return {
    theme: currentTheme(documentElement),
    density: documentElement.dataset.density === "compact" ? "compact" : "comfortable",
    motion: documentElement.dataset.motion === "reduced" ? "reduced" : "full"
  };
}

export function persistVisualPreferences(preferences: VisualPreferences, documentElement: Pick<HTMLElement, "dataset">, storage: Pick<Storage, "setItem">) {
  documentElement.dataset.theme = preferences.theme;
  documentElement.dataset.density = preferences.density;
  documentElement.dataset.motion = preferences.motion;
  storage.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify(preferences));
  storage.setItem(THEME_STORAGE_KEY, preferences.theme);
}

export function persistTheme(theme: BigHeadTheme, documentElement: Pick<HTMLElement, "dataset">, storage: Pick<Storage, "setItem">) {
  persistVisualPreferences({ ...currentVisualPreferences(documentElement), theme }, documentElement, storage);
}
