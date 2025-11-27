"use client";

import { useEffect, useRef, useState } from "react";
import { fetchConfig } from "@/lib/config";

type SpeedPreset = number; // seconds per bar

export type PlaybackState = {
  playing: boolean;
  speed: SpeedPreset;
  index: number;
};

export function PlaybackControls({
  maxIndex,
  speeds,
  onChange
}: {
  maxIndex: number;
  speeds?: SpeedPreset[];
  onChange: (state: PlaybackState) => void;
}) {
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<SpeedPreset>(30);
  const [index, setIndex] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const [presets, setPresets] = useState<SpeedPreset[]>(speeds?.length ? speeds : [15, 30, 45, 60]);

  useEffect(() => {
    if (speeds?.length) {
      setPresets(speeds);
      setSpeed(speeds[0]);
      return;
    }
    let mounted = true;
    fetchConfig()
      .then((cfg) => {
        if (!mounted) return;
        if (cfg.playback_speeds?.length) {
          setPresets(cfg.playback_speeds);
          setSpeed(cfg.playback_speeds[0]);
        }
      })
      .catch(() => {
        /* ignore, use defaults */
      });
    return () => {
      mounted = false;
    };
  }, [speeds]);

  useEffect(() => {
    if (!playing) {
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = null;
      return;
    }
    const intervalMs = speed * 1000;
    timerRef.current = setInterval(() => {
      setIndex((prev) => {
        const next = Math.min(prev + 1, maxIndex);
        if (next === maxIndex) {
          setPlaying(false);
        }
        return next;
      });
    }, intervalMs);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = null;
    };
  }, [playing, speed, maxIndex]);

  useEffect(() => {
    onChange({ playing, speed, index });
  }, [playing, speed, index, onChange]);

  const step = (delta: number) => {
    setIndex((prev) => Math.min(Math.max(prev + delta, 0), maxIndex));
    setPlaying(false);
  };

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-surface/70 p-3 text-sm text-slate-200">
      <button
        className="rounded-lg border border-white/10 px-3 py-2 font-semibold transition hover:border-accent"
        onClick={() => setPlaying((p) => !p)}
      >
        {playing ? "Pause" : "Play"}
      </button>
      <div className="flex items-center gap-2">
        <button
          className="rounded-lg border border-white/10 px-3 py-2 transition hover:border-highlight"
          onClick={() => step(-1)}
        >
          Prev
        </button>
        <button
          className="rounded-lg border border-white/10 px-3 py-2 transition hover:border-highlight"
          onClick={() => step(1)}
        >
          Next
        </button>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Speed</span>
        {presets.map((s) => (
          <button
            key={s}
            onClick={() => setSpeed(s as SpeedPreset)}
            className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
              speed === s ? "bg-accent text-black" : "border border-white/10 text-slate-200 hover:border-accent"
            }`}
          >
            {s}s
          </button>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Step</span>
        <input
          type="range"
          min={0}
          max={maxIndex}
          value={index}
          onChange={(e) => {
            setIndex(Number(e.target.value));
            setPlaying(false);
          }}
          className="w-48"
        />
        <span className="text-xs text-slate-300">{index + 1} / {maxIndex + 1}</span>
      </div>
    </div>
  );
}
