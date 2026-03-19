"use client";

import { useMemo, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { getDayPlanTaxonomy, getTagTaxonomy } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";

const workflow = [
  {
    step: "Step 1",
    title: "Before Placing an Order",
    details:
      "Build static bias first: review weekly analysis, last 5-10 days HTF/RTH structure, HLOC S/R, and 0-DTE OI/volume walls.",
  },
  {
    step: "Step 2",
    title: "Double Confirm",
    details:
      "Entry must pass Phase + Context + Setup + Signal Bar. No early entries before signal-bar quality is clear.",
  },
  {
    step: "Step 3",
    title: "Risk Management",
    details:
      "Pre-define trade type (scalp/swing), stop logic, and size. Do not improvise risk after entry.",
  },
  {
    step: "Step 4",
    title: "Trade Management",
    details:
      "Continuously re-evaluate time decay, opposite-side quality, and TP/SL adaptation using current context.",
  },
];

const beforeSession = [
  "Set Bias and expected Day Type.",
  "Write key levels and primary plan.",
];

const afterSession = [
  "Confirm actual Day Type.",
  "Adjust notes and finalize daily summary.",
];

const entryRules = [
  "Basic check must be explicit: Phase + Context + Setup(s) + Signal Bar.",
  "2nd entry means BO + retest + quality signal bar; do not trail too early before HL/LH confirmation.",
  "Trade with trend by default; avoid anti-trend unless major S/R and multi-setup confluence exist.",
  "If opposite side looks easier/stronger, reduce aggression or avoid entry.",
];

const managementRules = [
  "Time decay discipline: if expectation fails to materialize, decide exit faster (6-bar, 10-bar two-leg, 20-bar references).",
  "If scaled in, prioritize break-even / first-entry exit rather than hope-based hold.",
  "Scalp mode: no adding, no unnecessary risk expansion, pre-defined TP execution.",
  "Swing mode: monitor trend quality, stair/gap behavior, and opposite-side setup strength continuously.",
];

export default function GuidePage() {
  const [activeStep, setActiveStep] = useState(0);
  const [disciplinedMaxLoss, setDisciplinedMaxLoss] = useState(200);
  const [pricePerTick, setPricePerTick] = useState(1.25);
  const [ticksPerPoint, setTicksPerPoint] = useState(4);
  const [entryPrice, setEntryPrice] = useState(6000);
  const [size, setSize] = useState(1);
  const [tpPrice, setTpPrice] = useState(6010);
  const [stopPrice, setStopPrice] = useState(5990);
  const { data: taxonomy } = useQuery({
    queryKey: ["tag-taxonomy"],
    queryFn: () => getTagTaxonomy(),
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
  });
  const { data: dayPlanTaxonomy } = useQuery({
    queryKey: ["day-plan-taxonomy"],
    queryFn: () => getDayPlanTaxonomy(),
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
  });
  const activeMeta = workflow[activeStep];
  const phaseItems = useMemo(() => {
    const fromApi = (taxonomy?.phase ?? []).map((x) => ({ text: x.value, hint: x.hint || "" }));
    return fromApi;
  }, [taxonomy?.phase]);
  const contextItems = useMemo(() => {
    const fromApi = (taxonomy?.context ?? []).map((x) => ({ text: x.value, hint: x.hint || "" }));
    return fromApi;
  }, [taxonomy?.context]);
  const setupItems = useMemo(() => {
    const fromApi = (taxonomy?.setup ?? []).map((x) => ({ text: x.value, hint: x.hint || "" }));
    return fromApi;
  }, [taxonomy?.setup]);
  const signalItems = useMemo(() => {
    const fromApi = (taxonomy?.signal_bar ?? []).map((x) => ({ text: x.value, hint: x.hint || "" }));
    return fromApi;
  }, [taxonomy?.signal_bar]);
  const tradeIntentItems = useMemo(() => {
    const fromApi = (taxonomy?.trade_intent ?? []).map((x) => ({ text: x.value, hint: x.hint || "" }));
    return fromApi;
  }, [taxonomy?.trade_intent]);
  const biasItems = useMemo(() => {
    const fromApi = (dayPlanTaxonomy?.bias ?? []).map((x) => ({ text: x.value, hint: x.hint || "" }));
    return fromApi;
  }, [dayPlanTaxonomy?.bias]);
  const expectedDayTypeItems = useMemo(() => {
    const fromApi = (dayPlanTaxonomy?.expected_day_type ?? []).map((x) => ({ text: x.value, hint: x.hint || "" }));
    return fromApi;
  }, [dayPlanTaxonomy?.expected_day_type]);
  const taxonomyReady = phaseItems.length > 0 && contextItems.length > 0 && setupItems.length > 0 && signalItems.length > 0;
  const dayTaxonomyReady = biasItems.length > 0 && expectedDayTypeItems.length > 0;
  const intentTaxonomyReady = tradeIntentItems.length > 0;
  const progressPct = useMemo(() => ((activeStep + 1) / workflow.length) * 100, [activeStep]);
  const contractValuePerPoint = pricePerTick * ticksPerPoint;
  const onQuarterTick = (v: number) => Number.isFinite(v) && Math.abs(v * 4 - Math.round(v * 4)) < 1e-9;
  const riskCalc = useMemo(() => {
    if (!Number.isFinite(entryPrice) || !Number.isFinite(tpPrice) || !Number.isFinite(stopPrice)) {
      return null;
    }
    if (!onQuarterTick(entryPrice) || !onQuarterTick(tpPrice) || !onQuarterTick(stopPrice)) {
      return null;
    }
    if (
      !Number.isFinite(size) ||
      size <= 0 ||
      !Number.isFinite(disciplinedMaxLoss) ||
      disciplinedMaxLoss <= 0 ||
      !Number.isFinite(pricePerTick) ||
      pricePerTick <= 0 ||
      !Number.isFinite(ticksPerPoint) ||
      ticksPerPoint <= 0
    ) {
      return null;
    }
    if (entryPrice === stopPrice) {
      return { invalidReason: "Entry and SL cannot be equal." };
    }
    const direction: "Long" | "Short" = stopPrice < entryPrice ? "Long" : "Short";
    const validTp = direction === "Long" ? tpPrice > entryPrice : tpPrice < entryPrice;
    const validSl = direction === "Long" ? stopPrice < entryPrice : stopPrice > entryPrice;
    if (!validTp || !validSl) {
      return { invalidReason: `Invalid ${direction} setup: TP/SL are on wrong side of entry.` };
    }

    const potentialProfit = Math.abs(tpPrice - entryPrice) * size * contractValuePerPoint;
    const potentialLoss = Math.abs(entryPrice - stopPrice) * size * contractValuePerPoint;
    let verdict: "LESS" | "EQUAL" | "LARGER" = "LESS";
    const eps = 1e-9;
    if (Math.abs(potentialLoss - disciplinedMaxLoss) <= eps) {
      verdict = "EQUAL";
    } else if (potentialLoss > disciplinedMaxLoss) {
      verdict = "LARGER";
    }
    const rewardRisk = potentialLoss > 0 ? potentialProfit / potentialLoss : 0;
    return {
      direction,
      potentialProfit,
      potentialLoss,
      verdict,
      rewardRisk,
    };
  }, [contractValuePerPoint, disciplinedMaxLoss, entryPrice, pricePerTick, size, stopPrice, ticksPerPoint, tpPrice]);
  return (
    <AppShell active="/guide">
      <Card title="Guide Workflow">
        <div className="mb-4 flex flex-wrap gap-2">
          {workflow.map((step, idx) => (
            <button
              key={step.step}
              type="button"
              onClick={() => setActiveStep(idx)}
              className={`rounded-full border px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] transition sm:px-3 sm:text-xs sm:tracking-[0.12em] ${
                idx === activeStep
                  ? "border-accent bg-accent/20 text-white"
                  : "border-white/15 bg-white/5 text-slate-300 hover:border-accent/60 hover:text-white"
              }`}
            >
              {step.step}
            </button>
          ))}
        </div>
        <div className="mb-3 h-1.5 w-full rounded-full bg-white/10">
          <div className="h-1.5 rounded-full bg-accent transition-all" style={{ width: `${progressPct}%` }} />
        </div>
        <p className="text-sm font-semibold text-white">{activeMeta.title}</p>
        <p className="mt-1 text-sm text-slate-300">{activeMeta.details}</p>
      </Card>

      {activeStep === 0 ? (
        <>
          {!taxonomyReady ? (
            <Card title="Taxonomy Status">
              <p className="text-sm text-amber-300">
                Tag taxonomy is empty or not loaded from backend. Check `data/metadata/taxonomy.csv` and backend runtime config.
              </p>
            </Card>
          ) : null}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <Card title="Before and After Session">
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">
                {beforeSession.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <p className="mt-3 text-xs uppercase tracking-[0.12em] text-slate-400">After Session</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-200">
                {afterSession.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </Card>
            <Card title="Day Type Classification (Daily Sum)">
              {!dayTaxonomyReady ? (
                <p className="text-xs text-amber-300">
                  Day-plan taxonomy is empty or not loaded from backend metadata.
                </p>
              ) : (
                <div className="space-y-3">
                  <div>
                    <p className="mb-1 text-xs text-slate-400">Bias</p>
                    <HintChipGroup items={biasItems} tone="amber" hintLabel="Bias hint" />
                  </div>
                  <div>
                    <p className="mb-1 text-xs text-slate-400">Day Type (used for both expected and actual)</p>
                    <HintChipGroup items={expectedDayTypeItems} tone="emerald" hintLabel="Day-type hint" />
                  </div>
                </div>
              )}
            </Card>
            <Card title="Phase">
              <HintChipGroup items={phaseItems} tone="amber" hintLabel="Phase hint" />
            </Card>
            <Card title="Context">
              <HintChipGroup items={contextItems} tone="cyan" hintLabel="Context hint" />
            </Card>

            <Card title="Setups">
              <HintChipGroup
                items={setupItems}
                tone="emerald"
                hintLabel="Setup hint"
              />
            </Card>

            <Card title="Signal Bar">
              <HintChipGroup items={signalItems} tone="fuchsia" hintLabel="Signal hint" />
            </Card>
          </div>
        </>
      ) : null}

      {activeStep === 1 ? (
        <div className="mt-2 grid gap-4 xl:grid-cols-2">
          <Card title="Enter Reason: Probability, Risk, Reward">
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">
              <li>Basic gate: what Phase, which Context, what Setup(s), what Signal Bar.</li>
              <li>In TR, classify if it is two-leg or multi-leg structure before choosing direction.</li>
              <li>Multiple aligned setups increase quality; single weak setup lowers quality.</li>
              <li>Do not enter earlier than the confirmed signal bar.</li>
            </ul>
          </Card>
          <Card title="Advanced Confirmation">
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">
              <li>2nd entry: BO + retest + quality signal bar, or trapped-in/trapper-out shift.</li>
              <li>Unless new HL/LH forms, avoid aggressive stop movement during retest uncertainty.</li>
              <li>If BO lacks follow-through, treat it as possible TR instead of trend continuation.</li>
              <li>For sloped converging triangles, prioritize trend-side opportunities.</li>
            </ul>
          </Card>
          <Card title="Trend Bias vs Anti-Trend">
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">
              <li>Default is trend-side trading because failed counter-trend fuels trend continuation.</li>
              <li>Anti-trend is valid only at major S/R with multiple confirmations.</li>
              <li>Use close-price line trend check as a quick sanity filter.</li>
              <li>When market is dead-money sideways after sharp HTF drop, reduce participation.</li>
            </ul>
          </Card>
          <Card title="Trade Type Decision">
            {!intentTaxonomyReady ? (
              <p className="text-sm text-amber-300">TradeIntent taxonomy is empty or not loaded from backend metadata.</p>
            ) : (
              <HintChipGroup items={tradeIntentItems} tone="emerald" hintLabel="TradeIntent hint" />
            )}
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-200">
              <li>Choose TradeIntent before entry and treat it as execution discipline.</li>
              <li>Do not switch intent emotionally after entry unless structure is invalidated.</li>
            </ul>
          </Card>
        </div>
      ) : null}

      {activeStep === 2 ? (
        <div className="mt-2 grid gap-4">
          <Card title="Risk Calculator">
            <div className="grid gap-3 lg:grid-cols-2">
              <label className="flex flex-col gap-1 text-sm text-slate-300">
                Entry Price
                <input
                  type="number"
                  step={0.25}
                  value={entryPrice}
                  onChange={(e) => setEntryPrice(Number(e.target.value) || 0)}
                  className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm text-slate-300">
                Size (Contracts)
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={size}
                  onChange={(e) => setSize(Number(e.target.value) || 0)}
                  className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm text-slate-300">
                TP Price
                <input
                  type="number"
                  step={0.25}
                  value={tpPrice}
                  onChange={(e) => setTpPrice(Number(e.target.value) || 0)}
                  className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm text-slate-300">
                SL Price
                <input
                  type="number"
                  step={0.25}
                  value={stopPrice}
                  onChange={(e) => setStopPrice(Number(e.target.value) || 0)}
                  className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm text-slate-300">
                Price Per Tick ($)
                <input
                  type="number"
                  step={0.01}
                  min={0.01}
                  value={pricePerTick}
                  onChange={(e) => setPricePerTick(Number(e.target.value) || 0)}
                  className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm text-slate-300">
                Ticks Per Point
                <input
                  type="number"
                  step={1}
                  min={1}
                  value={ticksPerPoint}
                  onChange={(e) => setTicksPerPoint(Number(e.target.value) || 0)}
                  className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm text-slate-300 md:col-span-2">
                Disciplined Max Loss Per Trade ($)
                <input
                  type="number"
                  min={1}
                  value={disciplinedMaxLoss}
                  onChange={(e) => setDisciplinedMaxLoss(Number(e.target.value) || 0)}
                  className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                />
              </label>
            </div>

            <div className="mt-4 rounded-xl border border-amber-500/25 bg-amber-500/10 p-3">
              {!riskCalc ? (
                <p className="text-sm text-slate-200">
                  Enter valid numbers. Entry/TP/SL must use 0.25 increments.
                </p>
              ) : "invalidReason" in riskCalc ? (
                <p className="text-sm text-red-200">{riskCalc.invalidReason}</p>
              ) : (
                <div className="grid gap-2 text-sm text-slate-200 lg:grid-cols-2">
                  <p>
                    Price/Point: <span className="font-semibold text-white">${contractValuePerPoint.toFixed(2)}</span>
                  </p>
                  <p>
                    Direction: <span className="font-semibold text-white">{riskCalc.direction}</span>
                  </p>
                  <p>
                    Potential Profit: <span className="font-semibold text-white">${riskCalc.potentialProfit.toFixed(2)}</span>
                  </p>
                  <p>
                    Potential Loss: <span className="font-semibold text-white">${riskCalc.potentialLoss.toFixed(2)}</span>
                  </p>
                  <p>
                    Reward/Risk: <span className="font-semibold text-white">{riskCalc.rewardRisk.toFixed(2)}</span>
                  </p>
                  <p>
                    Loss vs Disciplined Max ({disciplinedMaxLoss}):{" "}
                    <span
                      className={`font-semibold ${
                        riskCalc.verdict === "LARGER"
                          ? "text-red-300"
                          : riskCalc.verdict === "EQUAL"
                            ? "text-amber-300"
                            : "text-emerald-300"
                      }`}
                    >
                      {riskCalc.verdict}
                    </span>
                  </p>
                </div>
              )}
            </div>
            <div className="mt-3 rounded-lg border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.12em] text-slate-300">Risk Management Rules</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-200">
                <li>If result is <strong>LARGER</strong>, reduce size or tighten SL before placing the order.</li>
                <li>If result is <strong>EQUAL</strong> or <strong>LESS</strong>, trade is within disciplined risk budget.</li>
                <li>Do not move SL farther after entry to avoid a loss.</li>
              </ul>
              <p className="mt-2 text-xs text-slate-400">
                Default values exposed: price per tick = 1.25, ticks per point = 4. Entry/TP/SL accept quarter points only.
              </p>
            </div>
          </Card>
        </div>
      ) : null}

      {activeStep === 3 ? (
        <div className="mt-2 grid gap-4 xl:grid-cols-2">
          <Card title="Before Exit Checklist">
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">
              <li>Time decay: after entry, if expectation is stale beyond 6 bars, decide exit path.</li>
              <li>Use 10-bar two-leg and 20-bar references for expectation quality checks.</li>
              <li>If scaled in, break-even or first-entry exit is preferred when structure weakens.</li>
              <li>Do not stay only because position once looked good.</li>
            </ul>
          </Card>

          <Card title="Dynamic Exit Evaluation">
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">
              <li>Use straddle width estimate: (ATM Call + ATM Put) / 50.</li>
              <li>Use IV width estimate: Price × IV × 0.06299.</li>
              <li>Read put/call OI ratio for sentiment pressure.</li>
              <li>Evaluate divergence between price and S/R, straddle width, IV width before TP/SL decisions.</li>
            </ul>
          </Card>

          <Card title="Execution by Trade Type">
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">
              <li>Scalp: do not add position, protect capital, execute pre-defined TP without delay.</li>
              <li>Swing: direct trend reversal is rare without TR transition; respect continuation structure.</li>
              <li>If opposite side has strong setups, exit faster and avoid adding.</li>
              <li>If opposite lacks quality and your thesis remains intact, hold/add only by pre-plan.</li>
            </ul>
          </Card>

          <Card title="Core Management Rules">
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">
              {entryRules.map((item) => (
                <li key={item}>{item}</li>
              ))}
              {managementRules.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </Card>
        </div>
      ) : null}
    </AppShell>
  );
}

function HintChipGroup({
  items,
  tone,
  hintLabel,
}: {
  items: { text: string; hint: string }[];
  tone: "cyan" | "emerald" | "fuchsia" | "amber";
  hintLabel: string;
}) {
  const [activeHint, setActiveHint] = useState<string>("");
  const toneClass = {
    cyan: "border-cyan-500/35 bg-cyan-500/15 text-cyan-200",
    emerald: "border-emerald-500/35 bg-emerald-500/15 text-emerald-200",
    fuchsia: "border-fuchsia-500/35 bg-fuchsia-500/15 text-fuchsia-200",
    amber: "border-amber-500/35 bg-amber-500/15 text-amber-200",
  }[tone];

  return (
    <>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <button
            key={item.text}
            type="button"
            onMouseEnter={() => setActiveHint(item.hint)}
            onFocus={() => setActiveHint(item.hint)}
            onClick={() => setActiveHint(item.hint)}
            className={`inline-flex w-fit max-w-full items-center rounded-full border px-3 py-1 text-xs font-semibold ${toneClass}`}
          >
            {item.text}
          </button>
        ))}
      </div>
      <p className="mt-3 text-xs text-slate-400">
        {activeHint ? `${hintLabel}: ${activeHint}` : `Hover or click a chip to see ${hintLabel.toLowerCase()}.`}
      </p>
    </>
  );
}
