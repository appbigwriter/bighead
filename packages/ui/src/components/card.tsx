import type { HTMLAttributes, PropsWithChildren } from "react";

export function Card({
  children,
  className,
  ...props
}: PropsWithChildren<HTMLAttributes<HTMLDivElement>>) {
  return (
    <div
      className={`rounded-[28px] border border-slate-200 bg-white/90 p-6 shadow-sm backdrop-blur ${className ?? ""}`}
      {...props}
    >
      {children}
    </div>
  );
}
