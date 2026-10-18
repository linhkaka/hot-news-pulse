// ============================================================================
// RICHTUBE - YouTube Intelligence & Autonomous Production Engine
// Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
// Module: Radar 24/7 - danh sách kênh theo dõi
// ============================================================================

import React, { useState } from "react";
import { ChevronDown, ChevronUp, Radio, RefreshCw, X } from "lucide-react";
import { WatchChannel } from "@/types/richtube";

function ago(iso?: string | null): string {
  if (!iso) return "chưa quét";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 60) return `quét ${minutes} phút trước`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `quét ${hours}h trước` : `quét ${Math.round(hours / 24)} ngày trước`;
}

export default function WatchlistPanel({
  channels,
  intervalHours,
  busy,
  onRemove,
  onRunRadar,
}: {
  channels: WatchChannel[];
  intervalHours: number;
  busy: boolean;
  onRemove: (channel: WatchChannel) => void;
  onRunRadar: () => void;
}) {
  const [open, setOpen] = useState(true);

  return (
    <div className="border-b border-slate-800/60">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-2.5 flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-slate-300 hover:bg-slate-900/50"
      >
        <span className="flex items-center gap-1.5">
          <Radio className="w-3.5 h-3.5 text-cyan-400" />
          Radar 24/7 · {channels.length} kênh
        </span>
        {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-1.5">
          {channels.length === 0 ? (
            <p className="text-[11px] text-slate-500 px-1">
              Dán link kênh lên ô nhập phía trên rồi bấm <strong className="text-slate-300">Theo dõi</strong> để Radar tự quét video mới.
            </p>
          ) : (
            <div className="max-h-40 overflow-y-auto space-y-1.5">
              {channels.map((c) => (
                <div
                  key={c.channel_id}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-slate-900/60 border border-slate-800 text-[11px]"
                >
                  {c.thumbnail_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={c.thumbnail_url} alt="" className="w-5 h-5 rounded-full shrink-0" />
                  ) : (
                    <span className="w-5 h-5 rounded-full bg-slate-800 shrink-0" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-slate-200 font-semibold">
                      <span className="text-cyan-300">[{c.market}]</span> {c.title}
                    </p>
                    <p className="text-slate-500">{ago(c.last_scanned_at)}</p>
                  </div>
                  <button
                    onClick={() => onRemove(c)}
                    className="text-slate-500 hover:text-red-400"
                    aria-label={`Bỏ theo dõi ${c.title}`}
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center justify-between pt-1">
            <span className="text-[10px] text-slate-500">
              {intervalHours > 0 ? `Tự quét mỗi ${intervalHours}h` : "Quét tự động đang tắt"}
            </span>
            <button
              onClick={onRunRadar}
              disabled={busy || channels.length === 0}
              className="px-2 py-1 rounded bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 text-[11px] font-semibold flex items-center gap-1 hover:bg-cyan-500/25 disabled:opacity-40"
            >
              <RefreshCw className={`w-3 h-3 ${busy ? "animate-spin" : ""}`} />
              Quét ngay
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
