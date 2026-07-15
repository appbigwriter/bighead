import { useId, type DialogHTMLAttributes, type PropsWithChildren, type ReactNode } from "react";

type DialogProps = PropsWithChildren<DialogHTMLAttributes<HTMLDialogElement>> & { title: string; actions?: ReactNode };

export function Dialog({ title, actions, children, className, ...props }: DialogProps) {
  const titleId = useId();
  return <dialog aria-labelledby={titleId} className={`bh-dialog ${className ?? ""}`} {...props}>
    <h2 className="bh-dialog-title" id={titleId}>{title}</h2><div className="bh-dialog-content">{children}</div>{actions ? <div aria-label="Acoes do dialogo" className="bh-dialog-actions">{actions}</div> : null}
  </dialog>;
}
