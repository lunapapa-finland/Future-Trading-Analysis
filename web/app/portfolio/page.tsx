"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { getPortfolio, postPortfolioAdjust } from "@/lib/api";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

type EquityPoint = {
  timestamp?: string;
  date?: string;
  equity: number;
  pnl?: number;
  reason?: string;
  source?: string;
  event_id?: string;
};
type PortfolioPayload = {
  latest: EquityPoint | null;
  series: EquityPoint[];
  risk_free_rate?: number;
  portfolio?: { initial_net_liq: number; start_date: string };
  metrics?: { latest_equity: number | null; max_drawdown: number | null; cagr: number | null; sharpe: number | null };
};

function localDateYmd(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export default function PortfolioPage() {
  const [data, setData] = useState<PortfolioPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState<"deposit" | "withdraw">("deposit");
  const [txDate, setTxDate] = useState(() => localDateYmd(new Date()));
  const [logSourceFilter, setLogSourceFilter] = useState<"all" | "cashflow" | "trade_sum">("all");

  useEffect(() => {
    getPortfolio()
      .then((d) => setData(d))
      .catch((err) => setError(err.message || "Failed to load portfolio"))
      .finally(() => setLoading(false));
  }, []);

  const submitAdjustment = async () => {
    setError(null);
    try {
      const parsedAmount = Number(amount);
      if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
        throw new Error("Amount must be a positive number");
      }
      await postPortfolioAdjust({ reason, amount: parsedAmount, date: txDate });
      // Reload portfolio
      const p = await getPortfolio();
      setData(p);
      setAmount("");
    } catch (err) {
      setError((err as Error).message || "Failed to adjust");
    }
  };

  const latest = data?.latest;
  const series = data?.series || [];

  return (
    <AppShell active="/portfolio">
      <div className="space-y-4">
        <div className="flex flex-col gap-1">
          <p className="text-sm uppercase tracking-[0.2em] text-accent">Portfolio</p>
          <h1 className="text-2xl font-semibold text-white">Net Liquidation</h1>
          <p className="text-slate-300">Latest equity and historical series from backend persistence.</p>
        </div>

        {loading && <p className="text-slate-300">Loading…</p>}
        {error && <p className="text-red-400">{error}</p>}
        {data?.risk_free_rate ? (
          <p className="text-xs text-slate-400">
            Config: initial net liq {data.portfolio?.initial_net_liq?.toLocaleString(undefined, { minimumFractionDigits: 2 })} | start{" "}
            {data.portfolio?.start_date || ""} | risk-free {(data.risk_free_rate * 100).toFixed(2)}%
          </p>
        ) : null}
        {data?.metrics ? (
          <Card title="Metrics" className="bg-surface/70">
            <div className="grid grid-cols-1 gap-4 text-white sm:grid-cols-2">
              <Metric label="Latest Equity" value={data.metrics.latest_equity} format="currency" />
              <Metric label="Max Drawdown" value={data.metrics.max_drawdown} format="percent" />
              <Metric label="CAGR" value={data.metrics.cagr} format="percent" />
              <Metric label="Sharpe" value={data.metrics.sharpe} format="number" />
            </div>
          </Card>
        ) : null}

        <Card title="Deposit / Withdraw" className="bg-surface/70">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="flex flex-col">
              <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Type</span>
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value as "deposit" | "withdraw")}
                className="rounded-lg border border-white/10 bg-background/60 px-3 py-2 text-sm text-white"
              >
                <option value="deposit">Deposit</option>
                <option value="withdraw">Withdraw</option>
              </select>
            </div>
            <div className="flex flex-col">
              <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Amount (USD)</span>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="rounded-lg border border-white/10 bg-background/60 px-3 py-2 text-sm text-white"
              />
            </div>
            <div className="flex flex-col">
              <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Date</span>
              <input
                type="date"
                value={txDate}
                onChange={(e) => setTxDate(e.target.value)}
                className="rounded-lg border border-white/10 bg-background/60 px-3 py-2 text-sm text-white"
              />
            </div>
            <div className="flex items-end">
              <button
                onClick={submitAdjustment}
                className="w-full rounded-lg border border-accent bg-accent px-4 py-2 text-sm font-semibold text-black shadow hover:-translate-y-0.5 hover:shadow-accent/40"
              >
                Submit
              </button>
            </div>
          </div>
        </Card>

        {latest ? (
          <Card title="Latest" className="bg-surface/70">
            <div className="grid grid-cols-1 gap-4 text-white sm:grid-cols-2">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Timestamp</p>
                <p className="text-lg font-semibold">{new Date(latest.timestamp || latest.date || "").toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Equity (USD)</p>
                <p className="text-2xl font-semibold">{latest.equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
              </div>
            </div>
          </Card>
        ) : null}

        {series.length ? (
          <Card title="Portfolio Equity" className="bg-surface/70">
            <PortfolioChart points={series} rfRate={data?.risk_free_rate ?? 0.02} />
          </Card>
        ) : null}
        {series.length ? (
          <Card title="Cashflow Log" className="bg-surface/70">
            <div className="mb-3 flex items-center gap-2">
              <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Filter</span>
              <select
                value={logSourceFilter}
                onChange={(e) => setLogSourceFilter(e.target.value as "all" | "cashflow" | "trade_sum")}
                className="rounded-lg border border-white/10 bg-background/60 px-3 py-1.5 text-xs text-white"
              >
                <option value="all">All</option>
                <option value="cashflow">Cashflow</option>
                <option value="trade_sum">Trade Sum</option>
              </select>
            </div>
            <div className="max-h-64 overflow-auto text-sm text-slate-200">
              <table className="w-full border-collapse">
                <thead className="text-slate-400">
                  <tr>
                    <th className="py-2 text-left">Date</th>
                    <th className="py-2 text-left">Source</th>
                    <th className="py-2 text-left">Event ID</th>
                    <th className="py-2 text-left">Equity</th>
                    <th className="py-2 text-left">PnL</th>
                    <th className="py-2 text-left">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {[...series]
                    .filter((pt) => {
                      if (logSourceFilter === "all") return true;
                      const src = (pt.source || (pt.reason === "trading" ? "trade_sum" : "cashflow")).toString();
                      return src === logSourceFilter;
                    })
                    .sort((a, b) => new Date((b as any).date || (b as any).timestamp || "").getTime() - new Date((a as any).date || (a as any).timestamp || "").getTime())
                    .slice(0, 50)
                    .map((pt, idx) => (
                      <tr key={`${pt.date || pt.timestamp}-${idx}`} className="border-t border-white/5">
                        <td className="py-2">{new Date((pt as any).timestamp || (pt as any).date || "").toLocaleDateString()}</td>
                        <td className="py-2">{(pt.source || (pt.reason === "trading" ? "trade_sum" : "cashflow")).toString()}</td>
                        <td className="py-2 font-mono text-xs text-slate-400">{(pt.event_id || "—").toString()}</td>
                        <td className="py-2">{Number(pt.equity).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                        <td className="py-2">{Number(pt.pnl ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                        <td className="py-2 capitalize text-slate-300">{(pt.reason || "trading").toString()}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </Card>
        ) : null}
      </div>
    </AppShell>
  );
}

function PortfolioChart({ points, rfRate }: { points: EquityPoint[]; rfRate: number }) {
  if (!points.length) return null;

  const normalized = points
    .map((pt, idx) => {
      const raw = (pt.timestamp || pt.date || "").toString();
      const ts = new Date(raw).getTime();
      if (!Number.isFinite(ts)) return null;
      const dayKey = /^\d{4}-\d{2}-\d{2}/.test(raw) ? raw.slice(0, 10) : localDateYmd(new Date(ts));
      return {
        idx,
        ts,
        dayKey,
        equity: Number(pt.equity),
        pnl: Number(pt.pnl ?? 0),
        reason: (pt.reason || "").toLowerCase(),
      };
    })
    .filter((v): v is { idx: number; ts: number; dayKey: string; equity: number; pnl: number; reason: string } => v !== null)
    .sort((a, b) => (a.ts === b.ts ? a.idx - b.idx : a.ts - b.ts));

  const byDay = new Map<string, { ts: number; equity: number; pnl: number; cashflow: number }>();
  for (const row of normalized) {
    const existing = byDay.get(row.dayKey);
    const cash = row.reason === "deposit" || row.reason === "withdraw" ? row.pnl : 0;
    if (!existing) {
      byDay.set(row.dayKey, { ts: row.ts, equity: row.equity, pnl: row.pnl, cashflow: cash });
    } else {
      existing.ts = row.ts;
      existing.equity = row.equity; // end-of-day equity
      existing.pnl += row.pnl; // daily net sum (+ and -)
      existing.cashflow += cash; // daily net cashflow (+ and -)
    }
  }

  const daily = Array.from(byDay.values()).sort((a, b) => a.ts - b.ts);
  // Use event-level cashflows (not daily net only) so frequent in/out flows are represented more faithfully.
  const cashflowEvents = normalized
    .filter((r) => r.reason === "deposit" || r.reason === "withdraw")
    .map((r) => ({ ts: r.ts, idx: r.idx, amount: r.reason === "withdraw" ? -Math.abs(r.pnl) : Math.abs(r.pnl) }))
    .filter((r) => Math.abs(r.amount) > 1e-12)
    .sort((a, b) => (a.ts === b.ts ? a.idx - b.idx : a.ts - b.ts));

  const rfSeries = daily.map((pt) => {
    const value = cashflowEvents.reduce((acc, cf) => {
      if (cf.ts > pt.ts) return acc;
      const days = (pt.ts - cf.ts) / (1000 * 60 * 60 * 24);
      const growth = cf.amount * ((1 + rfRate) ** (days / 365));
      return acc + growth;
    }, 0);
    return { ts: pt.ts, equity: value };
  });

  const labels = daily.map((p) => new Date(p.ts).toLocaleDateString());
  const data = {
    labels,
    datasets: [
      {
        label: "Equity",
        data: daily.map((p) => p.equity),
        borderColor: "#22c55e",
        backgroundColor: "rgba(34,197,94,0.2)",
        tension: 0.1,
      },
      {
        label: `Risk-free (${(rfRate * 100).toFixed(2)}% APR)`,
        data: rfSeries.map((p) => p.equity),
        borderColor: "#64748b",
        backgroundColor: "rgba(100,116,139,0.2)",
        tension: 0.1,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: { position: "top" as const, labels: { color: "#e2e8f0" } },
      tooltip: { mode: "index" as const, intersect: false },
      title: { display: false },
    },
    scales: {
      x: {
        ticks: { color: "#e2e8f0" },
        grid: { color: "rgba(226,232,240,0.1)" },
      },
      y: {
        ticks: { color: "#e2e8f0" },
        grid: { color: "rgba(226,232,240,0.1)" },
      },
    },
  };

  return (
    <div className="space-y-2">
      <Line data={data} options={options} />
    </div>
  );
}

function Metric({ label, value, format }: { label: string; value: number | null; format: "currency" | "percent" | "number" }) {
  let display = "—";
  if (typeof value === "number") {
    if (format === "currency") {
      display = value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } else if (format === "percent") {
      display = `${(value * 100).toFixed(2)}%`;
    } else {
      display = value.toFixed(2);
    }
  }
  return (
    <div>
      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{label}</p>
      <p className="text-lg font-semibold text-white">{display}</p>
    </div>
  );
}
