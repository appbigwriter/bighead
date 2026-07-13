import type { HTMLAttributes, PropsWithChildren } from "react";

export function FieldError({ children, ...props }: PropsWithChildren<HTMLAttributes<HTMLSpanElement>>) {
  return <span role="alert" {...props}>{children}</span>;
}
