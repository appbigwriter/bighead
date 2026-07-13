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
      ? "bg-slate-950 text-white hover:bg-slate-800"
      : "bg-white text-slate-950 ring-1 ring-slate-200 hover:bg-slate-50";

  return (
    <button
      className={`inline-flex items-center justify-center rounded-full px-4 py-2 text-sm font-medium transition ${toneClass} ${className ?? ""}`}
      {...props}
    >
      {children}
    </button>
  );
}
