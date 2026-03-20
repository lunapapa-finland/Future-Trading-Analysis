"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { fetchConfig } from "@/lib/config";
import { deleteJournalLive, getDayPlan, getDayPlanTaxonomy, getJournalLive, getJournalLiveMeta, postDayPlan, postJournalLive } from "@/lib/api";
import { tradingDateYmd } from "@/lib/trading-date";
import { JournalAdjustment, LiveJournalRow } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

const today = tradingDateYmd(new Date());

type TaxItem = { value: string; hint?: string; order?: number };
type DetailErrors = { qty?: string; entry?: string; tp?: string; sl?: string; exit?: string; row?: string };

function intentKey(v: string): "scalp" | "swing" | "scale_in" | "" {
  const s = String(v || "").trim().toLowerCase().replace("-", "_").replace(" ", "_");
  if (s === "scalp" || s === "swing" || s === "scale_in") return s;
  return "";
}

function emptyDetail(index: number): JournalAdjustment {
  return {
    LegIndex: index,
    Qty: "",
    EntryPrice: "",
    TakeProfitPrice: "",
    StopLossPrice: "",
    ExitPrice: "",
    EnteredAt: "",
    ExitedAt: "",
    Note: "",
  };
}

const emptyDraft = (day: string): LiveJournalRow => ({
  TradeDay: day,
  ContractName: "MES",
  Phase: "",
  Context: "",
  Setup: "",
  SignalBar: "",
  TradeIntent: "",
  Direction: "Long",
  Size: 0,
  MaxLossUSD: 200,
  Notes: "",
  adjustments: [emptyDetail(1)],
});

function normalizeSetupString(v: string): string {
  const vals = v
    .replace(/;/g, "|")
    .replace(/,/g, "|")
    .split("|")
    .map((s) => s.trim())
    .filter(Boolean);
  const out: string[] = [];
  const seen = new Set<string>();
  vals.forEach((s) => {
    const k = s.toLowerCase();
    if (seen.has(k)) return;
    seen.add(k);
    out.push(s);
  });
  return out.join(" | ");
}

function splitSetupValues(v: string): string[] {
  return normalizeSetupString(v)
    .split("|")
    .map((s) => s.trim())
    .filter(Boolean);
}

function selectedHint(items: TaxItem[], value: string): string {
  const hit = items.find((x) => String(x.value) === String(value));
  return String(hit?.hint || "").trim();
}

function num(v: unknown): number | null {
  const n = Number(String(v ?? "").trim());
  return Number.isFinite(n) ? n : null;
}

function isWeekdayYmd(raw: string): boolean {
  const ts = new Date(`${String(raw || "").trim()}T00:00:00`);
  if (Number.isNaN(ts.getTime())) return false;
  const wd = ts.getDay();
  return wd >= 1 && wd <= 5;
}

function fmt(v: number): string {
  return Number.isFinite(v) ? v.toFixed(2) : "";
}

