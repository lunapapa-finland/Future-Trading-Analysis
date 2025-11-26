import clsx from "clsx";
import { ReactNode } from "react";

export function Card({
  title,
  children,
  className
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("rounded-2xl border border-white/5 bg-surface/70 p-4 shadow-lg", className)}>
      {title ? <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-300">{title}</h2> : null}
      {children}
    </div>
  );
}
