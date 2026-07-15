import type { ButtonHTMLAttributes, PropsWithChildren } from "react";

type ButtonProps = PropsWithChildren<
  ButtonHTMLAttributes<HTMLButtonElement> & {
    tone?: "primary" | "secondary";
  }
>;

export function Button({
  children,
  className,
  tone = "primary",
  ...props
}: ButtonProps) {
  const toneClass =
    tone === "primary"
      ? "bh-button-primary"
      : "bh-button-secondary";

  return (
    <button
      className={`bh-button ${toneClass} ${className ?? ""}`}
      {...props}
    >
      {children}
    </button>
  );
}
