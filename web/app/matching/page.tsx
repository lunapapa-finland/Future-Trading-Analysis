"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { getMatchingRelinkPreview, postMatchingCommit, postMatchingReconfirm, postMatchingUnlink } from "@/lib/api";
import { tradingDateYmd } from "@/lib/trading-date";
import { LiveJournalRow } from "@/lib/types";
import { useMemo, useState } from "react";

type ParsePreview = {
  can_continue: boolean;
  hard_blocked: boolean;
  parse_logs: Array<Record<string, unknown>>;
  unparseable_rows: Array<Record<string, unknown>>;
  parsed_trades: Array<Record<string, unknown>>;
  parsed_range: { start: string; end: string; days: string[] };
  journal_rows: LiveJournalRow[];
  suggestions: Array<Record<string, unknown>>;
};

type LinkRow = {
  journal_id: string;
  preview_trade_id: string;
  score?: number;
  match_type?: string;
  is_primary?: boolean;
};

function showValue(v: unknown): string {
  if (v === null || v === undefined) return "-";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  const s = String(v).trim();
  return s ? s : "-";
}

export default function MatchingPage() {
  const thisDay = tradingDateYmd(new Date());
  const [busyCommit, setBusyCommit] = useState(false);
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<ParsePreview | null>(null);
  const [selectedJournalId, setSelectedJournalId] = useState("");
  const [dragJournalId, setDragJournalId] = useState("");
  const [links, setLinks] = useState<LinkRow[]>([]);
  const [linkStart, setLinkStart] = useState(thisDay);
  const [linkEnd, setLinkEnd] = useState(thisDay);
  const [unlinkingKey, setUnlinkingKey] = useState("");
  const [reconfirmingKey, setReconfirmingKey] = useState("");
  const [loadingRelinkPreview, setLoadingRelinkPreview] = useState(false);

  const parsedTrades = useMemo(() => preview?.parsed_trades || [], [preview?.parsed_trades]);
  const journalRows = useMemo(() => preview?.journal_rows || [], [preview?.journal_rows]);

  const journalById = useMemo(
    () => new Map(journalRows.map((j) => [String(j.journal_id || ""), j])),
    [journalRows]
  );

  const existingMatchByJournalId = useMemo(() => {
    const out = new Map<string, { trade_id: string; trade_day: string }>();
    journalRows.forEach((j) => {
      const jid = String(j.journal_id || "");
      if (!jid) return;
      const rows = Array.isArray((j as any).matches) ? ((j as any).matches as Array<Record<string, unknown>>) : [];
      const active = rows.find((m) => String(m["Status"] || "").toLowerCase() === "active") || rows[0];
      if (!active) return;
      out.set(jid, {
        trade_id: String(active["trade_id"] || ""),
        trade_day: String(active["TradeDay"] || ""),
      });
    });
    return out;
  }, [journalRows]);

  const assignedJournalIds = useMemo(() => new Set(links.map((l) => String(l.journal_id))), [links]);
  const poolJournals = useMemo(
    () => journalRows.filter((j) => !assignedJournalIds.has(String(j.journal_id || ""))),
    [journalRows, assignedJournalIds]
  );

  const linksByTrade = useMemo(() => {
    const out = new Map<string, LinkRow[]>();
    links.forEach((l) => {
      const tid = String(l.preview_trade_id || "");
      out.set(tid, [...(out.get(tid) || []), l]);
    });
    return out;
  }, [links]);

  const linkCommitSummary = useMemo(() => {
    const journals = new Set<string>();
    const trades = new Set<string>();
    const hardConflictByPair = new Map<string, string[]>();
    (preview?.suggestions || []).forEach((s) => {
      const jid = String(s["journal_id"] || "").trim();
      const tid = String(s["preview_trade_id"] || "").trim();
      if (!jid || !tid || !Boolean(s["hard_conflict"])) return;
      const reasons = Array.isArray(s["reasons"]) ? s["reasons"].map((r) => String(r || "")).filter(Boolean) : [];
      hardConflictByPair.set(`${jid}|${tid}`, reasons);
    });

    const hardConflicts: Array<{ journal_id: string; preview_trade_id: string; reasons: string[] }> = [];
    const lockConflicts: Array<{ journal_id: string; trade_id: string; trade_day: string }> = [];

    links.forEach((l) => {
      const jid = String(l.journal_id || "").trim();
      const tid = String(l.preview_trade_id || "").trim();
      if (!jid || !tid) return;
      journals.add(jid);
      trades.add(tid);

      const hardReasons = hardConflictByPair.get(`${jid}|${tid}`);
      if (hardReasons) {
        hardConflicts.push({ journal_id: jid, preview_trade_id: tid, reasons: hardReasons });
      }
      const locked = existingMatchByJournalId.get(jid);
      if (locked) {
        lockConflicts.push({ journal_id: jid, trade_id: locked.trade_id, trade_day: locked.trade_day });
      }
    });

    return {
      total_links: links.length,
      unique_journals: journals.size,
      unique_trades: trades.size,
      hard_conflicts: hardConflicts,
      lock_conflicts: lockConflicts,
    };
  }, [links, preview?.suggestions, existingMatchByJournalId]);

  const filteredSuggestions = useMemo(
    () =>
      (preview?.suggestions || [])
        .filter((s) => String(s["journal_id"] || "") === selectedJournalId)
        .sort((a, b) => {
          const ta = Number(a["tier"] || 9);
          const tb = Number(b["tier"] || 9);
          if (ta !== tb) return ta - tb;
          return Number(b["score"] || 0) - Number(a["score"] || 0);
        }),
    [preview?.suggestions, selectedJournalId]
  );

  async function loadRelinkPreview(options?: { silent?: boolean }) {
    const silent = Boolean(options?.silent);
    setLoadingRelinkPreview(true);
    if (!silent) setMessage("");
    try {
      const resp = await getMatchingRelinkPreview({ start: linkStart, end: linkEnd });
      setPreview(resp);
      setLinks([]);
      setSelectedJournalId("");
      setDragJournalId("");
      if (!silent) {
        setMessage(`Relink workspace loaded. Trades: ${resp.parsed_trades.length}. Journals: ${resp.journal_rows.length}.`);
      }
    } catch (e) {
      if (!silent) setMessage(`Relink preview failed: ${(e as Error).message}`);
      else throw e;
    } finally {
      setLoadingRelinkPreview(false);
    }
  }

  function assignJournalToTrade(journalId: string, tradeId: string, extra?: Partial<LinkRow>) {
    if (!journalId || !tradeId) return;
    const locked = existingMatchByJournalId.get(String(journalId));
    if (locked) {
      const at = locked.trade_day ? ` on ${locked.trade_day}` : "";
      const tid = locked.trade_id ? ` (trade ${locked.trade_id})` : "";
      setMessage(`Journal ${journalId} is already assigned${at}${tid}. To reassign, go to that trade day, unlink it there first, then return here.`);
      return;
    }
    setLinks((prev) => {
      const next = prev.filter((x) => String(x.journal_id) !== String(journalId));
      next.push({
        journal_id: journalId,
        preview_trade_id: tradeId,
        score: extra?.score,
        match_type: extra?.match_type || "manual",
        is_primary: true,
      });
      return next;
    });
  }

  function unassignJournal(journalId: string) {
    setLinks((prev) => prev.filter((x) => String(x.journal_id) !== String(journalId)));
  }

  async function commitAll() {
    if (!preview) return;
    if (!preview.can_continue) {
      setMessage("Step 1 is blocked. Load a date range with available trades.");
      return;
    }
    if (!links.length) {
      setMessage("Step 3 is blocked. Create at least one journal-trade link in Step 2.");
      return;
    }
    if (linkCommitSummary.hard_conflicts.length > 0) {
      setMessage(`Step 3 is blocked. ${linkCommitSummary.hard_conflicts.length} hard-conflict link(s) must be resolved before commit.`);
      return;
    }
    if (linkCommitSummary.lock_conflicts.length > 0) {
      setMessage(`Step 3 is blocked. ${linkCommitSummary.lock_conflicts.length} locked link(s) still exist. Unlink them first.`);
      return;
    }
    const ok = window.confirm(
      `Persist ${linkCommitSummary.total_links} link(s)?\n` +
      `Unique journals: ${linkCommitSummary.unique_journals}\n` +
      `Target trades: ${linkCommitSummary.unique_trades}\n\n` +
      "This will write match links and may inactivate previous links for the same journal."
    );
    if (!ok) {
      setMessage("Persist canceled.");
      return;
    }
    setBusyCommit(true);
    setMessage("");
    try {
      const resp = await postMatchingCommit({
        parsed_trades: preview.parsed_trades,
        links,
        replace_for_journal: true,
      });
      setLinks([]);
      setSelectedJournalId("");
      setDragJournalId("");
      try {
        await loadRelinkPreview({ silent: true });
        setMessage(`Matches persisted. Inserted: ${resp.matches_inserted}, inactivated: ${resp.matches_inactivated}. Workspace refreshed.`);
      } catch (refreshErr) {
        setMessage(`Matches persisted. Inserted: ${resp.matches_inserted}, inactivated: ${resp.matches_inactivated}. Refresh failed: ${(refreshErr as Error).message}`);
      }
    } catch (e) {
      setMessage(`Commit failed: ${(e as Error).message}`);
    } finally {
      setBusyCommit(false);
    }
  }

  async function unlinkLockedJournal(row: LiveJournalRow) {
    const journalId = String(row.journal_id || "").trim();
    const matches = Array.isArray(row.matches) ? row.matches : [];
    const active = (matches.find((m) => String((m as Record<string, unknown>)["Status"] || "").trim().toLowerCase() === "active") ||
      matches[0] ||
      {}) as Record<string, unknown>;
    const tradeId = String(active["trade_id"] || "").trim();
    const day = String(active["TradeDay"] || row.TradeDay || "").trim();
    if (!journalId) return;
    const key = `${journalId}|${tradeId}|${day}`;
    setUnlinkingKey(key);
    setMessage("");
    try {
      const resp = await postMatchingUnlink({ journal_id: journalId, trade_id: tradeId, trade_day: day });
      if (resp.inactivated > 0) {
        setMessage(`Unlinked: ${resp.inactivated}`);
        setPreview((prev) => {
          if (!prev) return prev;
          const nextRows = (prev.journal_rows || []).map((j) => {
            if (String(j.journal_id || "") !== journalId) return j;
            return { ...j, matches: [], MatchStatus: "unmatched" };
          });
          return { ...prev, journal_rows: nextRows };
        });
      } else {
        setMessage("Unlinked: 0. No active link was removed; reload workspace to verify current state.");
      }
    } catch (e) {
      setMessage(`Unlink failed: ${(e as Error).message}`);
    } finally {
      setUnlinkingKey("");
    }
  }

  async function reconfirmLockedJournal(row: LiveJournalRow) {
    const journalId = String(row.journal_id || "").trim();
    const matches = Array.isArray(row.matches) ? row.matches : [];
    const active = (matches.find((m) => String((m as Record<string, unknown>)["Status"] || "").trim().toLowerCase() === "active") ||
      matches[0] ||
      {}) as Record<string, unknown>;
    const tradeId = String(active["trade_id"] || "").trim();
    const day = String(active["TradeDay"] || row.TradeDay || "").trim();
    if (!journalId) return;
    const key = `${journalId}|${tradeId}|${day}`;
    setReconfirmingKey(key);
    setMessage("");
    try {
      const resp = await postMatchingReconfirm({ journal_id: journalId, trade_id: tradeId, trade_day: day });
      setMessage(`Reconfirmed: ${resp.updated}`);
      setPreview((prev) => {
        if (!prev) return prev;
        const nextRows = (prev.journal_rows || []).map((j) => {
          if (String(j.journal_id || "") !== journalId) return j;
          return { ...j, MatchStatus: "matched" };
        });
        return { ...prev, journal_rows: nextRows };
      });
    } catch (e) {
      setMessage(`Reconfirm failed: ${(e as Error).message}`);
    } finally {
      setReconfirmingKey("");
    }
  }

  return (
    <AppShell active="/matching">
      <Card title="Step 1: Load Match Workspace">
        <div className="space-y-3">
          <p className="text-xs text-slate-400">
            Source of truth is existing `Performance_sum`. Load trades + journals by date range, then link/unlink.
          </p>
          <div className="grid gap-2 md:grid-cols-4">
            <label className="text-xs text-slate-300">
              Start
              <input type="date" value={linkStart} onChange={(e) => setLinkStart(e.target.value)} className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white" />
            </label>
            <label className="text-xs text-slate-300">
              End
              <input type="date" value={linkEnd} onChange={(e) => setLinkEnd(e.target.value)} className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white" />
            </label>
            <div className="md:col-span-2 flex items-end">
              <button
                onClick={() => {
                  void loadRelinkPreview();
                }}
                disabled={loadingRelinkPreview}
                className="rounded border border-cyan-300/40 px-3 py-2 text-xs text-cyan-200 disabled:opacity-60"
              >
                {loadingRelinkPreview ? "Loading..." : "Load Workspace"}
              </button>
            </div>
          </div>

          {preview ? (
            <div className="space-y-2 rounded border border-white/10 bg-white/5 p-3 text-xs">
              <p>
                Trades: <span className="text-white">{preview.parsed_trades.length}</span> | Journals: <span className="text-white">{preview.journal_rows.length}</span> | Range:{" "}
                <span className="text-white">{preview.parsed_range.start || "-"} → {preview.parsed_range.end || "-"}</span>
              </p>
              <p>
                Status: <span className={preview.can_continue ? "text-emerald-300" : "text-red-300"}>{preview.can_continue ? "Ready for matching" : "No trades in range"}</span>
              </p>
            </div>
          ) : null}
        </div>
      </Card>

      <Card title="Step 2: Truth-Board Matching">
        <p className="mb-3 text-xs text-slate-400">
          Truth side is persisted performance trades (right). Journal pool is left. Drag journal cards onto a truth trade card to assign. Remove sends them back to pool.
        </p>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.12em] text-slate-400">Journal Pool ({poolJournals.length})</p>
            <div
              onDragOver={(e) => {
                if (dragJournalId) e.preventDefault();
              }}
              onDrop={(e) => {
                if (!dragJournalId) return;
                e.preventDefault();
                unassignJournal(dragJournalId);
                setDragJournalId("");
              }}
              className="min-h-[420px] space-y-2 rounded border border-dashed border-white/20 p-2"
            >
              {poolJournals.map((r) => {
                const jid = String(r.journal_id || "");
                const selected = selectedJournalId === jid;
                const locked = existingMatchByJournalId.get(jid);
                const key = `${jid}|${locked?.trade_id || ""}|${locked?.trade_day || ""}`;
                const status = String(r.MatchStatus || "").trim().toLowerCase();
                const adj = Array.isArray(r.adjustments) ? r.adjustments : [];
                return (
                  <div key={jid} className="space-y-1">
                    <button
                      onClick={() => setSelectedJournalId(jid)}
                      draggable={!locked}
                      onDragStart={() => {
                        if (!locked) setDragJournalId(jid);
                      }}
                      onDragEnd={() => setDragJournalId("")}
                      className={`w-full rounded border p-3 text-left text-xs ${selected ? "border-accent bg-accent/10" : "border-white/10 bg-white/5"}`}
                    >
                      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                        <span>Day {showValue(r.TradeDay)}</span>
                        <span>Seq {showValue(r.SeqInDay)}</span>
                        <span>{showValue(r.Direction)}</span>
                        <span>Size {showValue(r.Size)}</span>
                      </div>
                      <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
                        <span>Contract {showValue(r.ContractName)}</span>
                        <span>Intent {showValue(r.TradeIntent)}</span>
                        <span>Phase {showValue(r.Phase)}</span>
                        <span>Context {showValue(r.Context)}</span>
                        <span>Setup {showValue(r.Setup)}</span>
                        <span>Signal {showValue(r.SignalBar)}</span>
                        <span>Max Loss ${showValue(r.MaxLossUSD)}</span>
                        <span>Status {showValue(r.MatchStatus)}</span>
                      </div>
                      <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
                        <span>Entry Px {showValue(r.EntryPrice)}</span>
                        <span>TP Px {showValue(r.TakeProfitPrice)}</span>
                        <span>SL Px {showValue(r.StopLossPrice)}</span>
                        <span>Exit Px {showValue(r.ExitPrice)}</span>
                        <span>Entered {showValue(r.EnteredAt)}</span>
                        <span>Exited {showValue(r.ExitedAt)}</span>
                        <span>Exp Risk ${showValue(r.PotentialRiskUSD)}</span>
                        <span>Exp Reward ${showValue(r.PotentialRewardUSD)}</span>
                      </div>
                      <div className="mt-1 grid grid-cols-2 gap-2 md:grid-cols-4">
                        <span>Expected R:R {showValue(r.WinLossRatio)}</span>
                        <span>Rule {showValue(r.RuleStatus)}</span>
                        <span className="md:col-span-2">Notes {showValue(r.Notes)}</span>
                      </div>
                      <div className="mt-2 rounded border border-white/10 bg-surface/40 p-2">
                        <p className="mb-1 text-[10px] uppercase tracking-[0.1em] text-slate-400">Execution Detail Rows</p>
                        <div className="space-y-1">
                          {adj.map((a, i) => (
                            <div key={String(a.adjustment_id || i)} className="grid grid-cols-2 gap-2 text-[11px] text-slate-300 md:grid-cols-5">
                              <span>Leg {showValue(a.LegIndex)}</span>
                              <span>Qty {showValue(a.Qty)}</span>
                              <span>Entry {showValue(a.EntryPrice)}</span>
                              <span>TP {showValue(a.TakeProfitPrice)}</span>
                              <span>SL {showValue(a.StopLossPrice)}</span>
                              <span>Exit {showValue(a.ExitPrice)}</span>
                              <span>Entered {showValue(a.EnteredAt)}</span>
                              <span>Exited {showValue(a.ExitedAt)}</span>
                              <span>Exp Risk ${showValue(a.RiskUSD)}</span>
                              <span>Exp Reward ${showValue(a.RewardUSD)}</span>
                            </div>
                          ))}
                          {!adj.length ? <p className="text-[11px] text-slate-500">No execution detail rows.</p> : null}
                        </div>
                      </div>
                      {locked ? (
                        <div className="mt-1 text-[11px] text-amber-300">
                          Locked: linked {locked.trade_day ? `on ${locked.trade_day}` : ""} {locked.trade_id ? `to ${locked.trade_id}` : ""}
                        </div>
                      ) : null}
                    </button>
                    {locked ? (
                      <div className="flex items-center gap-1 pl-1">
                        <button
                          onClick={() => reconfirmLockedJournal(r)}
                          disabled={reconfirmingKey === key || status !== "needs_reconfirm"}
                          className="rounded border border-emerald-300/40 px-2 py-1 text-[11px] text-emerald-200 disabled:opacity-60"
                        >
                          {reconfirmingKey === key ? "Reconfirming..." : "Reconfirm"}
                        </button>
                        <button
                          onClick={() => unlinkLockedJournal(r)}
                          disabled={unlinkingKey === key}
                          className="rounded border border-red-300/40 px-2 py-1 text-[11px] text-red-200 disabled:opacity-60"
                        >
                          {unlinkingKey === key ? "Unlinking..." : "Unlink"}
                        </button>
                      </div>
                    ) : null}
                  </div>
                );
              })}
              {!poolJournals.length ? <p className="text-xs text-slate-500">Pool is empty.</p> : null}
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.12em] text-slate-400">Parsed Trades Truth Board ({parsedTrades.length})</p>
            <div className="max-h-[420px] space-y-2 overflow-auto pr-1">
              {parsedTrades.map((r, idx) => {
                const tid = String(r["preview_trade_id"] || r["trade_id"] || `row-${idx}`);
                const assigned = linksByTrade.get(tid) || [];
                return (
                  <div
                    key={tid}
                    onDragOver={(e) => {
                      if (dragJournalId) e.preventDefault();
                    }}
                    onDrop={(e) => {
                      if (!dragJournalId) return;
                      e.preventDefault();
                      assignJournalToTrade(dragJournalId, tid, { match_type: "manual", is_primary: true });
                      setDragJournalId("");
                    }}
                    className="rounded border border-white/10 bg-white/5 p-3 text-xs"
                  >
                    <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
                      <span>{String(r["TradeDay"] || "")}</span>
                      <span>{String(r["Type"] || "")}</span>
                      <span>Size {String(r["Size"] || "")}</span>
                      <span>Entry {String(r["EntryPrice"] || "")}</span>
                      <span>Exit {String(r["ExitPrice"] || "")}</span>
                    </div>
                    <div className="mt-1 font-mono text-[11px] text-slate-400">{tid}</div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {assigned.length ? (
                        assigned.map((l) => {
                          const jid = String(l.journal_id || "");
                          const j = journalById.get(jid);
                          return (
                            <div
                              key={`${tid}-${jid}`}
                              draggable
                              onDragStart={() => setDragJournalId(jid)}
                              onDragEnd={() => setDragJournalId("")}
                              className="inline-flex items-center gap-1 rounded-full border border-accent/40 bg-accent/10 px-2 py-0.5 text-[11px] text-accent"
                            >
                              <span>{jid}</span>
                              <span className="text-slate-300">Seq {String(j?.SeqInDay || "")}</span>
                              <button onClick={() => unassignJournal(jid)} className="rounded border border-red-300/40 px-1 text-[10px] text-red-200">
                                x
                              </button>
                            </div>
                          );
                        })
                      ) : (
                        <span className="text-[11px] text-slate-500">Drop journal here to assign</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {selectedJournalId ? (
          <div className="mt-3 rounded border border-white/10 bg-white/5 p-3">
            <p className="mb-2 text-xs uppercase tracking-[0.12em] text-slate-400">Recommendations for {selectedJournalId}</p>
            <div className="space-y-1 text-xs text-slate-200">
              {filteredSuggestions.length ? (
                filteredSuggestions.map((s, i) => {
                  const tid = String(s["preview_trade_id"] || "");
                  const tier = Number(s["tier"] || 3);
                  const recommended = Boolean(s["recommended"]);
                  const hardConflict = Boolean(s["hard_conflict"]);
                  const reasons = Array.isArray(s["reasons"]) ? s["reasons"] : [];
                  return (
                    <button
                      key={`${tid}-${i}`}
                      onClick={() =>
                        assignJournalToTrade(selectedJournalId, tid, {
                          score: Number(s["score"] || 0),
                          match_type: String(s["match_type"] || "heuristic"),
                          is_primary: true,
                        })
                      }
                      className={`block w-full rounded border px-2 py-1 text-left hover:border-accent/40 ${
                        recommended ? "border-emerald-300/40 bg-emerald-500/10" : "border-white/10 bg-surface"
                      }`}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-[11px]">{tid}</span>
                        <span className="rounded border border-white/20 px-1 py-0.5 text-[10px]">Tier {tier}</span>
                        {recommended ? <span className="rounded border border-emerald-300/40 px-1 py-0.5 text-[10px] text-emerald-200">Recommended</span> : null}
                        {hardConflict ? <span className="rounded border border-red-300/40 px-1 py-0.5 text-[10px] text-red-200">Hard conflict</span> : null}
                        <span className="text-[10px] text-slate-300">score {String(s["score"] || "")}</span>
                      </div>
                      <div className="mt-1 text-[10px] text-slate-400">{reasons.join(" | ")}</div>
                    </button>
                  );
                })
              ) : (
                <p className="text-slate-400">No recommendations.</p>
              )}
            </div>
          </div>
        ) : null}
      </Card>

      <Card title="Step 3: Persist Matches">
        <div className="space-y-2 text-xs text-slate-300">
          <p>Commit mode: <span className="text-white">link-only (no performance merge)</span></p>
          <p>Parsed trades to commit: <span className="text-white">{parsedTrades.length}</span></p>
          <p>Match links to persist: <span className="text-white">{links.length}</span></p>
          <div className="rounded border border-white/10 bg-white/5 p-2 text-[11px]">
            <p>Link summary: total {linkCommitSummary.total_links} | unique journals {linkCommitSummary.unique_journals} | target trades {linkCommitSummary.unique_trades}</p>
            <p className={linkCommitSummary.hard_conflicts.length > 0 ? "text-red-300" : "text-emerald-300"}>
              Hard conflicts: {linkCommitSummary.hard_conflicts.length}
            </p>
            <p className={linkCommitSummary.lock_conflicts.length > 0 ? "text-red-300" : "text-emerald-300"}>
              Locked conflicts: {linkCommitSummary.lock_conflicts.length}
            </p>
            {linkCommitSummary.hard_conflicts.length > 0 ? (
              <div className="mt-1 max-h-24 overflow-auto text-[10px] text-red-200">
                {linkCommitSummary.hard_conflicts.slice(0, 12).map((c, idx) => (
                  <p key={`${c.journal_id}|${c.preview_trade_id}|${idx}`}>
                    {c.journal_id} {"->"} {c.preview_trade_id}: {c.reasons.join(" | ")}
                  </p>
                ))}
              </div>
            ) : null}
          </div>
          <p>
            Gate:{" "}
            <span className={(preview?.can_continue ?? false) ? "text-emerald-300" : "text-red-300"}>
              {(preview?.can_continue ?? false) ? "open" : "blocked (no trades loaded)"}
            </span>
          </p>
          <button
            onClick={commitAll}
            disabled={busyCommit || !(preview?.can_continue ?? false) || links.length === 0}
            className="rounded bg-accent px-4 py-2 text-sm text-white disabled:opacity-60"
          >
            {busyCommit ? "Persisting..." : "Persist Match Links"}
          </button>
        </div>
      </Card>

      <p className="text-xs text-slate-400">{message}</p>
    </AppShell>
  );
}
