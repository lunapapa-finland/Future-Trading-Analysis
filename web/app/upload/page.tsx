"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { postTradeUploadCommit, postTradeUploadParsePreview, postTradeUploadReconcilePreview } from "@/lib/api";
import type { LiveJournalRow } from "@/lib/types";
import { useMemo, useState } from "react";

type ParsePreview = {
  can_continue: boolean;
  hard_blocked: boolean;
  parse_logs: Array<Record<string, unknown>>;
  unparseable_rows: Array<Record<string, unknown>>;
  parsed_trades: Array<Record<string, unknown>>;
  execution_pool: Array<Record<string, unknown>>;
  parsed_range: { start: string; end: string; days: string[] };
};

type ReconcilePreview = {
  parsed_range: { start: string; end: string; days: string[] };
  parsed_trades: Array<Record<string, unknown>>;
  journal_rows: LiveJournalRow[];
  suggestions: Array<Record<string, unknown>>;
  summary: {
    trade_count: number;
    journal_count: number;
    suggestion_count: number;
    recommended_count: number;
    hard_conflict_count: number;
  };
};

type WorkingTrade = Record<string, unknown> & { work_id: string };
type PoolLeg = {
  leg_id: string;
  source_trade_id: string;
  TradeDay: string;
  ContractName: string;
  Time: string;
  Qty: number;
  Price: number;
  Fee: number;
};

const POINT_VALUE_BY_ROOT: Record<string, number> = {
  MES: 5,
  MNQ: 2,
  M2K: 5,
  M6E: 12500,
  M6B: 6250,
  MBT: 0.1,
  MET: 0.1,
};

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "-";
  const s = String(v).trim();
  return s || "-";
}

function toNum(v: unknown, fallback = 0): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function tradeIdOf(t: Record<string, unknown>, idx: number): string {
  return String(t["work_id"] || t["preview_trade_id"] || t["trade_id"] || `trade-${idx}`);
}

function normalizeWorkingTrades(rows: Array<Record<string, unknown>>): WorkingTrade[] {
  return rows.map((r, i) => ({
    ...r,
    work_id: tradeIdOf(r, i),
  }));
}

function symbolRoot(contract: string): string {
  const s = String(contract || "").toUpperCase().split(".")[0];
  const knownRoots = Object.keys(POINT_VALUE_BY_ROOT).sort((a, b) => b.length - a.length);
  const pref = knownRoots.find((root) => s.startsWith(root));
  if (pref) return pref;
  const m = s.match(/^([A-Z0-9]+?)([FGHJKMNQUVXZ])(\d{1,2})$/);
  if (m) return m[1];
  const m2 = s.match(/^([A-Z0-9]+)/);
  return m2 ? m2[1] : s;
}

function pointValueFor(contract: string): number {
  return POINT_VALUE_BY_ROOT[symbolRoot(contract)] ?? 5;
}

