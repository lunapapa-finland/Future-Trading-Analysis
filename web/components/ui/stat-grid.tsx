import { Card } from "./card";

type WinLoss = { label: string; value: number };
type ByType = { Type: string; Wins: number; Losses: number };
type StreakPoint = { TradeIndex?: number; Streak?: number };
type SizeCount = { Size: number; Count: number };
type DurationBin = { label: string; count: number };

function BarRow({ label, value, total, color }: { label: string; value: number; total: number; color: string }) {
  const pct = total > 0 ? Math.min(100, Math.max(0, (value / total) * 100)) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-slate-400">
        <span>{label}</span>
        <span className="text-slate-200">{value}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-white/10">
        <div className="h-2 rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

export function StatGrid({
  stats
}: {
  stats: {
    win_loss?: WinLoss[];
    financial_metrics?: Record<string, number | string>;
    win_loss_by_type?: ByType[];
    streak_data?: StreakPoint[];
    size_counts?: SizeCount[];
    duration_bins?: DurationBin[];
  };
}) {
  const winLoss = stats.win_loss || [];
  const totalTrades = winLoss.reduce((acc, cur) => acc + (cur.value || 0), 0);
  const fin = stats.financial_metrics || {};
  const largestWinTime = fin["Largest Win Time"];
  const largestLossTime = fin["Largest Loss Time"];
  const finMax = Math.max(
    ...Object.entries(fin)
      .filter(([k, v]) => typeof v === "number" && !k.toLowerCase().includes("time"))
      .map(([, v]) => Math.abs(v as number)),
    1
  );
  const byType = stats.win_loss_by_type || [];
  const streak = stats.streak_data || [];
  const streakMax = Math.max(1, ...streak.map((s) => Math.abs(Number(s.Streak || 0))));
  const sizeCounts = stats.size_counts || [];
  const durationBins = stats.duration_bins || [];

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
      <Card>
        <div className="pb-2">
          <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Win / Loss</h3>
        </div>
        <div className="space-y-3 text-sm text-slate-200">
          {winLoss.map((w) => (
            <BarRow key={w.label} label={w.label} value={w.value} total={totalTrades} color="#5bc0be" />
          ))}
          {byType.length ? (
            <table className="w-full text-xs text-slate-200">
              <thead>
                <tr className="text-slate-400">
                  <th className="text-left"></th>
                  <th className="text-right text-emerald-300">Win</th>
                  <th className="text-right text-rose-300">Loss</th>
                </tr>
              </thead>
              <tbody>
                {byType.map((row) => (
                  <tr key={row.Type}>
                    <td className="py-1">{row.Type}</td>
                    <td className="py-1 text-right text-emerald-300">{row.Wins}</td>
                    <td className="py-1 text-right text-rose-300">{row.Losses}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </div>
      </Card>

      <Card>
        <div className="pb-2">
          <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Financial</h3>
        </div>
        <div className="space-y-2 text-sm text-slate-200">
          {Object.entries(fin)
            .filter(([k]) => !k.toLowerCase().includes("time"))
            .map(([k, v]) => {
              const num = typeof v === "number" ? v : 0;
              const pct = finMax ? Math.min(100, (Math.abs(num) / finMax) * 100) : 0;
              const color = num >= 0 ? "#5bc0be" : "#ff6b6b";
              const display = typeof v === "number" ? v.toFixed(2) : String(v);
              const timeTip =
                k.toLowerCase() === "largest win" && largestWinTime
                  ? String(largestWinTime)
                  : k.toLowerCase() === "largest loss" && largestLossTime
                    ? String(largestLossTime)
                    : undefined;
              return (
                <div key={k} className="space-y-1">
                  <div className="flex justify-between text-xs text-slate-400">
                    <span>{k}</span>
                    <span className="text-slate-200">
                      {display}
                    </span>
                  </div>
                  {timeTip ? (
                    <div className="flex justify-end text-[10px] text-slate-400">
                      <span>{timeTip}</span>
                    </div>
                  ) : null}
                  <div className="h-2 w-full rounded-full bg-white/10">
                    <div className="h-2 rounded-full" style={{ width: `${pct}%`, background: color }} />
                  </div>
                </div>
              );
            })}
        </div>
      </Card>

      <Card>
        <div className="pb-2">
          <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Streak</h3>
        </div>
        <div className="text-sm text-slate-200 pt-3">
          {streak.length > 0 ? (
            <div className="relative h-40 overflow-visible">
              <div className="absolute inset-0 flex items-center">
                {streak.map((s, idx) => {
                  const val = Number(s.Streak || 0);
                  const widthPct = 100 / Math.max(1, streak.length);
                  const maxHeightPx = 60;
                  const heightPx = Math.max(2, (Math.abs(val) / streakMax) * maxHeightPx);
                  const tooltip = `Trade ${s.TradeIndex ?? idx + 1}: ${val}`;
                  const isUp = val >= 0;
                  const leftPct = idx * widthPct;
                  const top = isUp ? `calc(50% - ${heightPx}px)` : "50%";
                  return (
                    <div
                      key={idx}
                      className="group absolute"
                      style={{ left: `${leftPct}%`, width: `${widthPct}%`, top: 0, bottom: 0 }}
                    >
                      <div className="absolute -top-6 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-black/80 px-2 py-1 text-[10px] text-white opacity-0 transition group-hover:opacity-100">
                        {tooltip}
                      </div>
                      <div
                        className="absolute w-full rounded-sm"
                        style={{
                          height: `${heightPx}px`,
                          top,
                          background: isUp ? "#5bc0be" : "#ff6b6b"
                        }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <p className="text-slate-400">No streak data.</p>
          )}
        </div>
      </Card>

      <Card>
        <div className="pb-2">
          <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Size Distribution</h3>
        </div>
        <div className="text-sm text-slate-200 pt-3">
          {sizeCounts.length > 0 ? (
            <div className="relative h-40">
              {(() => {
                const sorted = [...sizeCounts].sort((a, b) => Number(a.Size) - Number(b.Size));
                const maxCount = Math.max(...sorted.map((r) => Number(r.Count) || 0), 1);
                const maxHeightPx = 120;
                return (
                  <div className="flex h-full items-end gap-2">
                    {sorted.map((row) => {
                      const count = Number(row.Count) || 0;
                      const heightPx = Math.max(4, (count / maxCount) * maxHeightPx);
                      return (
                        <div key={row.Size} className="group relative flex-1">
                        <div className="absolute -top-6 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-black/80 px-2 py-1 text-[10px] text-white opacity-0 transition group-hover:opacity-100">
                          {count}
                        </div>
                          <div
                            className="w-full rounded bg-accent"
                            style={{ height: `${heightPx}px`, minHeight: "4px" }}
                            title={`Size ${row.Size}: ${count}`}
                          />
                          <div className="mt-1 text-center text-[10px] text-slate-300">{row.Size}</div>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </div>
          ) : (
            <p className="text-slate-400">No size data.</p>
          )}
        </div>
      </Card>

      <Card>
        <div className="pb-2">
          <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Position Hold Time</h3>
        </div>
        <div className="text-sm text-slate-200 pt-3">
          {durationBins.length > 0 ? (
            <div className="relative h-40">
              {(() => {
                const maxCount = Math.max(...durationBins.map((b) => Number(b.count) || 0), 1);
                const maxHeightPx = 120;
                return (
                  <div className="flex h-full items-end gap-2">
                    {durationBins.map((bin) => {
                      const count = Number(bin.count) || 0;
                      const heightPx = Math.max(4, (count / maxCount) * maxHeightPx);
                      return (
                        <div key={bin.label} className="group relative flex-1">
                      <div className="absolute -top-6 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-black/80 px-2 py-1 text-[10px] text-white opacity-0 transition group-hover:opacity-100">
                        {count}
                      </div>
                          <div
                            className="w-full rounded bg-highlight"
                            style={{ height: `${heightPx}px`, minHeight: "4px" }}
                            title={`${bin.label}: ${count}`}
                          />
                          <div className="mt-1 text-center text-[10px] text-slate-300">{bin.label}</div>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </div>
          ) : (
            <p className="text-slate-400">No duration data.</p>
          )}
        </div>
      </Card>
    </div>
  );
}
