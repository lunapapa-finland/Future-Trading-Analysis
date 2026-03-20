"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { postTradeUploadCommit, postTradeUploadParsePreview } from "@/lib/api";
import { useMemo, useState } from "react";

type ParsePreview = {
  can_continue: boolean;
  hard_blocked: boolean;
  parse_logs: Array<Record<string, unknown>>;
  unparseable_rows: Array<Record<string, unknown>>;
  parsed_trades: Array<Record<string, unknown>>;
  parsed_range: { start: string; end: string; days: string[] };
};

export default function UploadPage() {
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [archiveRaw, setArchiveRaw] = useState(false);
  const [busyParse, setBusyParse] = useState(false);
  const [busyCommit, setBusyCommit] = useState(false);
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<ParsePreview | null>(null);

  const parsedTrades = useMemo(() => preview?.parsed_trades || [], [preview?.parsed_trades]);

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
      setMessage(`Parsed trades: ${resp.parsed_trades.length}. Unparseable rows: ${resp.unparseable_rows.length}.`);
      setUploadFiles([]);
    } catch (e) {
      setMessage(`Parse preview failed: ${(e as Error).message}`);
    } finally {
      setBusyParse(false);
    }
  }

  async function commitMerge() {
    if (!preview) {
      setMessage("Run parse preview first.");
      return;
    }
    if (preview.hard_blocked || !preview.can_continue) {
      setMessage("Commit blocked. Fix parse errors first.");
      return;
    }
    if (!preview.parsed_trades.length) {
      setMessage("Commit blocked. No parsed trades.");
      return;
    }
    setBusyCommit(true);
    setMessage("");
    try {
      const resp = await postTradeUploadCommit({
        parsed_trades: preview.parsed_trades,
      });
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
          <p className="text-xs text-slate-400">Upload raw CSVs and parse round-trip trades. No persistence in this step.</p>
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
                Commit gate: <span className={preview.can_continue ? "text-emerald-300" : "text-red-300"}>{preview.can_continue ? "open" : "blocked"}</span>
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

      <Card title="Step 2: Commit Merge to Performance">
        <div className="space-y-2 text-xs text-slate-300">
          <p>Parsed trades ready: <span className="text-white">{parsedTrades.length}</span></p>
          <p>Rule: commit is disallowed when parse preview has any unparseable rows.</p>
          <button
            onClick={commitMerge}
            disabled={busyCommit || !(preview?.can_continue ?? false) || parsedTrades.length === 0}
            className="rounded bg-accent px-4 py-2 text-sm text-white disabled:opacity-60"
          >
            {busyCommit ? "Committing..." : "Commit Parsed Trades"}
          </button>
        </div>
      </Card>

      <Card title="Parsed Trades Board">
        <div className="space-y-2">
          <p className="text-xs text-slate-400">Preview of parsed round-trip trades before commit.</p>
          <div className="max-h-[440px] space-y-2 overflow-auto pr-1">
            {parsedTrades.map((r, idx) => {
              const tradeId = String(r["preview_trade_id"] || r["trade_id"] || `row-${idx}`);
              return (
                <div key={tradeId} className="rounded border border-white/10 bg-white/5 p-3 text-xs text-slate-200">
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
                    <span>{String(r["TradeDay"] || "-")}</span>
                    <span>{String(r["ContractName"] || "-")}</span>
                    <span>{String(r["Type"] || "-")}</span>
                    <span>Size {String(r["Size"] || "-")}</span>
                    <span>Entry {String(r["EntryPrice"] || "-")}</span>
                    <span>Exit {String(r["ExitPrice"] || "-")}</span>
                  </div>
                  <div className="mt-1 font-mono text-[11px] text-slate-400">{tradeId}</div>
                </div>
              );
            })}
            {!parsedTrades.length ? <p className="text-xs text-slate-500">No parsed trades to display.</p> : null}
          </div>
        </div>
      </Card>

      <p className="text-xs text-slate-400">{message}</p>
    </AppShell>
  );
}