function durationText(startRaw: string, endRaw: string): string {
  const s = Date.parse(startRaw);
  const e = Date.parse(endRaw);
  if (!Number.isFinite(s) || !Number.isFinite(e) || e < s) return "0 days 00:00:00";
  let sec = Math.floor((e - s) / 1000);
  const days = Math.floor(sec / 86400);
  sec %= 86400;
  const hh = Math.floor(sec / 3600);
  sec %= 3600;
  const mm = Math.floor(sec / 60);
  sec %= 60;
  return `${days} days ${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

export default function UploadPage() {
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [archiveRaw, setArchiveRaw] = useState(false);
  const [busyParse, setBusyParse] = useState(false);
  const [busyReconcile, setBusyReconcile] = useState(false);
  const [busyCommit, setBusyCommit] = useState(false);
  const [commitLocked, setCommitLocked] = useState(false);
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<ParsePreview | null>(null);
  const [reconcile, setReconcile] = useState<ReconcilePreview | null>(null);
  const [workingTrades, setWorkingTrades] = useState<WorkingTrade[]>([]);
  const [poolLegs, setPoolLegs] = useState<PoolLeg[]>([]);
  const [rawLegCatalog, setRawLegCatalog] = useState<PoolLeg[]>([]);
  const [selectedLegIds, setSelectedLegIds] = useState<string[]>([]);
  const [selectedJournalId, setSelectedJournalId] = useState("");

  const parsedTrades = useMemo(() => preview?.parsed_trades || [], [preview?.parsed_trades]);
  const suggestedByTrade = useMemo(() => {
    const out = new Map<string, Record<string, unknown>[]>();
    (reconcile?.suggestions || []).forEach((s) => {
      const tid = String(s["preview_trade_id"] || "").trim();
      if (!tid) return;
      out.set(tid, [...(out.get(tid) || []), s]);
    });
    out.forEach((arr, k) => {
      out.set(
        k,
        [...arr].sort((a, b) => {
          const ta = Number(a["tier"] || 9);
          const tb = Number(b["tier"] || 9);
          if (ta !== tb) return ta - tb;
          return Number(b["score"] || 0) - Number(a["score"] || 0);
        })
      );
    });
    return out;
  }, [reconcile?.suggestions]);
  const journalById = useMemo(() => {
    const m = new Map<string, LiveJournalRow>();
    (reconcile?.journal_rows || []).forEach((j) => {
      const jid = String(j.journal_id || "").trim();
      if (jid) m.set(jid, j);
    });
    return m;
  }, [reconcile?.journal_rows]);

  const selectedLegSet = useMemo(() => new Set(selectedLegIds), [selectedLegIds]);

  async function runParsePreview() {
    if (!uploadFiles.length) {
      setMessage("Select at least one CSV file.");
      return;
    }
    setBusyParse(true);
    setMessage("");
    try {
      const resp = await postTradeUploadParsePreview(uploadFiles, { archiveRaw });
      setPreview(resp);
      setReconcile(null);
      setWorkingTrades([]);
      setPoolLegs([]);
      setRawLegCatalog(
        (resp.execution_pool || []).map((r, i) => ({
          leg_id: String(r["raw_fill_id"] || `raw_leg_${i}`),
          source_trade_id: String(r["preview_trade_id"] || r["trade_id"] || "").trim(),
          TradeDay: String(r["TradeDay"] || "").trim(),
          ContractName: String(r["ContractName"] || "").trim(),
          Time: String(r["Time"] || "").trim(),
          Qty: toNum(r["Qty"], 0),
          Price: toNum(r["Price"], 0),
          Fee: toNum(r["Fee"], 0),
        }))
      );
      setSelectedJournalId("");
      setSelectedLegIds([]);
      setCommitLocked(false);
      setMessage(`Parsed trades: ${resp.parsed_trades.length}. Unparseable rows: ${resp.unparseable_rows.length}.`);
      setUploadFiles([]);
    } catch (e) {
      setMessage(`Parse preview failed: ${(e as Error).message}`);
    } finally {
      setBusyParse(false);
    }
  }

  async function runReconcilePreviewWithRows(rows: Array<Record<string, unknown>>) {
    const resp = await postTradeUploadReconcilePreview({ parsed_trades: rows });
    setReconcile(resp);
    setWorkingTrades(normalizeWorkingTrades(resp.parsed_trades));
  }

  async function runReconcilePreview() {
    if (!preview) {
      setMessage("Run parse preview first.");
      return;
    }
    if (preview.hard_blocked || !preview.can_continue) {
      setMessage("Reconciliation blocked. Fix parse errors first.");
      return;
    }
    if (!preview.parsed_trades.length) {
      setMessage("Reconciliation blocked. No parsed trades.");
      return;
    }
    setBusyReconcile(true);
    setMessage("");
    try {
      await runReconcilePreviewWithRows(preview.parsed_trades);
      setPoolLegs([]);
      setSelectedLegIds([]);
      setMessage("Reconciliation ready. You can split/merge trades before commit.");
    } catch (e) {
      setMessage(`Reconciliation preview failed: ${(e as Error).message}`);
    } finally {
      setBusyReconcile(false);
    }
  }

  function splitTradeToPool(workId: string) {
    const target = workingTrades.find((t) => String(t.work_id) === String(workId));
    if (!target) return;
    const sourceTradeId = String(target["preview_trade_id"] || target["trade_id"] || workId).trim();
    const rawLegs = rawLegCatalog.filter((l) => l.source_trade_id === sourceTradeId);
    if (rawLegs.length > 0) {
      setWorkingTrades((prev) => prev.filter((t) => String(t.work_id) !== String(workId)));
      setPoolLegs((prev) => [...prev, ...rawLegs]);
      setMessage(`Split ${workId} into ${rawLegs.length} raw-derived execution legs.`);
      return;
    }

    // Fallback for trades created in UI by manual merge (not present in raw catalog).
    const size = Math.max(1, Math.abs(toNum(target["Size"], 1)));
    const typ = String(target["Type"] || "").toLowerCase();
    const isLong = typ === "long";
    const qtyOpen = isLong ? size : -size;
    const qtyClose = -qtyOpen;
    const feeTotal = toNum(target["Fees"], 0);
    const feeHalf = feeTotal / 2;
    const stamp = `${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
    const legA: PoolLeg = {
      leg_id: `leg_${stamp}_a`,
      source_trade_id: workId,
      TradeDay: String(target["TradeDay"] || ""),
      ContractName: String(target["ContractName"] || ""),
      Time: String(target["EnteredAt"] || ""),
      Qty: qtyOpen,
      Price: toNum(target["EntryPrice"], 0),
      Fee: feeHalf,
    };
    const legB: PoolLeg = {
      leg_id: `leg_${stamp}_b`,
      source_trade_id: workId,
      TradeDay: String(target["TradeDay"] || ""),
      ContractName: String(target["ContractName"] || ""),
      Time: String(target["ExitedAt"] || ""),
      Qty: qtyClose,
      Price: toNum(target["ExitPrice"], 0),
      Fee: feeTotal - feeHalf,
    };
    setWorkingTrades((prev) => prev.filter((t) => String(t.work_id) !== String(workId)));
    setPoolLegs((prev) => [...prev, legA, legB]);
    setMessage(`Split ${workId} into synthetic execution legs (manual-merge trade fallback).`);
  }

  function mergeSelectedPoolLegs() {
    const selected = poolLegs.filter((l) => selectedLegSet.has(l.leg_id));
    if (selected.length < 2) {
      setMessage("Select at least two execution legs to merge.");
      return;
    }
    const contract = selected[0].ContractName;
    if (!selected.every((l) => l.ContractName === contract)) {
      setMessage("Merge blocked. Selected legs must share the same contract.");
      return;
    }
    const tradeDay = String(selected[0].TradeDay || "");
    if (!selected.every((l) => String(l.TradeDay || "") === tradeDay)) {
      setMessage("Merge blocked. Selected legs must be from the same TradeDay.");
      return;
    }
    const netQty = selected.reduce((a, b) => a + b.Qty, 0);
    if (Math.abs(netQty) > 1e-9) {
      setMessage(`Merge blocked. Selected net quantity must be 0, got ${netQty}.`);
      return;
    }
    const parsedTimes = selected.map((l) => Date.parse(l.Time));
    if (parsedTimes.some((v) => !Number.isFinite(v))) {
      setMessage("Merge blocked. Selected legs must have valid Time values.");
      return;
    }
    const timeByLegId = new Map(selected.map((l) => [l.leg_id, Date.parse(l.Time)]));
    const ordered = [...selected].sort((a, b) => (timeByLegId.get(a.leg_id) || 0) - (timeByLegId.get(b.leg_id) || 0));
    const first = ordered.find((l) => l.Qty !== 0);
    if (!first) {
      setMessage("Merge blocked. Invalid leg quantities.");
      return;
    }
    const openSign = first.Qty > 0 ? 1 : -1;
    const opening = ordered.filter((l) => (l.Qty > 0 ? 1 : -1) === openSign);
    const closing = ordered.filter((l) => (l.Qty > 0 ? 1 : -1) !== openSign);
    const openQty = opening.reduce((a, b) => a + Math.abs(b.Qty), 0);
    const closeQty = closing.reduce((a, b) => a + Math.abs(b.Qty), 0);
    if (openQty <= 0 || Math.abs(openQty - closeQty) > 1e-9) {
      setMessage("Merge blocked. Opening and closing quantities must balance.");
      return;
    }

    const entryPrice = opening.reduce((a, b) => a + b.Price * Math.abs(b.Qty), 0) / openQty;
    const exitPrice = closing.reduce((a, b) => a + b.Price * Math.abs(b.Qty), 0) / closeQty;
    const enteredAt = opening[0]?.Time || ordered[0].Time;
    const exitedAt = closing[closing.length - 1]?.Time || ordered[ordered.length - 1].Time;
    const fees = selected.reduce((a, b) => a + b.Fee, 0);
    const tradeType = openSign > 0 ? "Long" : "Short";
    const pointValue = pointValueFor(contract);
    const pnlGross = tradeType === "Long" ? (exitPrice - entryPrice) * pointValue * openQty : (entryPrice - exitPrice) * pointValue * openQty;
    const pnl = pnlGross - fees;
    const newId = `manual_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
    const nextTrade: WorkingTrade = {
      work_id: newId,
      preview_trade_id: newId,
      ContractName: contract,
      EnteredAt: enteredAt,
      ExitedAt: exitedAt,
      EntryPrice: Number(entryPrice.toFixed(6)),
      ExitPrice: Number(exitPrice.toFixed(6)),
      Fees: Number(fees.toFixed(2)),
      PnL: Number(pnl.toFixed(2)),
      Size: openQty,
      Type: tradeType,
      TradeDay: tradeDay,
      TradeDuration: durationText(enteredAt, exitedAt),
    };
    setWorkingTrades((prev) => [...prev, nextTrade].sort((a, b) => String(a["EnteredAt"] || "").localeCompare(String(b["EnteredAt"] || ""))));
    setPoolLegs((prev) => prev.filter((l) => !selectedLegSet.has(l.leg_id)));
    setSelectedLegIds([]);
    setMessage(`Merged ${selected.length} legs into trade ${newId}.`);
  }

  async function refreshSuggestionsAfterAdjustments() {
    if (!workingTrades.length) {
      setMessage("No working trades to reconcile.");
      return;
    }
    if (poolLegs.length > 0) {
      setMessage("Reconcile refresh blocked. Merge or clear all execution legs from pool first.");
      return;
    }
    setBusyReconcile(true);
    setMessage("");
    try {
      const rows = workingTrades.map(({ work_id: _x, ...rest }) => rest);
      await runReconcilePreviewWithRows(rows);
      setMessage("Recommendations refreshed on adjusted trades.");
    } catch (e) {
      setMessage(`Refresh failed: ${(e as Error).message}`);
    } finally {
      setBusyReconcile(false);
    }
  }

  async function commitMerge() {
    if (commitLocked) {
      setMessage("Commit blocked. This preview is already committed. Run parse preview again before another commit.");
      return;
    }
    if (!preview) {
      setMessage("Run parse preview first.");
      return;
    }
    if (preview.hard_blocked || !preview.can_continue) {
      setMessage("Commit blocked. Fix parse errors first.");
      return;
    }
    if (!reconcile) {
      setMessage("Commit blocked. Run reconciliation preview first.");
      return;
    }
    if (!workingTrades.length) {
      setMessage("Commit blocked. No working trades.");
      return;
    }
    if (poolLegs.length) {
      setMessage("Commit blocked. Execution pool is not empty. Merge or remove pool legs first.");
      return;
    }
    setBusyCommit(true);
    setMessage("");
    try {
      const rows = workingTrades.map(({ work_id: _x, ...rest }) => rest);
      const resp = await postTradeUploadCommit({ parsed_trades: rows });
      setCommitLocked(true);
      setMessage(`Merged successfully. Rows delta: ${resp.rows_delta}.`);
    } catch (e) {
      setMessage(`Commit failed: ${(e as Error).message}`);
    } finally {
      setBusyCommit(false);
    }
  }

  return (
    <AppShell active="/upload">
      <Card title="Step 1: Upload and Parse Preview">
        <div className="space-y-3">
          <p className="text-xs text-slate-400">Upload raw CSVs and parse FIFO round-trip trades. No persistence in this step.</p>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="file"
              accept=".csv"
              multiple
              onChange={(e) => setUploadFiles(Array.from(e.target.files || []))}
              className="rounded border border-white/10 bg-surface px-2 py-1 text-xs text-slate-200"
            />
            <label className="inline-flex items-center gap-2 text-xs text-slate-300">
              <input type="checkbox" checked={archiveRaw} onChange={(e) => setArchiveRaw(e.target.checked)} />
              Archive raw uploads
            </label>
            <button
              onClick={runParsePreview}
              disabled={busyParse}
              className="rounded border border-emerald-400/50 px-3 py-2 text-xs text-emerald-200 disabled:opacity-60"
            >
              {busyParse ? "Parsing..." : "Upload + Parse Preview"}
            </button>
            <span className="text-xs text-slate-400">{uploadFiles.length ? `${uploadFiles.length} file(s) selected` : "No files selected"}</span>
          </div>

          {preview ? (
            <div className="space-y-2 rounded border border-white/10 bg-white/5 p-3 text-xs">
              <p>
                Parsed trades: <span className="text-white">{preview.parsed_trades.length}</span> | Range: <span className="text-white">{preview.parsed_range.start || "-"} → {preview.parsed_range.end || "-"}</span>
              </p>
              <p>
                Gate: <span className={preview.can_continue ? "text-emerald-300" : "text-red-300"}>{preview.can_continue ? "open" : "blocked"}</span>
              </p>
            </div>
          ) : null}

          {preview?.parse_logs?.length ? (
            <div className="rounded border border-white/10 bg-white/5 p-3">
              <p className="mb-2 text-xs uppercase tracking-[0.12em] text-slate-400">Parse Logs</p>
              <div className="space-y-1 text-xs text-slate-200">
                {preview.parse_logs.map((r, i) => (
                  <div key={i} className="rounded border border-white/10 bg-surface px-2 py-1">{JSON.stringify(r)}</div>
                ))}
              </div>
            </div>
          ) : null}

          {preview?.unparseable_rows?.length ? (
            <div className="rounded border border-red-400/30 bg-red-500/10 p-3">
              <p className="mb-2 text-xs uppercase tracking-[0.12em] text-red-300">Unparseable Rows (Commit Blocked)</p>
              <div className="max-h-56 space-y-1 overflow-auto text-xs text-red-100">
                {preview.unparseable_rows.map((r, i) => (
                  <div key={i} className="rounded border border-red-300/30 px-2 py-1">{JSON.stringify(r)}</div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </Card>

      <Card title="Step 2: Reconciliation + Split/Merge Workspace">
        <div className="space-y-3 text-xs text-slate-300">
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={runReconcilePreview}
              disabled={busyReconcile || !(preview?.can_continue ?? false) || parsedTrades.length === 0}
              className="rounded border border-sky-400/50 px-3 py-2 text-xs text-sky-200 disabled:opacity-60"
            >
              {busyReconcile ? "Reconciling..." : "Run Reconciliation Preview"}
            </button>
            <button
              onClick={refreshSuggestionsAfterAdjustments}
              disabled={busyReconcile || !workingTrades.length || poolLegs.length > 0}
              className="rounded border border-indigo-400/50 px-3 py-2 text-xs text-indigo-200 disabled:opacity-60"
            >
              Refresh Recommendations
            </button>
            <button
              onClick={mergeSelectedPoolLegs}
              disabled={selectedLegIds.length < 2}
              className="rounded border border-amber-400/50 px-3 py-2 text-xs text-amber-200 disabled:opacity-60"
            >
              Merge Selected Legs
            </button>
          </div>

          {reconcile ? (
            <div className="rounded border border-white/10 bg-white/5 p-3">
              <div className="grid gap-2 text-xs md:grid-cols-3">
                <p>Working trades: <span className="text-white">{workingTrades.length}</span></p>
                <p>Journal rows: <span className="text-white">{reconcile.summary.journal_count}</span></p>
                <p>Recommended pairs: <span className="text-white">{(reconcile.suggestions || []).filter((s) => Boolean(s["recommended"])).length}</span></p>
                <p>Pool legs: <span className="text-white">{poolLegs.length}</span></p>
                <p>Range start: <span className="text-white">{reconcile.parsed_range.start || "-"}</span></p>
                <p>Range end: <span className="text-white">{reconcile.parsed_range.end || "-"}</span></p>
              </div>
            </div>
          ) : null}

          <div className="grid gap-3 xl:grid-cols-2">
            <div className="space-y-2 rounded border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.12em] text-slate-400">Left: Working Trades</p>
              <div className="max-h-[420px] space-y-2 overflow-auto pr-1">
                {workingTrades.map((t, idx) => {
                  const tid = tradeIdOf(t, idx);
                  const tradeSuggestions = suggestedByTrade.get(String(t["preview_trade_id"] || tid)) || [];
                  return (
                    <div key={tid} className="rounded border border-white/10 bg-surface p-3">
                      <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
                        <span>{fmt(t["TradeDay"])}</span>
                        <span>{fmt(t["ContractName"])}</span>
                        <span>{fmt(t["Type"])}</span>
                        <span>Size {fmt(t["Size"])}</span>
                        <span>Entry {fmt(t["EntryPrice"])}</span>
                        <span>Exit {fmt(t["ExitPrice"])}</span>
                      </div>
                      <div className="mt-1 font-mono text-[11px] text-slate-400">{tid}</div>
                      {tradeSuggestions.length ? (
                        <div className="mt-2 space-y-1">
                          <p className="text-[11px] text-slate-400">Attached Journals</p>
                          <div className="flex flex-wrap gap-1">
                            {tradeSuggestions.map((s, i) => {
                              const jid = String(s["journal_id"] || "");
                              const selected = selectedJournalId === jid;
                              return (
                                <button
                                  key={`${tid}-${jid}-${i}`}
                                  onClick={() => setSelectedJournalId(jid)}
                                  className={`rounded border px-2 py-0.5 text-[11px] ${
                                    selected ? "border-emerald-300/60 bg-emerald-500/10 text-emerald-100" : "border-white/20 text-slate-200"
                                  }`}
                                >
                                  {jid} | tier {fmt(s["tier"])} | score {fmt(s["score"])}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ) : (
                        <div className="mt-2 text-[11px] text-slate-500">No suggested journal for this trade.</div>
                      )}
                      {selectedJournalId && tradeSuggestions.some((s) => String(s["journal_id"] || "") === selectedJournalId) ? (
                        <div className="mt-2 rounded border border-white/10 bg-white/5 p-2 text-[11px] text-slate-200">
                          {(() => {
                            const j = journalById.get(selectedJournalId);
                            if (!j) return <p>Journal details unavailable.</p>;
                            return (
                              <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                                <span>{fmt(j.TradeDay)}</span>
                                <span>Seq {fmt(j.SeqInDay)}</span>
                                <span>{fmt(j.Direction)}</span>
                                <span>Size {fmt(j.Size)}</span>
                                <span>Contract {fmt(j.ContractName)}</span>
                                <span>Intent {fmt(j.TradeIntent)}</span>
                                <span>Phase {fmt(j.Phase)}</span>
                                <span>Context {fmt(j.Context)}</span>
                                <span>Setup {fmt(j.Setup)}</span>
                                <span>Signal {fmt(j.SignalBar)}</span>
                                <span>Entry {fmt(j.EntryPrice)}</span>
                                <span>Exit {fmt(j.ExitPrice)}</span>
                              </div>
                            );
                          })()}
                        </div>
                      ) : null}
                      <div className="mt-2">
                        <button
                          onClick={() => splitTradeToPool(String(t.work_id))}
                          className="rounded border border-rose-400/50 px-2 py-1 text-[11px] text-rose-200"
                        >
                          Split To Pool
                        </button>
                      </div>
                    </div>
                  );
                })}
                {!workingTrades.length ? <p className="text-xs text-slate-500">No working trades.</p> : null}
              </div>
            </div>

            <div className="space-y-2 rounded border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.12em] text-slate-400">Right: Execution Pool (Select Legs To Merge)</p>
              <div className="max-h-[420px] space-y-2 overflow-auto pr-1">
                {poolLegs.map((l) => {
                  const selected = selectedLegSet.has(l.leg_id);
                  return (
                    <button
                      key={l.leg_id}
                      onClick={() =>
                        setSelectedLegIds((prev) => (prev.includes(l.leg_id) ? prev.filter((x) => x !== l.leg_id) : [...prev, l.leg_id]))
                      }
                      className={`w-full rounded border p-2 text-left text-xs ${
                        selected ? "border-amber-300/60 bg-amber-500/10" : "border-white/10 bg-surface"
                      }`}
                    >
                      <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
                        <span>{fmt(l.TradeDay)}</span>
                        <span>{fmt(l.ContractName)}</span>
                        <span>Qty {fmt(l.Qty)}</span>
                        <span>Px {fmt(l.Price)}</span>
                        <span>Fee {fmt(l.Fee)}</span>
                      </div>
                      <div className="mt-1 font-mono text-[11px] text-slate-400">{l.Time}</div>
                    </button>
                  );
                })}
                {!poolLegs.length ? <p className="text-xs text-slate-500">Pool is empty.</p> : null}
              </div>
            </div>
          </div>
        </div>
      </Card>

      <Card title="Step 3: Commit Merge to Performance">
        <div className="space-y-2 text-xs text-slate-300">
          <p>Working trades ready: <span className="text-white">{workingTrades.length}</span></p>
          <p>Execution pool must be empty: <span className={poolLegs.length ? "text-red-300" : "text-emerald-300"}>{poolLegs.length ? "blocked" : "open"}</span></p>
          <p>Commit lock: <span className={commitLocked ? "text-red-300" : "text-emerald-300"}>{commitLocked ? "locked (run parse preview again)" : "open"}</span></p>
          <button
            onClick={commitMerge}
            disabled={busyCommit || commitLocked || !(preview?.can_continue ?? false) || !reconcile || workingTrades.length === 0 || poolLegs.length > 0}
            className="rounded bg-accent px-4 py-2 text-sm text-white disabled:opacity-60"
          >
            {busyCommit ? "Committing..." : "Commit Parsed Trades"}
          </button>
        </div>
      </Card>

      <p className="text-xs text-slate-400">{message}</p>
    </AppShell>
  );
}
