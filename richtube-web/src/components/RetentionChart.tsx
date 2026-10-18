// ============================================================================
// RICHTUBE - YouTube Intelligence & Autonomous Production Engine
// Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
// Module: Biểu đồ sóng giữ chân (Most Replayed Heatmap)
// ============================================================================

import React from "react";
import { HeatmapPoint } from "@/types/richtube";

function toSeconds(ts: string): number {
  return ts
    .trim()
    .split(":")
    .reduce((acc, part) => acc * 60 + Number(part || 0), 0);
}

function parseRange(range: string): [number, number] {
  const [a, b] = range.split("-");
  return [toSeconds(a ?? "0"), toSeconds(b ?? a ?? "0")];
}

function fmt(seconds: number): string {
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${String(m).padStart(2, "0")}:${sec}`;
}

const W = 100;
const H = 32;

export default function RetentionChart({
  curve,
  duration,
  spikes,
  drops,
}: {
  curve: number[];
  duration: number;
  spikes: HeatmapPoint[];
  drops: HeatmapPoint[];
}) {
  if (curve.length < 2) {
    return (
      <div className="h-20 rounded-lg border border-dashed border-slate-800 flex items-center justify-center text-[11px] text-slate-500">
        Video này chưa có dữ liệu Most Replayed (video mới hoặc ít lượt xem)
      </div>
    );
  }

  const total = duration > 0 ? duration : Math.max(...[...spikes, ...drops].map((p) => parseRange(p.time_range)[1]), 1);
  const step = W / (curve.length - 1);
  const points = curve.map((v, i) => `${(i * step).toFixed(2)},${(H - v * (H - 2)).toFixed(2)}`);
  const line = `M${points.join(" L")}`;
  const area = `${line} L${W},${H} L0,${H} Z`;

  const band = (p: HeatmapPoint) => {
    const [start, end] = parseRange(p.time_range);
    const x = Math.min((start / total) * W, W);
    return { x, width: Math.max(Math.min((end / total) * W, W) - x, 0.8) };
  };

  return (
    <div>
      <div className="relative h-24 rounded-lg bg-slate-950/80 border border-slate-800 overflow-hidden">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="absolute inset-0 w-full h-full" role="img"
          aria-label="Biểu đồ mức độ xem lại theo thời gian">
          <defs>
            <linearGradient id="retention-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#34d399" stopOpacity="0.55" />
              <stop offset="100%" stopColor="#34d399" stopOpacity="0.03" />
            </linearGradient>
          </defs>
          {spikes.map((p, i) => {
            const b = band(p);
            return <rect key={`s${i}`} x={b.x} y={0} width={b.width} height={H} fill="#34d399" opacity={0.12} />;
          })}
          {drops.map((p, i) => {
            const b = band(p);
            return <rect key={`d${i}`} x={b.x} y={0} width={b.width} height={H} fill="#ef4444" opacity={0.18} />;
          })}
          <path d={area} fill="url(#retention-fill)" />
          <path d={line} fill="none" stroke="#34d399" strokeWidth={0.6} vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
      <div className="flex justify-between text-[10px] font-mono text-slate-500 mt-1">
        <span>00:00</span>
        <span>{fmt(total / 2)}</span>
        <span>{fmt(total)}</span>
      </div>
    </div>
  );
}