export default function LivePage() {
  const [tradeDay, setTradeDay] = useState(today);
  const [draft, setDraft] = useState<LiveJournalRow>(emptyDraft(today));
  const [editingJournalId, setEditingJournalId] = useState("");
  const [journalMessage, setJournalMessage] = useState("");
  const [planMessage, setPlanMessage] = useState("");
  const [savingJournal, setSavingJournal] = useState(false);
  const [deletingJournalId, setDeletingJournalId] = useState("");
  const [savingPlan, setSavingPlan] = useState(false);
  const [dailyOpen, setDailyOpen] = useState(true);

  const [planBias, setPlanBias] = useState("");
  const [planDayType, setPlanDayType] = useState("");
  const [actualDayType, setActualDayType] = useState("");
  const [planLevels, setPlanLevels] = useState("");
  const [planPrimary, setPlanPrimary] = useState("");
  const [planAvoidance, setPlanAvoidance] = useState("");

  const { data: meta, error: metaError } = useQuery({ queryKey: ["journal-meta"], queryFn: () => getJournalLiveMeta(), staleTime: 0 });
  const { data: config } = useQuery({ queryKey: ["config-symbols"], queryFn: fetchConfig, staleTime: 60_000 });
  const { data: dayPlanTax, error: dayPlanTaxError } = useQuery({ queryKey: ["day-plan-tax"], queryFn: () => getDayPlanTaxonomy(), staleTime: 0 });
  const { data: dayPlanData, refetch: refetchDayPlan, error: dayPlanError } = useQuery({
    queryKey: ["live-day-plan", tradeDay],
    queryFn: () => getDayPlan({ start: tradeDay, end: tradeDay }),
    staleTime: 0,
  });
  const { data: journalData, refetch: refetchJournal, isFetching: journalLoading, error: journalLoadError } = useQuery({
    queryKey: ["live-journal", tradeDay],
    queryFn: () => getJournalLive({ start: tradeDay, end: tradeDay }),
    staleTime: 0,
  });

  const phaseItems = useMemo(() => (meta?.phase || []) as TaxItem[], [meta?.phase]);
  const contextItems = useMemo(() => (meta?.context || []) as TaxItem[], [meta?.context]);
  const signalItems = useMemo(() => (meta?.signal_bar || []) as TaxItem[], [meta?.signal_bar]);
  const intentItems = useMemo(() => (meta?.trade_intent || []) as TaxItem[], [meta?.trade_intent]);
  const setupItems = useMemo(() => (meta?.setup || []) as TaxItem[], [meta?.setup]);
  const pointValueBySymbol = useMemo(() => {
    const out: Record<string, number> = {};
    (meta?.contracts || []).forEach((c) => {
      const key = String(c.symbol || "").trim().toUpperCase();
      if (!key) return;
      out[key] = Number(c.point_value || 0);
    });
    return out;
  }, [meta?.contracts]);

  const symbolOptions = useMemo(() => {
    const items = (config?.symbols || []).map((s) => String(s.symbol || "").trim()).filter(Boolean);
    if (!items.includes("MES")) items.unshift("MES");
    return Array.from(new Set(items));
  }, [config?.symbols]);

  const rows = useMemo(
    () => (journalData?.rows || []).filter((r) => String(r.TradeDay || "") === tradeDay).sort((a, b) => Number(a.SeqInDay || 0) - Number(b.SeqInDay || 0)),
    [journalData?.rows, tradeDay]
  );
  const matchedCount = useMemo(() => rows.filter((r) => String(r.MatchStatus || "") === "matched").length, [rows]);
  const reconfirmCount = useMemo(() => rows.filter((r) => String(r.MatchStatus || "") === "needs_reconfirm").length, [rows]);
  const dayPlan = useMemo(() => (dayPlanData?.rows || [])[0] || null, [dayPlanData?.rows]);
  const setupSelected = useMemo(() => splitSetupValues(String(draft.Setup || "")), [draft.Setup]);

  const details = useMemo(() => (Array.isArray(draft.adjustments) ? draft.adjustments : []), [draft.adjustments]);
  const intent = useMemo(() => intentKey(String(draft.TradeIntent || "")), [draft.TradeIntent]);
  const isScaleIn = intent === "scale_in";
  const pointValue = useMemo(() => pointValueBySymbol[String(draft.ContractName || "MES").toUpperCase()] || 0, [pointValueBySymbol, draft.ContractName]);

  const detailValidation = useMemo(() => {
    const errors: DetailErrors[] = details.map(() => ({}));
    let totalQty = 0;
    let totalRisk = 0;
    let totalReward = 0;
    let firstError = "";
    let finalExit: number | null = null;
    let finalExitTime = "";

    if (!intent) {
      return { errors, totalQty, totalRisk, totalReward, rr: "", firstError: "TradeIntent is required.", ruleViolation: false };
    }
    if (!pointValue || pointValue <= 0) {
      return { errors, totalQty, totalRisk, totalReward, rr: "", firstError: "Missing contract point value.", ruleViolation: false };
    }
    if (!details.length) {
      return { errors, totalQty, totalRisk, totalReward, rr: "", firstError: "At least one execution detail row is required.", ruleViolation: false };
    }
    if ((intent === "scalp" || intent === "swing") && details.length !== 1) {
      return { errors, totalQty, totalRisk, totalReward, rr: "", firstError: `${intent} requires exactly one execution detail row.`, ruleViolation: false };
    }

    details.forEach((d, i) => {
      const e = errors[i];
      const qty = num(d.Qty);
      const entry = num(d.EntryPrice);
      const tp = num(d.TakeProfitPrice);
      const sl = num(d.StopLossPrice);
      const ex = num(d.ExitPrice);
      const exAt = String(d.ExitedAt || "").trim();
      if (qty === null || qty <= 0) e.qty = "Qty must be positive.";
      if (entry === null || entry <= 0) e.entry = "Entry required.";
      if (tp === null || tp <= 0) e.tp = "TP required.";
      if (sl === null || sl <= 0) e.sl = "SL required.";
      if (String(d.ExitPrice || "").trim() && ex === null) e.exit = "Exit must be numeric.";

      if (!e.entry && !e.tp && !e.sl) {
        if (String(draft.Direction) === "Long" && !(Number(sl) < Number(entry) && Number(entry) < Number(tp))) {
          e.row = "Long requires SL < Entry < TP.";
        }
        if (String(draft.Direction) === "Short" && !(Number(tp) < Number(entry) && Number(entry) < Number(sl))) {
          e.row = "Short requires TP < Entry < SL.";
        }
      }

      if (!e.qty && !e.entry && !e.sl && !e.tp) {
        const risk = Math.abs((Number(entry) - Number(sl)) * pointValue * Number(qty));
        const reward = Math.abs((Number(tp) - Number(entry)) * pointValue * Number(qty));
        totalQty += Number(qty);
        totalRisk += risk;
        totalReward += reward;
      }

      if (ex !== null) {
        if (finalExit === null) finalExit = ex;
        else if (Math.abs(finalExit - ex) > 1e-9) e.exit = "Final exit only: keep one shared ExitPrice.";
      }
      if (exAt) {
        if (!finalExitTime) finalExitTime = exAt;
        else if (finalExitTime !== exAt) e.row = "Final exit only: keep one shared ExitedAt.";
      }
      if (!firstError) {
        const m = e.qty || e.entry || e.tp || e.sl || e.exit || e.row || "";
        if (m) firstError = `Row ${i + 1}: ${m}`;
      }
    });

    const rr = totalRisk > 0 ? totalReward / totalRisk : null;
    const maxLoss = num(draft.MaxLossUSD) ?? 200;
    const ruleViolation = totalRisk > maxLoss;
    return { errors, totalQty, totalRisk, totalReward, rr: rr === null ? "" : rr.toFixed(3), firstError, ruleViolation };
  }, [details, draft.Direction, draft.MaxLossUSD, intent, pointValue]);

  useEffect(() => {
    if (!editingJournalId) {
      setDraft((prev) => ({ ...prev, TradeDay: tradeDay }));
    }
  }, [tradeDay, editingJournalId]);

  useEffect(() => {
    if (!editingJournalId && !String(draft.ContractName || "").trim()) {
      setDraft((prev) => ({ ...prev, ContractName: "MES" }));
    }
  }, [draft.ContractName, editingJournalId]);

  useEffect(() => {
    if (!dayPlan) {
      setPlanBias("");
      setPlanDayType("");
      setActualDayType("");
      setPlanLevels("");
      setPlanPrimary("");
      setPlanAvoidance("");
      return;
    }
    setPlanBias(String(dayPlan.Bias || ""));
    setPlanDayType(String(dayPlan.ExpectedDayType || ""));
    setActualDayType(String(dayPlan.ActualDayType || ""));
    setPlanLevels(String(dayPlan.KeyLevelsHTFContext || ""));
    setPlanPrimary(String(dayPlan.PrimaryPlan || ""));
    setPlanAvoidance(String(dayPlan.AvoidancePlan || ""));
  }, [dayPlan]);

  useEffect(() => {
    setDraft((prev) => {
      const current = Array.isArray(prev.adjustments) ? [...prev.adjustments] : [];
      let changed = false;
      if (!current.length) {
        current.push(emptyDetail(1));
        changed = true;
      }
      if (intentKey(String(prev.TradeIntent || "")) !== "scale_in" && current.length > 1) {
        current.splice(1);
        changed = true;
      }
      current.forEach((d, idx) => {
        const want = idx + 1;
        if (Number(d.LegIndex || 0) !== want) {
          d.LegIndex = want;
          changed = true;
        }
      });
      return changed ? { ...prev, adjustments: current } : prev;
    });
  }, [draft.TradeIntent]);

  function toggleSetupChoice(option: string) {
    const current = splitSetupValues(String(draft.Setup || ""));
    const has = current.some((x) => x.toLowerCase() === option.toLowerCase());
    const next = has ? current.filter((x) => x.toLowerCase() !== option.toLowerCase()) : [...current, option];
    setDraft((p) => ({ ...p, Setup: next.join(" | ") }));
  }

  function addDetailRow() {
    setDraft((p) => {
      const cur = Array.isArray(p.adjustments) ? [...p.adjustments] : [];
      cur.push(emptyDetail(cur.length + 1));
      return { ...p, adjustments: cur };
    });
  }

  function removeDetailRow(index: number) {
    setDraft((p) => {
      const cur = Array.isArray(p.adjustments) ? [...p.adjustments] : [];
      if (cur.length <= 1) return p;
      cur.splice(index, 1);
      cur.forEach((d, idx) => {
        d.LegIndex = idx + 1;
      });
      return { ...p, adjustments: cur };
    });
  }

  function updateDetail(index: number, patch: Partial<JournalAdjustment>) {
    setDraft((p) => {
      const cur = Array.isArray(p.adjustments) ? [...p.adjustments] : [];
      const prev = cur[index] || emptyDetail(index + 1);
      cur[index] = { ...prev, ...patch };
      return { ...p, adjustments: cur };
    });
  }

  async function savePlan() {
    if (!isWeekdayYmd(tradeDay)) {
      setPlanMessage("Trade Day must be a weekday (Mon-Fri).");
      return;
    }
    setSavingPlan(true);
    setPlanMessage("");
    try {
      await postDayPlan({
        rows: [
          {
            Date: tradeDay,
            Bias: planBias,
            ExpectedDayType: planDayType,
            ActualDayType: actualDayType,
            KeyLevelsHTFContext: planLevels,
            PrimaryPlan: planPrimary,
            AvoidancePlan: planAvoidance,
          },
        ],
      });
      setPlanMessage("Daily sum saved.");
      await refetchDayPlan();
    } catch (e) {
      setPlanMessage(`Save failed: ${(e as Error).message}`);
    } finally {
      setSavingPlan(false);
    }
  }

  async function saveJournal() {
    if (!isWeekdayYmd(tradeDay)) {
      setJournalMessage("Trade Day must be a weekday (Mon-Fri).");
      return;
    }
    setSavingJournal(true);
    setJournalMessage("");
    try {
      if (detailValidation.firstError) {
        throw new Error(detailValidation.firstError);
      }
      const payload: LiveJournalRow = {
        ...draft,
        journal_id: editingJournalId || undefined,
        TradeDay: tradeDay,
        Setup: normalizeSetupString(String(draft.Setup || "")),
        Size: detailValidation.totalQty,
        MaxLossUSD: num(draft.MaxLossUSD) ?? 200,
        adjustments_mode: "replace",
        adjustments: details.map((d, idx) => ({
          adjustment_id: d.adjustment_id,
          LegIndex: idx + 1,
          Qty: String(d.Qty || "").trim(),
          EntryPrice: String(d.EntryPrice || "").trim(),
          TakeProfitPrice: String(d.TakeProfitPrice || "").trim(),
          StopLossPrice: String(d.StopLossPrice || "").trim(),
          ExitPrice: String(d.ExitPrice || "").trim(),
          EnteredAt: String(d.EnteredAt || "").trim(),
          ExitedAt: String(d.ExitedAt || "").trim(),
          Note: String(d.Note || "").trim(),
        })),
      };
      const resp = await postJournalLive({ rows: [payload] });
      setJournalMessage(`Saved. Inserted ${resp.inserted}, updated ${resp.updated}.`);
      setEditingJournalId("");
      setDraft(emptyDraft(tradeDay));
      await refetchJournal();
    } catch (e) {
      setJournalMessage(`Save failed: ${(e as Error).message}`);
    } finally {
      setSavingJournal(false);
    }
  }

  function startEdit(row: LiveJournalRow) {
    const hasActiveLinks = Array.isArray(row.matches) && row.matches.length > 0;
    if (hasActiveLinks) {
      setJournalMessage("Edit blocked: this journal is linked to an active trade. Unlink first in Trading Match.");
      return;
    }
    setEditingJournalId(String(row.journal_id || ""));
    const incoming = (Array.isArray(row.adjustments) ? row.adjustments : []).map((a, idx) => ({
      adjustment_id: a.adjustment_id,
      LegIndex: Number(a.LegIndex || idx + 1),
      Qty: String(a.Qty || ""),
      EntryPrice: String(a.EntryPrice || ""),
      TakeProfitPrice: String(a.TakeProfitPrice || ""),
      StopLossPrice: String(a.StopLossPrice || ""),
      ExitPrice: String(a.ExitPrice || ""),
      EnteredAt: String(a.EnteredAt || ""),
      ExitedAt: String(a.ExitedAt || ""),
      Note: String(a.Note || ""),
    }));
    setDraft({
      journal_id: row.journal_id,
      TradeDay: tradeDay,
      SeqInDay: row.SeqInDay,
      ContractName: row.ContractName || "MES",
      Phase: row.Phase || "",
      Context: row.Context || "",
      Setup: normalizeSetupString(String(row.Setup || "")),
      SignalBar: row.SignalBar || "",
      TradeIntent: row.TradeIntent || "",
      Direction: (row.Direction as "Long" | "Short") || "Long",
      Size: row.Size || 0,
      MaxLossUSD: row.MaxLossUSD || 200,
      Notes: row.Notes || "",
      adjustments: incoming.length ? incoming : [emptyDetail(1)],
    });
  }

  async function removeJournal(row: LiveJournalRow) {
    const journalId = String(row.journal_id || "").trim();
    if (!journalId) return;
    const status = String(row.MatchStatus || "").trim().toLowerCase() || "unmatched";
    const hasActiveLinks = Array.isArray(row.matches) && row.matches.length > 0;
    if (hasActiveLinks) {
      setJournalMessage("Delete blocked: this journal still has active link(s). Unlink first in Trading Match.");
      return;
    }
    if (!["initial", "unmatched", "needs_reconfirm"].includes(status)) {
      setJournalMessage("Delete blocked: only initial/unmatched or needs_reconfirm rows can be deleted.");
      return;
    }
    const ok = window.confirm(`Delete journal ${journalId}? This also deletes its execution detail rows.`);
    if (!ok) return;
    setDeletingJournalId(journalId);
    setJournalMessage("");
    try {
      const resp = await deleteJournalLive({ journal_id: journalId });
      setJournalMessage(`Deleted ${resp.deleted} journal row, removed ${resp.deleted_adjustments} detail row(s).`);
      if (editingJournalId === journalId) {
        setEditingJournalId("");
        setDraft(emptyDraft(tradeDay));
      }
      await refetchJournal();
    } catch (e) {
      setJournalMessage(`Delete failed: ${(e as Error).message}`);
    } finally {
      setDeletingJournalId("");
    }
  }

  const contractOptions = useMemo(() => {
    const cur = String(draft.ContractName || "").trim();
    if (!cur) return symbolOptions;
    if (symbolOptions.includes(cur)) return symbolOptions;
    return [cur, ...symbolOptions];
  }, [draft.ContractName, symbolOptions]);

  return (
    <AppShell active="/live">
      {metaError || dayPlanTaxError || dayPlanError || journalLoadError ? (
        <Card title="Data Status">
          <div className="text-xs text-amber-300">
            {metaError ? <p>Journal meta load failed: {(metaError as Error).message}</p> : null}
            {dayPlanTaxError ? <p>Day-plan taxonomy load failed: {(dayPlanTaxError as Error).message}</p> : null}
            {dayPlanError ? <p>Day-plan row load failed: {(dayPlanError as Error).message}</p> : null}
            {journalLoadError ? <p>Journal rows load failed: {(journalLoadError as Error).message}</p> : null}
          </div>
        </Card>
      ) : null}
      <Card title="Daily Sum">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-slate-400">Maintained twice per day: pre-trade and post-trade summary.</p>
          <button onClick={() => setDailyOpen((v) => !v)} className="rounded border border-white/20 px-2 py-1 text-xs text-slate-200">
            {dailyOpen ? "Collapse" : "Expand"}
          </button>
        </div>

        <div className="mb-2 grid gap-3 md:grid-cols-4">
          <label className="text-xs text-slate-300">
            Trade Day
            <input
              type="date"
              value={tradeDay}
              onChange={(e) => {
                const next = e.target.value;
                if (!isWeekdayYmd(next)) {
                  setJournalMessage("Trade Day must be a weekday (Mon-Fri).");
                  return;
                }
                setTradeDay(next);
                setJournalMessage("");
                setPlanMessage("");
              }}
              className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white"
            />
          </label>
        </div>

        {dailyOpen ? (
          <>
            <div className="grid gap-3 md:grid-cols-3">
              <label className="text-xs text-slate-300">
                Bias
                <select value={planBias} onChange={(e) => setPlanBias(e.target.value)} className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white">
                  <option value="">Bias</option>
                  {(dayPlanTax?.bias || []).map((x) => <option key={x.value} value={x.value}>{x.value}</option>)}
                </select>
              </label>
              <label className="text-xs text-slate-300">
                Expected Day Type
                <select value={planDayType} onChange={(e) => setPlanDayType(e.target.value)} className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white">
                  <option value="">Expected Day Type</option>
                  {(dayPlanTax?.expected_day_type || []).map((x) => <option key={x.value} value={x.value}>{x.value}</option>)}
                </select>
              </label>
              <label className="text-xs text-slate-300">
                Actual Day Type (post-trade)
                <select value={actualDayType} onChange={(e) => setActualDayType(e.target.value)} className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white">
                  <option value="">Actual Day Type</option>
                  {(dayPlanTax?.actual_day_type || dayPlanTax?.expected_day_type || []).map((x) => <option key={x.value} value={x.value}>{x.value}</option>)}
                </select>
              </label>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <textarea value={planLevels} onChange={(e) => setPlanLevels(e.target.value)} placeholder="Key levels / HTF context" className="h-20 rounded border border-white/10 bg-surface px-2 py-2 text-white" />
              <textarea value={planPrimary} onChange={(e) => setPlanPrimary(e.target.value)} placeholder="Primary plan" className="h-20 rounded border border-white/10 bg-surface px-2 py-2 text-white" />
            </div>
            <textarea value={planAvoidance} onChange={(e) => setPlanAvoidance(e.target.value)} placeholder="Avoidance plan" className="mt-3 h-16 w-full rounded border border-white/10 bg-surface px-2 py-2 text-white" />
            <div className="mt-3 flex items-center gap-3">
              <button onClick={savePlan} disabled={savingPlan} className="rounded bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">{savingPlan ? "Saving..." : "Save Daily Sum"}</button>
              <span className="text-xs text-slate-300">{planMessage}</span>
            </div>
          </>
        ) : null}
      </Card>

      <Card title="Trade Journal">
        <p className="mb-2 text-xs text-slate-400">Intent controls execution detail constraints. Scalp/Swing = one detail row, Scale-in = multiple rows.</p>

        <div className="rounded border border-white/10 bg-white/5 p-3">
          <p className="mb-2 text-xs uppercase tracking-[0.15em] text-slate-400">Category A: Header (Required)</p>
          <div className="grid gap-3 md:grid-cols-4">
            <label className="text-xs text-slate-300">
              Contract Symbol
              <select value={String(draft.ContractName || "MES")} onChange={(e) => setDraft((p) => ({ ...p, ContractName: e.target.value }))} className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white">
                {contractOptions.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label className="text-xs text-slate-300">
              Direction
              <select value={draft.Direction} onChange={(e) => setDraft((p) => ({ ...p, Direction: e.target.value as "Long" | "Short" }))} className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white">
                <option value="Long">Long</option>
                <option value="Short">Short</option>
              </select>
            </label>
            <label className="text-xs text-slate-300">
              Max Loss USD
              <input type="number" min="1" step="1" value={String(draft.MaxLossUSD ?? 200)} onChange={(e) => setDraft((p) => ({ ...p, MaxLossUSD: e.target.value }))} className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white" />
            </label>
            <label className="text-xs text-slate-300">
              Derived Size
              <input
                value={fmt(detailValidation.totalQty)}
                readOnly
                className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white"
              />
            </label>
          </div>
        </div>

        <div className="mt-3 rounded border border-white/10 bg-white/5 p-3">
          <p className="mb-2 text-xs uppercase tracking-[0.15em] text-slate-400">Category B: Taxonomy Tags (Required)</p>
          <div className="grid gap-3 md:grid-cols-4">
            <label className="text-xs text-slate-300">
              Phase
              <select value={draft.Phase} onChange={(e) => setDraft((p) => ({ ...p, Phase: e.target.value }))} className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white">
                <option value="">Phase</option>
                {phaseItems.map((v) => <option key={v.value} value={v.value}>{v.value}</option>)}
              </select>
              {draft.Phase ? <span className="mt-1 block text-[11px] text-slate-400">{selectedHint(phaseItems, String(draft.Phase || ""))}</span> : null}
            </label>
            <label className="text-xs text-slate-300">
              Context
              <select value={draft.Context} onChange={(e) => setDraft((p) => ({ ...p, Context: e.target.value }))} className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white">
                <option value="">Context</option>
                {contextItems.map((v) => <option key={v.value} value={v.value}>{v.value}</option>)}
              </select>
              {draft.Context ? <span className="mt-1 block text-[11px] text-slate-400">{selectedHint(contextItems, String(draft.Context || ""))}</span> : null}
            </label>
            <label className="text-xs text-slate-300">
              SignalBar
              <select value={draft.SignalBar} onChange={(e) => setDraft((p) => ({ ...p, SignalBar: e.target.value }))} className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white">
                <option value="">SignalBar</option>
                {signalItems.map((v) => <option key={v.value} value={v.value}>{v.value}</option>)}
              </select>
              {draft.SignalBar ? <span className="mt-1 block text-[11px] text-slate-400">{selectedHint(signalItems, String(draft.SignalBar || ""))}</span> : null}
            </label>
            <label className="text-xs text-slate-300">
              TradeIntent
              <select value={draft.TradeIntent} onChange={(e) => setDraft((p) => ({ ...p, TradeIntent: e.target.value }))} className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white">
                <option value="">TradeIntent</option>
                {intentItems.map((v) => <option key={v.value} value={v.value}>{v.value}</option>)}
              </select>
              {draft.TradeIntent ? <span className="mt-1 block text-[11px] text-slate-400">{selectedHint(intentItems, String(draft.TradeIntent || ""))}</span> : null}
            </label>
          </div>

          <div className="mt-3 rounded border border-white/10 bg-surface/60 p-2">
            <p className="mb-1 text-[11px] uppercase tracking-[0.12em] text-slate-400">Setup (Multi-Select)</p>
            <div className="mb-2 flex flex-wrap gap-1">
              {setupSelected.length ? setupSelected.map((s) => <span key={s} className="rounded-full border border-accent/40 bg-accent/10 px-2 py-0.5 text-[11px] text-accent">{s}</span>) : <span className="text-[11px] text-slate-500">No setup selected</span>}
            </div>
            <div className="flex flex-wrap gap-1">
              {setupItems.map((opt) => {
                const checked = setupSelected.some((v) => v.toLowerCase() === opt.value.toLowerCase());
                return (
                  <button key={opt.value} type="button" onClick={() => toggleSetupChoice(opt.value)} className={`rounded-full border px-2 py-1 text-[11px] transition ${checked ? "border-accent/50 bg-accent/20 text-accent" : "border-white/15 bg-white/5 text-slate-300 hover:border-accent/40 hover:text-white"}`}>
                    {opt.value}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="mt-3 rounded border border-white/10 bg-white/5 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-xs uppercase tracking-[0.15em] text-slate-400">Category C: Execution Detail Rows</p>
            {isScaleIn ? <button type="button" onClick={addDetailRow} className="rounded border border-accent/50 px-2 py-1 text-[11px] text-accent">Add Scale-in Row</button> : null}
          </div>
          <div className="space-y-2">
            {details.map((d, idx) => {
              const err = detailValidation.errors[idx] || {};
              const qty = num(d.Qty) || 0;
              const entry = num(d.EntryPrice) || 0;
              const tp = num(d.TakeProfitPrice) || 0;
              const sl = num(d.StopLossPrice) || 0;
              const risk = Math.abs((entry - sl) * pointValue * qty);
              const reward = Math.abs((tp - entry) * pointValue * qty);
              const rr = risk > 0 ? reward / risk : 0;
              const hasErr = Boolean(err.qty || err.entry || err.tp || err.sl || err.exit || err.row);
              return (
                <div key={d.adjustment_id || `detail-${idx}`} className={`rounded border p-2 ${hasErr ? "border-rose-400/40" : "border-white/10"} bg-surface/50`}>
                  <div className="mb-2 flex items-center justify-between text-xs text-slate-300">
                    <span>Row {idx + 1}</span>
                    {isScaleIn && details.length > 1 ? <button type="button" onClick={() => removeDetailRow(idx)} className="rounded border border-rose-400/50 px-2 py-0.5 text-[11px] text-rose-300">Remove</button> : null}
                  </div>
                  <div className="grid gap-2 md:grid-cols-5">
                    <input value={String(d.Qty || "")} onChange={(e) => updateDetail(idx, { Qty: e.target.value })} placeholder="Qty" className={`h-9 rounded border bg-surface px-2 text-white ${err.qty ? "border-rose-400/60" : "border-white/10"}`} />
                    <input value={String(d.EntryPrice || "")} onChange={(e) => updateDetail(idx, { EntryPrice: e.target.value })} placeholder="EntryPrice" className={`h-9 rounded border bg-surface px-2 text-white ${err.entry ? "border-rose-400/60" : "border-white/10"}`} />
                    <input value={String(d.TakeProfitPrice || "")} onChange={(e) => updateDetail(idx, { TakeProfitPrice: e.target.value })} placeholder="TakeProfitPrice" className={`h-9 rounded border bg-surface px-2 text-white ${err.tp ? "border-rose-400/60" : "border-white/10"}`} />
                    <input value={String(d.StopLossPrice || "")} onChange={(e) => updateDetail(idx, { StopLossPrice: e.target.value })} placeholder="StopLossPrice" className={`h-9 rounded border bg-surface px-2 text-white ${err.sl ? "border-rose-400/60" : "border-white/10"}`} />
                    <input value={String(d.ExitPrice || "")} onChange={(e) => updateDetail(idx, { ExitPrice: e.target.value })} placeholder="ExitPrice (final shared)" className={`h-9 rounded border bg-surface px-2 text-white ${err.exit ? "border-rose-400/60" : "border-white/10"}`} />
                  </div>
                  <div className="mt-2 grid gap-2 md:grid-cols-3">
                    <input value={String(d.EnteredAt || "")} onChange={(e) => updateDetail(idx, { EnteredAt: e.target.value })} placeholder="EnteredAt (optional)" className="h-9 rounded border border-white/10 bg-surface px-2 text-white" />
                    <input value={String(d.ExitedAt || "")} onChange={(e) => updateDetail(idx, { ExitedAt: e.target.value })} placeholder="ExitedAt (optional, final shared)" className="h-9 rounded border border-white/10 bg-surface px-2 text-white" />
                    <input value={String(d.Note || "")} onChange={(e) => updateDetail(idx, { Note: e.target.value })} placeholder="Note" className="h-9 rounded border border-white/10 bg-surface px-2 text-white" />
                  </div>
                  <div className="mt-2 text-[11px] text-slate-400">Expected Risk ${fmt(risk)} | Expected Reward ${fmt(reward)} | Expected R:R {rr > 0 ? rr.toFixed(3) : "-"}</div>
                  {err.row ? <div className="mt-1 text-[11px] text-rose-300">{err.row}</div> : null}
                  {err.qty || err.entry || err.tp || err.sl || err.exit ? (
                    <div className="mt-1 text-[11px] text-rose-300">{[err.qty, err.entry, err.tp, err.sl, err.exit].filter(Boolean).join(" ")}</div>
                  ) : null}
                </div>
              );
            })}
          </div>

          <div className="mt-3 rounded border border-white/10 bg-surface/40 p-2 text-xs text-slate-300">
            <div>Expected Total Risk: ${fmt(detailValidation.totalRisk)} | Expected Total Reward: ${fmt(detailValidation.totalReward)} | Expected R:R {detailValidation.rr || "-"}</div>
            <div className={detailValidation.ruleViolation ? "text-rose-300" : "text-emerald-300"}>
              Rule Check (MaxLoss ${fmt(num(draft.MaxLossUSD) ?? 200)}): {detailValidation.ruleViolation ? "VIOLATION" : "OK"}
            </div>
          </div>
        </div>

        <div className="mt-3 rounded border border-white/10 bg-white/5 p-3">
          <p className="mb-2 text-xs uppercase tracking-[0.15em] text-slate-400">Category D: Notes</p>
          <textarea value={draft.Notes || ""} onChange={(e) => setDraft((p) => ({ ...p, Notes: e.target.value }))} placeholder="Notes" className="h-16 w-full rounded border border-white/10 bg-surface px-2 py-2 text-white" />
        </div>

        <div className="mt-3 flex items-center gap-2">
          <button onClick={saveJournal} disabled={savingJournal} className="rounded bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
            {savingJournal ? "Saving..." : editingJournalId ? "Update Journal Entry" : "Add Journal Entry"}
          </button>
          {editingJournalId ? <button onClick={() => { setEditingJournalId(""); setDraft(emptyDraft(tradeDay)); }} className="rounded border border-white/20 px-3 py-2 text-sm text-slate-200">Cancel Edit</button> : null}
          <span className="text-xs text-slate-300">{journalMessage}</span>
        </div>

        <div className="mt-4 space-y-2">
          <p className="text-xs text-slate-400">
            {journalLoading ? "Loading..." : `${rows.length} saved row(s) for ${tradeDay} | matched: ${matchedCount} | needs reconfirm: ${reconfirmCount}`}
          </p>
          {rows.map((r) => (
            <div key={String(r.journal_id)} className="rounded border border-white/10 bg-white/5 p-3 text-xs text-slate-200">
              <div className="grid grid-cols-2 gap-2 md:grid-cols-8">
                <span>Seq {r.SeqInDay}</span>
                <span>{r.ContractName || "MES"}</span>
                <span>{r.Direction}</span>
                <span>Size {r.Size}</span>
                <span>{r.Phase}</span>
                <span>{r.Context}</span>
                <span>{r.TradeIntent}</span>
                <span>{r.MatchStatus || "unmatched"}</span>
              </div>
              <div className="mt-1 text-slate-400">Setup: {r.Setup}</div>
              <div className="mt-1 text-slate-400">Expected Risk ${r.PotentialRiskUSD || "-"} | Expected Reward ${r.PotentialRewardUSD || "-"} | Expected R:R {r.WinLossRatio || "-"} | Rule {r.RuleStatus || "-"}</div>
              {Array.isArray(r.adjustments) && r.adjustments.length ? (
                <div className="mt-1 text-slate-400">Details: {r.adjustments.map((a, i) => <span key={a.adjustment_id || `${r.journal_id}-d-${i}`}>{i ? " | " : ""}L{a.LegIndex}: qty {a.Qty} @ {a.EntryPrice} tp {a.TakeProfitPrice} sl {a.StopLossPrice}{a.ExitPrice ? ` exit ${a.ExitPrice}` : ""}</span>)}</div>
              ) : null}
              <div className="mt-2">
                <button
                  onClick={() => startEdit(r)}
                  className="rounded border border-accent/50 px-2 py-1 text-[11px] text-accent"
                >
                  Edit
                </button>
                <button
                  onClick={() => removeJournal(r)}
                  disabled={deletingJournalId === String(r.journal_id || "")}
                  className="ml-2 rounded border border-rose-400/50 px-2 py-1 text-[11px] text-rose-300 disabled:opacity-60"
                >
                  {deletingJournalId === String(r.journal_id || "") ? "Deleting..." : "Delete"}
                </button>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </AppShell>
  );
}
