"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchConfig, type SymbolConfig } from "@/lib/config";

const fallbackSymbols: SymbolConfig[] = [
  { symbol: "MES", data_path: "", performance_path: "", asset_class: "equity" },
  { symbol: "MNQ", data_path: "", performance_path: "", asset_class: "equity" },
  { symbol: "M2K", data_path: "", performance_path: "", asset_class: "equity" },
  { symbol: "M6E", data_path: "", performance_path: "", asset_class: "fx" },
  { symbol: "M6B", data_path: "", performance_path: "", asset_class: "fx" },
  { symbol: "MBT", data_path: "", performance_path: "", asset_class: "crypto" },
  { symbol: "MET", data_path: "", performance_path: "", asset_class: "crypto" }
];
export function SymbolSelect({
  value,
  onChange
}: {
  value: string;
  onChange: (s: string) => void;
}) {
  const [symbols, setSymbols] = useState<SymbolConfig[]>(fallbackSymbols);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    fetchConfig()
      .then((cfg) => {
        if (mounted && cfg.symbols?.length) setSymbols(cfg.symbols);
      })
      .catch(() => {
        /* fallback already set */
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const active = useMemo(() => symbols.find((s) => s.symbol === value), [symbols, value]);

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Symbol</span>
        <select
          className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-accent disabled:opacity-60"
          value={value}
          disabled={loading}
          onChange={(e) => onChange(e.target.value)}
        >
          {symbols.map((s) => (
            <option key={s.symbol} value={s.symbol}>
              {s.symbol} {s.asset_class ? `(${s.asset_class})` : ""}
            </option>
          ))}
        </select>
      </div>
      {active ? (
        <div className="text-xs text-slate-400">
          <div>Asset: {active.asset_class || "n/a"}</div>
          {active.data_path ? <div>Data: {active.data_path}</div> : null}
        </div>
      ) : null}
    </div>
  );
}
