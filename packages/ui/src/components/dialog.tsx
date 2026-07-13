import { useId, type DialogHTMLAttributes, type PropsWithChildren, type ReactNode } from "react";

type DialogProps = PropsWithChildren<DialogHTMLAttributes<HTMLDialogElement>> & { title: string; actions?: ReactNode };

export function Dialog({ title, actions, children, className, ...props }: DialogProps) {
  const titleId = useId();
  return <dialog aria-labelledby={titleId} className={`rounded-3xl border border-slate-200 bg-white p-6 text-slate-950 shadow-xl ${className ?? ""}`} {...props}>
    <h2 id={titleId}>{title}</h2><div>{children}</div>{actions ? <div aria-label="Acoes do dialogo">{actions}</div> : null}
  </dialog>;
}
