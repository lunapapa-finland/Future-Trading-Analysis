import Link from "next/link";
import { ReactNode } from "react";
import clsx from "clsx";

const navLinks = [
  { href: "/trading", label: "Trading" },
  { href: "/analysis", label: "Analysis" },
  { href: "/config", label: "Config" }
];

export function AppShell({ children, active }: { children: ReactNode; active?: string }) {
  const title = active === "/analysis" ? "Analytics Dashboard" : "Trade Dashboard";
  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-6">
      <header className="flex items-center justify-between rounded-2xl border border-white/5 bg-surface/60 px-5 py-4 shadow-lg">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-accent">Future Trading</p>
          <p className="text-lg font-semibold text-white">{title}</p>
        </div>
        <nav className="flex items-center gap-3">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={clsx(
                "rounded-full px-3 py-2 text-sm transition",
                active === link.href
                  ? "bg-accent/20 text-white"
                  : "text-slate-300 hover:bg-white/5 hover:text-white"
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </header>
      {children}
    </div>
  );
}
