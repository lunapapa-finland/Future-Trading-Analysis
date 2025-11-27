"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
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

type EquityPoint = { timestamp?: string; date?: string; equity: number; pnl?: number; reason?: string };
type PortfolioPayload = { latest: EquityPoint; series: EquityPoint[]; risk_free_rate?: number };

export default function PortfolioPage() {
  const [data, setData] = useState<PortfolioPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState<"deposit" | "withdraw">("deposit");
  const [txDate, setTxDate] = useState(() => new Date().toISOString().slice(0, 10));

  useEffect(() => {
    fetch("/api/portfolio")
      .then((res) => res.json())
      .then((d) => setData(d))
      .catch((err) => setError(err.message || "Failed to load portfolio"))
      .finally(() => setLoading(false));
  }, []);

  const submitAdjustment = async () => {
    setError(null);
    try {
      const res = await fetch("/api/portfolio/adjust", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason, amount: Number(amount), date: txDate })
      });
      const resp = await res.json();
      if (!res.ok) throw new Error(resp?.error || "Failed to adjust");
      // Reload portfolio
      const p = await fetch("/api/portfolio").then((r) => r.json());
      setData(p);
      setAmount("");
    } catch (err) {
      setError((err as Error).message || "Failed to adjust");
    }
  };

  const latest = data?.latest;
  const series = data?.series || [];

  const chartPoints = series
    .map((pt) => {
      const ts = new Date((pt as any).timestamp || (pt as any).date).getTime();
      return { ts, equity: Number(pt.equity), pnl: Number(pt.pnl), reason: pt.reason || "" };
    })
    .sort((a, b) => a.ts - b.ts);

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

        <Card title="Deposit / Withdraw" className="bg-surface/70">
          <div className="flex flex-wrap items-end gap-3">
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
            <button
              onClick={submitAdjustment}
              className="rounded-lg border border-accent bg-accent px-4 py-2 text-sm font-semibold text-black shadow hover:-translate-y-0.5 hover:shadow-accent/40"
            >
              Submit
            </button>
          </div>
        </Card>

        {latest ? (
          <Card title="Latest" className="bg-surface/70">
            <div className="grid grid-cols-2 gap-4 text-white">
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
            <PortfolioChart points={chartPoints} rfRate={data?.risk_free_rate ?? 0.02} />
          </Card>
        ) : null}
      </div>
    </AppShell>
  );
}

function PortfolioChart({ points, rfRate }: { points: { ts: number; equity: number; pnl: number; reason?: string }[]; rfRate: number }) {
  if (!points.length) return null;
  const sorted = [...points].sort((a, b) => a.ts - b.ts);
  const cashflows = sorted
    .filter((p) => ["init", "deposit", "withdraw"].includes((p.reason || "").toLowerCase()))
    .map((p) => {
      const reason = (p.reason || "").toLowerCase();
      let amount = 0;
      if (reason === "init") {
        amount = p.equity; // initial capital
      } else if (reason === "deposit") {
        amount = Math.abs(p.pnl);
      } else if (reason === "withdraw") {
        amount = -Math.abs(p.pnl);
      }
      return { ts: p.ts, amount };
    })
    .sort((a, b) => a.ts - b.ts);

  const rfSeries = sorted.map((pt) => {
    const value = cashflows.reduce((acc, cf) => {
      if (cf.ts > pt.ts) return acc;
      const days = (pt.ts - cf.ts) / (1000 * 60 * 60 * 24);
      const growth = cf.amount * ((1 + rfRate) ** (days / 365));
      return acc + growth;
    }, 0);
    return { ts: pt.ts, equity: value };
  });

  const labels = sorted.map((p) => new Date(p.ts).toLocaleDateString());
  const data = {
    labels,
    datasets: [
      {
        label: "Equity",
        data: sorted.map((p) => p.equity),
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
