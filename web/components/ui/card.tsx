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
    <div className={clsx("rounded-2xl border border-white/5 bg-surface/70 p-3 shadow-lg sm:p-4", className)}>
      {title ? <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-300 sm:mb-3 sm:text-sm">{title}</h2> : null}
      {children}
    </div>
  );
}
