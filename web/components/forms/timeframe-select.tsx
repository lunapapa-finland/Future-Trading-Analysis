"use client";

import { useEffect, useState } from "react";
import { TIMEFRAME_OPTIONS } from "@/lib/timeframes";
import { Timeframe } from "@/lib/types";
import { fetchConfig } from "@/lib/config";

export function TimeframeSelect({
  value,
  onChange
}: {
  value: Timeframe;
  onChange: (tf: Timeframe) => void;
}) {
  const [options, setOptions] = useState(TIMEFRAME_OPTIONS);

  useEffect(() => {
    let mounted = true;
    fetchConfig()
      .then((cfg) => {
        if (mounted && cfg.timeframes?.length) {
          setOptions(cfg.timeframes.map((tf) => ({ label: tf, value: tf as Timeframe })));
        }
      })
      .catch(() => {
        /* fallback stays */
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Timeframe</span>
      <select
        className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-accent"
        value={value}
        onChange={(e) => onChange(e.target.value as Timeframe)}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
