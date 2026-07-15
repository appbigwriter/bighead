import type { HTMLAttributes, PropsWithChildren } from "react";

export function Card({
  children,
  className,
  ...props
}: PropsWithChildren<HTMLAttributes<HTMLDivElement>>) {
  return (
    <div
      className={`bh-card ${className ?? ""}`}
      {...props}
    >
      {children}
    </div>
  );
}
