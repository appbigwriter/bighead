"use client";

import { useState, useTransition } from "react";
import { Button, FieldError } from "@bighead/ui";
import { saveVisualPreferences } from "@/app/actions/visual-preferences";
import { currentVisualPreferences, persistVisualPreferences, type VisualPreferences } from "@/lib/theme-preference";

export function ThemeToggle({ organizationId }: { organizationId: string }) {
  const [pending, startTransition] = useTransition();
  const [syncFailed, setSyncFailed] = useState(false);

  function update(next: (current: VisualPreferences) => VisualPreferences) {
    const preferences = next(currentVisualPreferences(document.documentElement));
    persistVisualPreferences(preferences, document.documentElement, window.localStorage);
    setSyncFailed(false);
    startTransition(() => { void saveVisualPreferences({ ...preferences, organizationId }).catch(() => setSyncFailed(true)); });
  }

  return (
    <div aria-label="Preferencias visuais" className="bh-inline" role="group">
      <Button className="bh-chip" disabled={pending} onClick={() => update((value) => ({ ...value, theme: value.theme === "aurora-light" ? "radar-dark" : "aurora-light" }))} type="button">Alternar tema</Button>
      <Button className="bh-chip" disabled={pending} onClick={() => update((value) => ({ ...value, density: value.density === "comfortable" ? "compact" : "comfortable" }))} type="button">Alternar densidade</Button>
      <Button className="bh-chip" disabled={pending} onClick={() => update((value) => ({ ...value, motion: value.motion === "full" ? "reduced" : "full" }))} type="button">Alternar movimento</Button>
      {syncFailed ? <FieldError>Preferencia aplicada neste dispositivo; sincronizacao pendente.</FieldError> : null}
    </div>
  );
}
