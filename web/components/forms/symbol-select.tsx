export const symbols = ["MES", "MNQ", "M2K", "M6E", "M6B", "MBT", "MET"];

export function SymbolSelect({
  value,
  onChange
}: {
  value: string;
  onChange: (s: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Symbol</span>
      <select
        className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-accent"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {symbols.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </div>
  );
}
