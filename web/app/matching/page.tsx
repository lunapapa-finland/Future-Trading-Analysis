"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { getMatchingLinks, postMatchingCommit, postMatchingParsePreview, postMatchingUnlink } from "@/lib/api";
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

export default function MatchingPage() {
  const now = new Date();
  const thisDay = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [archiveRaw, setArchiveRaw] = useState(false);
  const [busyParse, setBusyParse] = useState(false);
  const [busyCommit, setBusyCommit] = useState(false);
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<ParsePreview | null>(null);
  const [selectedJournalId, setSelectedJournalId] = useState("");
  const [dragJournalId, setDragJournalId] = useState("");
  const [links, setLinks] = useState<LinkRow[]>([]);
  const [linkStart, setLinkStart] = useState(thisDay);
  const [linkEnd, setLinkEnd] = useState(thisDay);
  const [loadingLinks, setLoadingLinks] = useState(false);
  const [unlinkingKey, setUnlinkingKey] = useState("");
  const [activeLinks, setActiveLinks] = useState<Array<Record<string, unknown>>>([]);

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

  async function runParsePreview() {
    if (!uploadFiles.length) {
      setMessage("Select at least one CSV file.");
      return;
    }
    setBusyParse(true);
    setMessage("");
    try {
      const resp = await postMatchingParsePreview(uploadFiles, { archiveRaw });
      setPreview(resp);
      setLinks([]);
      setSelectedJournalId("");
      setDragJournalId("");
      setMessage(`Parsed trades: ${resp.parsed_trades.length}. Unparseable rows: ${resp.unparseable_rows.length}.`);
      setUploadFiles([]);
    } catch (e) {
      setMessage(`Parse preview failed: ${(e as Error).message}`);
    } finally {
      setBusyParse(false);
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
    if (preview.hard_blocked || !preview.can_continue) {
      setMessage("Step 1 is blocked. Fix raw data first.");
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
      setMessage(`Committed. Performance rows delta: ${resp.rows_delta}. Matches inserted: ${resp.matches_inserted}, inactivated: ${resp.matches_inactivated}.`);
    } catch (e) {
      setMessage(`Commit failed: ${(e as Error).message}`);
    } finally {
      setBusyCommit(false);
    }
  }

  async function loadActiveLinks() {
    setLoadingLinks(true);
    setMessage("");
    try {
      const resp = await getMatchingLinks({ start: linkStart, end: linkEnd });
      setActiveLinks(resp.rows || []);
      setMessage(`Loaded active links: ${(resp.rows || []).length}`);
    } catch (e) {
      setMessage(`Load links failed: ${(e as Error).message}`);
    } finally {
      setLoadingLinks(false);
    }
  }

  async function unlinkOne(row: Record<string, unknown>) {
    const journalId = String(row["journal_id"] || "");
    const tradeId = String(row["trade_id"] || "");
    const day = String(row["TradeDay"] || "");
    if (!journalId) return;
    const key = `${journalId}|${tradeId}|${day}`;
    setUnlinkingKey(key);
    setMessage("");
    try {
      const resp = await postMatchingUnlink({ journal_id: journalId, trade_id: tradeId, trade_day: day });
      setMessage(`Unlinked: ${resp.inactivated}`);
      setActiveLinks((prev) => prev.filter((x) => !(String(x["journal_id"] || "") === journalId && String(x["trade_id"] || "") === tradeId && String(x["TradeDay"] || "") === day)));
      setPreview((prev) => {
        if (!prev) return prev;
        const nextRows = (prev.journal_rows || []).map((j) => {
          if (String(j.journal_id || "") !== journalId) return j;
          const matches = Array.isArray((j as any).matches) ? ((j as any).matches as Array<Record<string, unknown>>) : [];
          const kept = matches.filter((m) => !(String(m["trade_id"] || "") === tradeId && String(m["TradeDay"] || "") === day && String(m["Status"] || "").toLowerCase() === "active"));
          return { ...j, matches: kept };
        });
        return { ...prev, journal_rows: nextRows };
      });
    } catch (e) {
      setMessage(`Unlink failed: ${(e as Error).message}`);
    } finally {
      setUnlinkingKey("");
    }
  }

  return (
    <AppShell active="/matching">
      <Card title="Step 1: Upload and Parse Preview">
        <div className="space-y-3">
          <p className="text-xs text-slate-400">
            Parse only. No persistence in this step. Continuation is blocked if any raw row is unparseable.
          </p>
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
                Parsed trades: <span className="text-white">{preview.parsed_trades.length}</span> | Range:{" "}
                <span className="text-white">{preview.parsed_range.start || "-"} → {preview.parsed_range.end || "-"}</span>
              </p>
              <p>
                Status:{" "}
                <span className={preview.can_continue ? "text-emerald-300" : "text-red-300"}>{preview.can_continue ? "Ready for Step 2/3" : "Blocked"}</span>
              </p>
            </div>
          ) : null}

          {preview?.parse_logs?.length ? (
            <div className="rounded border border-white/10 bg-white/5 p-3">
              <p className="mb-2 text-xs uppercase tracking-[0.12em] text-slate-400">Parse Logs</p>
              <div className="space-y-1 text-xs text-slate-200">
                {preview.parse_logs.map((r, i) => (
                  <div key={i} className="rounded border border-white/10 bg-surface px-2 py-1">
                    {JSON.stringify(r)}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {preview?.unparseable_rows?.length ? (
            <div className="rounded border border-red-400/30 bg-red-500/10 p-3">
              <p className="mb-2 text-xs uppercase tracking-[0.12em] text-red-300">Unparseable Rows (Hard Block)</p>
              <div className="max-h-56 space-y-1 overflow-auto text-xs text-red-100">
                {preview.unparseable_rows.map((r, i) => (
                  <div key={i} className="rounded border border-red-300/30 px-2 py-1">
                    {JSON.stringify(r)}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </Card>

      <Card title="Step 2: Truth-Board Matching">
        <p className="mb-3 text-xs text-slate-400">
          Truth side is parsed trades (right). Journal pool is left. Drag journal cards onto a truth trade card to assign. Remove sends them back to pool.
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
                return (
                  <button
                    key={jid}
                    onClick={() => setSelectedJournalId(jid)}
                    draggable={!locked}
                    onDragStart={() => {
                      if (!locked) setDragJournalId(jid);
                    }}
                    onDragEnd={() => setDragJournalId("")}
                    className={`w-full rounded border p-3 text-left text-xs ${selected ? "border-accent bg-accent/10" : "border-white/10 bg-white/5"}`}
                  >
                    <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                      <span>{String(r.TradeDay || "")}</span>
                      <span>Seq {String(r.SeqInDay || "")}</span>
                      <span>{String(r.Direction || "")}</span>
                      <span>Size {String(r.Size || "")}</span>
                    </div>
                    <div className="mt-1 text-slate-300">Setup: {String(r.Setup || "")}</div>
                    {locked ? (
                      <div className="mt-1 text-[11px] text-amber-300">
                        Locked: linked {locked.trade_day ? `on ${locked.trade_day}` : ""} {locked.trade_id ? `to ${locked.trade_id}` : ""}
                      </div>
                    ) : null}
                  </button>
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

      <Card title="Link Manager (No Upload Needed)">
        <p className="mb-3 text-xs text-slate-400">
          Load existing active journal-trade links by date range, then unlink directly here.
        </p>
        <div className="mb-3 grid gap-2 md:grid-cols-4">
          <label className="text-xs text-slate-300">
            Start
            <input type="date" value={linkStart} onChange={(e) => setLinkStart(e.target.value)} className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white" />
          </label>
          <label className="text-xs text-slate-300">
            End
            <input type="date" value={linkEnd} onChange={(e) => setLinkEnd(e.target.value)} className="mt-1 h-9 w-full rounded border border-white/10 bg-surface px-2 text-white" />
          </label>
          <div className="md:col-span-2 flex items-end">
            <button onClick={loadActiveLinks} disabled={loadingLinks} className="rounded border border-amber-300/40 px-3 py-2 text-xs text-amber-200 disabled:opacity-60">
              {loadingLinks ? "Loading..." : "Load Active Links"}
            </button>
          </div>
        </div>
        <div className="space-y-2">
          {activeLinks.map((r, i) => {
            const journal = (r["journal"] as Record<string, unknown>) || {};
            const trade = (r["trade"] as Record<string, unknown>) || {};
            const journalId = String(r["journal_id"] || "");
            const tradeId = String(r["trade_id"] || "");
            const day = String(r["TradeDay"] || "");
            const key = `${journalId}|${tradeId}|${day}`;
            return (
              <div key={`${key}|${i}`} className="rounded border border-white/10 bg-white/5 p-3 text-xs">
                <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
                  <span>{day}</span>
                  <span>{journalId}</span>
                  <span>{tradeId}</span>
                  <span>{String(journal["Direction"] || "")} / {String(journal["Size"] || "")}</span>
                  <span>{String(trade["Type"] || "")} / {String(trade["Size"] || "")}</span>
                  <button
                    onClick={() => unlinkOne(r)}
                    disabled={unlinkingKey === key}
                    className="rounded border border-red-300/40 px-2 py-1 text-[11px] text-red-200 disabled:opacity-60"
                  >
                    {unlinkingKey === key ? "Unlinking..." : "Unlink"}
                  </button>
                </div>
              </div>
            );
          })}
          {!activeLinks.length ? <p className="text-xs text-slate-500">No loaded links.</p> : null}
        </div>
      </Card>

      <Card title="Step 3: Commit to Performance and Persist Matches">
        <div className="space-y-2 text-xs text-slate-300">
          <p>Parsed trades to commit: <span className="text-white">{parsedTrades.length}</span></p>
          <p>Match links to persist: <span className="text-white">{links.length}</span></p>
          <p>
            Gate:{" "}
            <span className={(preview?.can_continue ?? false) ? "text-emerald-300" : "text-red-300"}>
              {(preview?.can_continue ?? false) ? "open" : "blocked (fix Step 1 raw data)"}
            </span>
          </p>
          <button
            onClick={commitAll}
            disabled={busyCommit || !(preview?.can_continue ?? false)}
            className="rounded bg-accent px-4 py-2 text-sm text-white disabled:opacity-60"
          >
            {busyCommit ? "Committing..." : "Commit Parsed Trades + Matches"}
          </button>
        </div>
      </Card>

      <p className="text-xs text-slate-400">{message}</p>
    </AppShell>
  );
}
