"use client";

import Link from "next/link";
import { ReactNode, useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";

const navLinks = [
  { href: "/guide", label: "Guide" },
  { href: "/trading", label: "Trading" },
  { href: "/analysis", label: "Analysis" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/config", label: "Config" }
];

export function AppShell({ children, active }: { children: ReactNode; active?: string }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const title =
    active === "/guide"
      ? "Intraday Guide"
      : active === "/analysis"
        ? "Analytics Dashboard"
        : "Trade Dashboard";
  const router = useRouter();

  async function handleSignOut() {
    const res = await fetch("/api/auth/logout", { method: "POST" });
    if (res.ok) {
      router.push("/login");
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-4 px-3 py-4 sm:gap-6 sm:px-6 sm:py-6">
      <header className="rounded-2xl border border-white/5 bg-surface/60 px-3 py-3 shadow-lg sm:px-5 sm:py-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-accent sm:text-xs">Future Trading</p>
            <p className="text-base font-semibold text-white sm:text-lg">{title}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="rounded-full border border-white/10 px-3 py-2 text-xs text-slate-200 md:hidden"
              onClick={() => setMobileNavOpen((v) => !v)}
              aria-expanded={mobileNavOpen}
              aria-controls="mobile-nav"
            >
              Menu
            </button>
            <button
              type="button"
              onClick={handleSignOut}
              className="rounded-full border border-white/10 px-3 py-2 text-xs text-slate-200 transition hover:border-accent hover:bg-accent/10 hover:text-white sm:text-sm"
            >
              Sign Out
            </button>
          </div>
        </div>

        <nav className="mt-3 hidden flex-wrap items-center gap-2 md:flex">
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

        {mobileNavOpen ? (
          <nav id="mobile-nav" className="mt-3 grid gap-2 md:hidden">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileNavOpen(false)}
                className={clsx(
                  "rounded-lg border px-3 py-2 text-sm transition",
                  active === link.href
                    ? "border-accent/40 bg-accent/20 text-white"
                    : "border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/5 hover:text-white"
                )}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        ) : null}
      </header>
      {children}
    </div>
  );
}
