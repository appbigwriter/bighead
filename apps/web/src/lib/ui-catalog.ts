export const uiCatalog = [
  { name: "Button", variants: ["primary", "secondary", "disabled", "pending"], accessibility: "button nativo; foco visivel; nome acessivel obrigatorio" },
  { name: "Dialog", variants: ["confirmation", "destructive", "form"], accessibility: "dialog nativo; titulo por aria-labelledby; acoes nomeadas" },
  { name: "FieldError", variants: ["validation", "conflict", "sync"], accessibility: "alert inline associado ao campo por aria-describedby" },
  { name: "StatePanel", variants: ["loading", "empty", "error", "permission", "offline", "success"], accessibility: "alert para erro; aria-busy para loading; status nos demais estados" }
] as const;

export function catalogCoversUniversalPrimitives() {
  return ["Button", "Dialog", "StatePanel"].every((name) => uiCatalog.some((entry) => entry.name === name && entry.variants.length >= 3));
}
