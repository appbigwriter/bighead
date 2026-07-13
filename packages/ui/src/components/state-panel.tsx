import type { HTMLAttributes, PropsWithChildren, ReactNode } from "react";

export type StatePanelKind = "loading" | "empty" | "error" | "permission" | "offline" | "success";
type StatePanelProps = PropsWithChildren<HTMLAttributes<HTMLDivElement>> & { kind: StatePanelKind; title: string; action?: ReactNode };

export function StatePanel({ kind, title, action, children, className, ...props }: StatePanelProps) {
  const semantics = kind === "error" ? { role: "alert" } : kind === "loading" ? { "aria-busy": true } : { role: "status" };
  return <div className={`bh-state-panel ${kind === "error" ? "bh-state-panel-risk" : ""} ${className ?? ""}`} data-state={kind} {...semantics} {...props}>
    <strong>{title}</strong><div>{children}</div>{action}
  </div>;
}
