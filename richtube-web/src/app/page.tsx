// ============================================================================
// RICHTUBE - YouTube Intelligence & Autonomous Production Engine
// Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
// Module: 3-Column Autonomous Studio Command Center UI
// ============================================================================

"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Radar,
  Flame,
  Sparkles,
  Copy,
  Check,
  Globe,
  Film,
  Volume2,
  Eye,
  AlertTriangle,
  ExternalLink,
  Layers,
  CheckCircle2,
} from "lucide-react";
import { EngineHealth, Job, OutlierRecord } from "@/types/richtube";
import { triggerVideoSpy, triggerChannelDiscovery, checkEngineHealth, fetchOutliers, getJob } from "@/lib/api";

const MARKETS = ["US", "JP", "KR", "ES", "DE", "FR"];

// Dữ liệu mẫu khởi tạo để hiển thị trực quan ngay khi mở Dashboard
const INITIAL_OUTLIERS: OutlierRecord[] = [
  {
    video_id: "dQw4w9WgXcQ",
    title: "How One Secret Company Monopolized Global Chip Machines",
    channel_name: "MagnatesMedia",
    market: "US",
    url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    thumbnail_url: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=600&q=80",
    tae_score: 5.4,
    current_vph: 4280,
    baseline_vph: 790,
    published_hours_ago: 36,
    lark_synced: true,
    lark_record_id: "rec_snakemedia_01",
    heatmap_peaks: {
      retention_spikes: [
        { time_range: "00:00 - 00:18", intensity: 0.94, note: "Hook mở màn 3D + nghịch lý địa chính trị" },
        { time_range: "04:15 - 04:50", intensity: 0.88, note: "Tiết lộ hợp đồng độc quyền với TSMC" },
        { time_range: "09:10 - 09:45", intensity: 0.82, note: "Cú twist về lệnh cấm vận công nghệ" },
      ],
      retention_drops: [
        { time_range: "06:20 - 07:05", intensity: 0.12, note: "Đoạn giải thích lịch sử thành lập quá dài dòng" },
      ],
    },
    deconstruction: {
      packaging_analysis: {
        visual_trigger: "Cỗ máy quang khắc EUV đặt giữa bàn cờ Mỹ - Trung, độ tương phản Xanh/Đỏ cực gắt, chữ vàng 'MONOPOLY'.",
        curiosity_gap: "Tại sao cả thế giới công nghệ phải phụ thuộc vào một công ty vô danh ở Hà Lan?",
        psychological_angle: "Mystery / Hidden Power (Quyền lực ngầm chi phối thế giới)",
      },
      hook_30s_breakdown: {
        opening_mechanism: "Mở đầu bằng câu khẳng định gây sốc: 'Nếu nhà máy này tại Hà Lan biến mất, nền văn minh hiện đại sẽ lùi lại 30 năm'.",
        pacing_notes: "14 lần cắt cảnh trong 30s đầu (2.1s/cut). Nhạc Synth trầm dồn dập, ngắt im lặng (Silence Drop) đúng giây 00:07.",
        core_loop_opened: "Bí mật về canh bạc trị giá 15 tỷ USD suýt làm công ty phá sản trước khi thống trị toàn cầu.",
      },
      narrative_beats: [
        {
          time_range: "00:00 - 00:45",
          beat_name: "The Indispensable Monopoly Hook",
          retention_technique: "High-Stakes Paradox + Silence Drop",
          structural_purpose: "Khẳng định tầm quan trọng sống còn của chủ thể và mở vòng lặp tò mò lớn nhất.",
        },
        {
          time_range: "00:45 - 03:30",
          beat_name: "The Impossible Physics Challenge",
          retention_technique: "Visual Metaphor (3D Zoom-in)",
          structural_purpose: "Giải thích độ khó kỹ thuật bằng hình ảnh ẩn dụ trực quan để giữ chân tệp khán giả đại chúng.",
        },
      ],
      exploitable_gaps: {
        unanswered_questions: [
          "Liệu Trung Quốc đã chế tạo được máy thay thế ngầm đến giai đoạn nào?",
          "Chi phí vận hành thực tế mỗi giờ của 1 cỗ máy này đắt đỏ ra sao?",
        ],
        viewer_complaints_or_debates: "Hàng trăm bình luận tranh cãi về việc video bỏ qua vai trò của chuỗi cung ứng gương quang học Zeiss (Đức).",
        superior_angle_proposal: "Triển khai góc nhìn: 'Liên minh Ngầm Đằng Sau Cỗ Máy Đắt Nhất Hành Tinh' - Bóc tách sâu mắt xích Zeiss & chi phí ẩn mà video gốc bỏ sót.",
      },
    },
    blueprint: {
      packaging_blueprint: {
        titles: [
          "The $380M Machine No Country Can Copy",
          "How One Tiny Company Controls the Entire World",
          "Inside the Secret Monopoly Behind Every Microchip",
        ],
        thumbnail_concepts: [
          {
            layout_description: "Cận cảnh cỗ máy phát tia laser tím ở trung tâm, 2 bên là bóng mờ 2 siêu cường đang giằng co, text ngắn: 'UNTOUCHABLE'.",
            ai_image_prompt: "Cinematic 3D render of a futuristic extreme ultraviolet lithography machine glowing neon blue inside a dark high-tech cleanroom, dramatic volumetric lighting, hyper-detailed, 8k, Unreal Engine 5 style --ar 16:9",
          },
        ],
      },
      production_script: [
        {
          scene_id: 1,
          estimated_time: "00:00 - 00:07",
          beat_function: "Visual & Cognitive Hook",
          voiceover_script: "[Trầm, dứt khoát] Bên trong một căn phòng kín tại Hà Lan... đang vận hành cỗ máy duy nhất ngăn nền kinh tế toàn cầu sụp đổ. [Ngắt 1s]",
          visual_direction: "Zoom nhanh (Fast push-in) xuyên qua bản đồ châu Âu vào thẳng bên trong phòng sạch ASML, chèn chữ lớn '100% MONOPOLY'.",
          visual_generation_prompt: "3D isometric map of Netherlands zooming into a glowing futuristic facility, dark moody cinematic style, gold and cyan accents",
          audio_sfx_cues: "Deep sub-bass boom + Map whoosh + Silence drop tại giây 00:06.5",
        },
        {
          scene_id: 2,
          estimated_time: "00:07 - 00:19",
          beat_function: "Agitation & Curiosity Loop",
          voiceover_script: "[Nhịp nhanh hơn] Nó nặng bằng 2 chiếc máy bay chở khách, đắt giá 380 triệu đô la... nhưng thứ thực sự khiến các siêu cường mất ngủ lại nằm ở chiếc gương bí mật bên trong.",
          visual_direction: "Tách lớp 3D (Exploded view) cỗ máy để lộ hệ thống gương phản xạ tia cực tím ở lõi trung tâm.",
          visual_generation_prompt: "3D exploded view of complex industrial microchip machine revealing a glowing mirror core, dark background, cinematic rim lighting",
          audio_sfx_cues: "Mechanical unfolding SFX + High tension ticking clock BGM",
        },
      ],
    },
  },
];

export default function RichTubeDashboard() {
  const [outliers, setOutliers] = useState<OutlierRecord[]>(INITIAL_OUTLIERS);
  const [isDemoData, setIsDemoData] = useState(true);
  const [selected, setSelected] = useState<OutlierRecord>(INITIAL_OUTLIERS[0]);
  const [spyInput, setSpyInput] = useState("");
  const [selectedMarketFilter, setSelectedMarketFilter] = useState<string>("ALL");
  const [copiedIndex, setCopiedIndex] = useState<string | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [statusBanner, setStatusBanner] = useState<string | null>(null);
  const [health, setHealth] = useState<EngineHealth | null>(null);
  const engineOnline = health === null ? null : health.status === "online";

  // Tải dữ liệu thật từ RICHTUBE Engine; nếu chưa có thì giữ dữ liệu mẫu
  const loadOutliers = useCallback(async (focusVideoId?: string) => {
    try {
      const records = await fetchOutliers();
      if (records.length === 0) return;
      setOutliers(records);
      setIsDemoData(false);
      setSelected((current) =>
        records.find((r) => r.video_id === focusVideoId) ??
        records.find((r) => r.video_id === current.video_id) ??
        records[0]
      );
    } catch {
      // Engine offline -> tiếp tục hiển thị dữ liệu mẫu
    }
  }, []);

  useEffect(() => {
    checkEngineHealth().then(setHealth);
    loadOutliers();
  }, [loadOutliers]);

  // Theo dõi lệnh đang chạy ở Engine cho tới khi xong
  const watchJob = async (job: Job) => {
    for (let i = 0; i < 300; i++) {
      await new Promise((r) => setTimeout(r, 4000));
      try {
        const latest = await getJob(job.job_id);
        if (latest.status === "done") {
          await loadOutliers(latest.result_video_ids[0]);
          checkEngineHealth().then(setHealth);
          setStatusBanner(
            latest.result_video_ids.length
              ? `✅ Hoàn tất! Đã mổ xẻ ${latest.result_video_ids.length} video và cập nhật Dashboard.`
              : "⚠️ Lệnh đã chạy xong nhưng không tìm thấy video outlier phù hợp."
          );
          return;
        }
        if (latest.status === "failed") {
          setStatusBanner(`❌ Lệnh thất bại: ${latest.error ?? "không rõ lỗi"}`);
          return;
        }
      } catch {
        // Mất kết nối tạm thời -> thử lại ở vòng sau
      }
    }
  };

  const handleCopy = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(id);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch {
      setStatusBanner("⚠️ Trình duyệt chặn quyền Copy. Hãy bôi đen và copy thủ công.");
    }
  };

  const handleQuickAction = async (mode: "spy" | "discover") => {
    if (!spyInput.trim()) return;
    setIsTriggering(true);
    setStatusBanner(null);
    try {
      let job: Job;
      if (mode === "spy") {
        job = await triggerVideoSpy(spyInput.trim());
        setStatusBanner("🔬 Đang mổ xẻ Video (1-3 phút). Kết quả sẽ tự hiện ở đây, gửi Telegram & đồng bộ Lark Base.");
      } else {
        job = await triggerChannelDiscovery(spyInput.trim(), MARKETS);
        setStatusBanner("🌐 Đang truy vết kênh tương tự ở 6 thị trường & ghép lưới 3x3 (3-10 phút)...");
      }
      setSpyInput("");
      watchJob(job);
    } catch (err) {
      setStatusBanner(
        err instanceof TypeError
          ? "⚠️ Không kết nối được Backend (chế độ Demo). Hãy bật RICHTUBE Engine ở cổng 8000 để chạy thực tế."
          : `⚠️ ${(err as Error).message}`
      );
    } finally {
      setIsTriggering(false);
    }
  };

  const filteredOutliers =
    selectedMarketFilter === "ALL"
      ? outliers
      : outliers.filter((o) => o.market === selectedMarketFilter);

  return (
    <div className="h-screen bg-[#090B10] text-slate-100 flex flex-col font-sans overflow-hidden">
      {/* TOP HEADER BAR - THƯƠNG HIỆU RICHTUBE | SNAKEMEDIA */}
      <header className="h-16 shrink-0 border-b border-slate-800/80 bg-[#0D1017] px-6 flex items-center justify-between gap-4 z-30">
        <div className="flex items-center gap-4 min-w-0">
          <div className="h-10 w-10 shrink-0 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Radar className="w-6 h-6 text-slate-950 stroke-[2.5]" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2.5">
              <span className="font-black tracking-wider text-lg bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400 bg-clip-text text-transparent">
                RICHTUBE OS
              </span>
              <span className="text-[11px] font-semibold uppercase tracking-widest px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                SNAKEMEDIA CO., LTD.
              </span>
            </div>
            <p className="text-xs text-slate-400 truncate">
              Hệ thống Do thám Thuật toán Đa thị trường & Sản xuất Kịch bản 4 Cột Tự hành
            </p>
          </div>
        </div>

        {/* Thanh nhập lệnh nhanh: Spy Video hoặc Discover Channel */}
        <div className="flex items-center gap-2 w-[520px] shrink-0">
          <input
            type="text"
            value={spyInput}
            onChange={(e) => setSpyInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleQuickAction("spy")}
            placeholder="Dán link Video để bóc tách 60s hoặc link Kênh để tìm đối thủ..."
            className="w-full bg-slate-900/90 border border-slate-700/80 rounded-lg px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
          <button
            onClick={() => handleQuickAction("spy")}
            disabled={isTriggering}
            className="px-3.5 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center gap-1.5 whitespace-nowrap transition"
          >
            <Flame className="w-3.5 h-3.5" />
            Spy Video
          </button>
          <button
            onClick={() => handleQuickAction("discover")}
            disabled={isTriggering}
            className="px-3.5 py-2 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 disabled:opacity-50 text-cyan-300 border border-cyan-500/30 font-semibold text-xs flex items-center gap-1.5 whitespace-nowrap transition"
          >
            <Globe className="w-3.5 h-3.5" />
            Tìm Kênh Đa Quốc Gia
          </button>
        </div>

        {/* Trạng thái API Pool & Lark Sync */}
        <div className="flex items-center gap-3 text-xs shrink-0">
          <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${
                engineOnline === null
                  ? "bg-slate-500"
                  : engineOnline
                    ? "bg-emerald-400 animate-pulse"
                    : "bg-red-500"
              }`}
            />
            <span className="text-slate-300 font-medium">
              Engine:{" "}
              {engineOnline === null
                ? "Đang kiểm tra..."
                : engineOnline
                  ? `Online · Gemini Pool ${health?.gemini_pool_size ?? 0} key`
                  : "Offline (Demo)"}
            </span>
          </div>
          <div
            className={`px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center gap-1.5 ${
              health?.lark_configured ? "text-emerald-400" : "text-slate-500"
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>{health?.lark_configured ? "Lark Base Connected" : "Lark Base chưa cấu hình"}</span>
          </div>
        </div>
      </header>

      {/* Thanh thông báo trạng thái */}
      {statusBanner && (
        <div className="shrink-0 bg-emerald-950/60 border-b border-emerald-500/30 px-6 py-2 text-xs text-emerald-300 flex items-center justify-between">
          <span>{statusBanner}</span>
          <button onClick={() => setStatusBanner(null)} className="text-slate-400 hover:text-white">
            Đóng
          </button>
        </div>
      )}

      {/* BỐ CỤC CHÍNH 3 CỘT: SIGNAL -> ANATOMY -> PRODUCTION */}
      <main className="flex-1 min-h-0 grid grid-cols-12 gap-0 overflow-hidden">
        {/* ================================================================
            CỘT 1 (3/12): MARKET SIGNAL RADAR (KẾ THỪA & NÂNG CẤP VIDIQ)
           ================================================================ */}
        <section className="col-span-3 border-r border-slate-800/80 bg-[#0B0E14] flex flex-col min-h-0 overflow-hidden">
          <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Flame className="w-4 h-4 text-orange-400" />
              <h2 className="font-bold text-xs uppercase tracking-wider text-slate-200">
                1. Tín Hiệu Outlier (Pure TAE)
              </h2>
            </div>
            <span className="text-[11px] text-slate-400">
              {isDemoData ? "Dữ liệu mẫu" : `${outliers.length} video`}
            </span>
          </div>

          {/* Bộ lọc thị trường (US, JP, KR, ES, DE, FR) */}
          <div className="px-4 py-2.5 border-b border-slate-800/60 flex items-center gap-1.5 overflow-x-auto">
            {["ALL", ...MARKETS].map((mkt) => (
              <button
                key={mkt}
                onClick={() => setSelectedMarketFilter(mkt)}
                className={`px-2.5 py-1 rounded text-[11px] font-bold transition ${
                  selectedMarketFilter === mkt
                    ? "bg-emerald-500 text-slate-950"
                    : "bg-slate-900 text-slate-400 hover:text-slate-200"
                }`}
              >
                {mkt}
              </button>
            ))}
          </div>

          {/* Danh sách thẻ Video Outlier */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {filteredOutliers.length === 0 && (
              <p className="text-xs text-slate-500 text-center py-8">
                Chưa có video Outlier nào ở thị trường {selectedMarketFilter}.
              </p>
            )}
            {filteredOutliers.map((item) => {
              const isSelected = selected.video_id === item.video_id;
              return (
                <div
                  key={item.video_id}
                  onClick={() => setSelected(item)}
                  className={`p-3 rounded-xl border transition cursor-pointer ${
                    isSelected
                      ? "bg-slate-900/95 border-emerald-500/60 shadow-lg shadow-emerald-950/30"
                      : "bg-slate-900/40 border-slate-800/80 hover:border-slate-700"
                  }`}
                >
                  <div className="relative rounded-lg overflow-hidden mb-2.5 aspect-video bg-slate-950">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={item.thumbnail_url}
                      alt={item.title}
                      className="w-full h-full object-cover text-transparent"
                      onError={(e) => {
                        // Ảnh lỗi -> dùng thumbnail gốc của YouTube
                        const fallback = `https://i.ytimg.com/vi/${item.video_id}/hqdefault.jpg`;
                        if (e.currentTarget.src !== fallback) e.currentTarget.src = fallback;
                      }}
                    />
                    <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-slate-950/85 border border-slate-700 text-[10px] font-bold text-cyan-300">
                      [{item.market}] {item.channel_name}
                    </div>
                    <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-red-600/95 text-white font-black text-xs shadow">
                      TAE: {item.tae_score}x
                    </div>
                  </div>

                  <h3 className="font-semibold text-xs text-slate-100 line-clamp-2 leading-snug mb-2">
                    {item.title}
                  </h3>

                  <div className="flex items-center justify-between text-[11px] text-slate-400 pt-2 border-t border-slate-800/80">
                    <span className="text-emerald-400 font-bold">⚡ {item.current_vph.toLocaleString()} VPH</span>
                    <span>Baseline: {item.baseline_vph.toLocaleString()} VPH</span>
                    <span>{item.published_hours_ago}h trước</span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* ================================================================
            CỘT 2 (4/12): DEEP NARRATIVE ANATOMY (KẾ THỪA & NÂNG CẤP NEVLEX)
           ================================================================ */}
        <section className="col-span-4 border-r border-slate-800/80 bg-[#0D1017] flex flex-col min-h-0 overflow-hidden">
          <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Eye className="w-4 h-4 text-cyan-400" />
              <h2 className="font-bold text-xs uppercase tracking-wider text-slate-200">
                2. Giải Mã Cấu Trúc & Sóng Giữ Chân
              </h2>
            </div>
            <a
              href={selected.url}
              target="_blank"
              rel="noreferrer"
              className="text-[11px] text-cyan-400 hover:underline flex items-center gap-1"
            >
              Xem gốc <ExternalLink className="w-3 h-3" />
            </a>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* A. BIỂU ĐỒ MOST REPLAYED HEATMAP THỰC TẾ */}
            <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
              <div className="flex items-center justify-between mb-2.5">
                <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
                  🔥 Dữ liệu Ngầm Most Replayed (YouTube Heatmap)
                </span>
              </div>
              <div className="space-y-2">
                {selected.heatmap_peaks.retention_spikes.map((spike, idx) => (
                  <div key={idx} className="text-xs bg-slate-950/80 p-2.5 rounded-lg border border-emerald-500/20">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono font-bold text-emerald-300">[{spike.time_range}]</span>
                      <span className="text-[11px] font-bold text-emerald-400">
                        Đỉnh giữ chân: {Math.round(spike.intensity * 100)}%
                      </span>
                    </div>
                    <div className="h-1 rounded bg-slate-800 mb-1.5 overflow-hidden">
                      <div className="h-full bg-emerald-400" style={{ width: `${spike.intensity * 100}%` }} />
                    </div>
                    <p className="text-slate-300 text-[11px]">{spike.note}</p>
                  </div>
                ))}

                {selected.heatmap_peaks.retention_drops.map((drop, idx) => (
                  <div key={idx} className="text-xs bg-red-950/20 p-2.5 rounded-lg border border-red-500/30">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono font-bold text-red-400">[{drop.time_range}]</span>
                      <span className="text-[11px] font-bold text-red-400 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> Vùng trũng tụt view ({Math.round(drop.intensity * 100)}%)
                      </span>
                    </div>
                    <div className="h-1 rounded bg-slate-800 mb-1.5 overflow-hidden">
                      <div className="h-full bg-red-500" style={{ width: `${drop.intensity * 100}%` }} />
                    </div>
                    <p className="text-slate-300 text-[11px]">{drop.note}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* B. GIẢI MÃ HOOK 30 GIÂY ĐẦU & BAO BÌ */}
            <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-2.5">
              <h3 className="text-xs font-bold text-cyan-400 uppercase tracking-wider">
                🎬 Mổ Xẻ 30s Đầu (Khắc Timecode) & Bao Bì
              </h3>
              <div className="text-xs space-y-2 text-slate-300">
                <p>
                  <strong className="text-slate-100">• Đòn tâm lý chủ đạo:</strong>{" "}
                  <span className="text-amber-300">{selected.deconstruction.packaging_analysis.psychological_angle}</span>
                </p>
                <p>
                  <strong className="text-slate-100">• Kích thích thị giác (Thumbnail):</strong>{" "}
                  {selected.deconstruction.packaging_analysis.visual_trigger}
                </p>
                <p>
                  <strong className="text-slate-100">• Khoảng trống tò mò (Curiosity Gap):</strong>{" "}
                  {selected.deconstruction.packaging_analysis.curiosity_gap}
                </p>
                <p>
                  <strong className="text-slate-100">• Cơ chế 5s đầu:</strong>{" "}
                  {selected.deconstruction.hook_30s_breakdown.opening_mechanism}
                </p>
                <p>
                  <strong className="text-slate-100">• Nhịp dựng & Âm thanh (Pacing):</strong>{" "}
                  <span className="text-emerald-300">{selected.deconstruction.hook_30s_breakdown.pacing_notes}</span>
                </p>
                <p>
                  <strong className="text-slate-100">• Vòng lặp tò mò mở ra:</strong>{" "}
                  {selected.deconstruction.hook_30s_breakdown.core_loop_opened}
                </p>
              </div>

              {/* Các nhịp kể chuyện có Timecode */}
              <div className="pt-2 border-t border-slate-800 space-y-2">
                {selected.deconstruction.narrative_beats.map((beat, idx) => (
                  <div key={idx} className="text-[11px] bg-slate-950/80 p-2.5 rounded-lg border border-slate-800">
                    <div className="flex items-center justify-between mb-1 gap-2">
                      <span className="font-mono font-bold text-cyan-300">[{beat.time_range}]</span>
                      <span className="text-slate-400 text-right">{beat.retention_technique}</span>
                    </div>
                    <p className="font-semibold text-slate-100">{beat.beat_name}</p>
                    <p className="text-slate-400">{beat.structural_purpose}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* C. ĐIỂM KHUYẾT TỪ BÌNH LUẬN KHÁN GIẢ (GAP IDENTIFIER) */}
            <div className="p-3.5 rounded-xl bg-gradient-to-br from-amber-950/30 to-slate-900 border border-amber-500/40 space-y-2">
              <h3 className="text-xs font-bold text-amber-300 uppercase tracking-wider">
                💡 Vũ Khí Vượt Mặt Đối Thủ (Quét từ Top Comments)
              </h3>
              <p className="text-xs text-slate-200 leading-relaxed font-medium">
                {selected.deconstruction.exploitable_gaps.superior_angle_proposal}
              </p>
              <div className="pt-2 border-t border-amber-500/20 text-[11px] text-slate-300">
                <strong>Tranh cãi chưa được giải đáp:</strong>{" "}
                {selected.deconstruction.exploitable_gaps.viewer_complaints_or_debates}
              </div>
              <ul className="list-disc pl-4 text-[11px] text-slate-300 space-y-1">
                {selected.deconstruction.exploitable_gaps.unanswered_questions.map((q, idx) => (
                  <li key={idx}>{q}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* ================================================================
            CỘT 3 (5/12): DIRECT-TO-PRODUCTION BLUEPRINT (SNAKEMEDIA STUDIO)
           ================================================================ */}
        <section className="col-span-5 bg-[#090B10] flex flex-col min-h-0 overflow-hidden">
          <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-emerald-400" />
              <h2 className="font-bold text-xs uppercase tracking-wider text-slate-200">
                3. Đặc Tả Sản Xuất & Kịch Bản 4 Cột
              </h2>
            </div>

            <span className="px-2.5 py-1 rounded-md bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-[11px] font-bold flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5" />
              Lark Base Record: {selected.lark_record_id ?? "—"}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-5">
            {/* PHẦN 1: 3 PHƯƠNG ÁN TIÊU ĐỀ & PROMPT THUMBNAIL */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
              <h3 className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
                🏷️ Bao Bì Đề Xuất Mới (Kế thừa công thức CTR cao)
              </h3>
              <div className="space-y-1.5">
                {selected.blueprint.packaging_blueprint.titles.map((t, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between bg-slate-950 px-3 py-2 rounded-lg border border-slate-800/80 text-xs"
                  >
                    <span className="font-semibold text-slate-100">
                      {i + 1}. {t}
                    </span>
                    <button
                      onClick={() => handleCopy(t, `title-${i}`)}
                      className="text-slate-400 hover:text-emerald-400"
                      aria-label="Copy tiêu đề"
                    >
                      {copiedIndex === `title-${i}` ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                ))}
              </div>

              {selected.blueprint.packaging_blueprint.thumbnail_concepts.map((tc, idx) => (
                <div key={idx} className="p-3 rounded-lg bg-slate-950 border border-cyan-500/30 space-y-1.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-cyan-300">🎨 Prompt Tạo Phôi Thumbnail (Midjourney / Whisk):</span>
                    <button
                      onClick={() => handleCopy(tc.ai_image_prompt, `thumb-${idx}`)}
                      className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 text-[11px] flex items-center gap-1 hover:bg-cyan-500/30"
                    >
                      {copiedIndex === `thumb-${idx}` ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                      Copy Prompt
                    </button>
                  </div>
                  <p className="text-slate-400 text-[11px]">{tc.layout_description}</p>
                  <p className="font-mono text-[11px] text-slate-200 bg-slate-900 p-2 rounded border border-slate-800">
                    {tc.ai_image_prompt}
                  </p>
                </div>
              ))}
            </div>

            {/* PHẦN 2: BẢNG KỊCH BẢN PHÂN CẢNH 4 CỘT (VOICE + VISUAL + PROMPT + SFX) */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                  <Film className="w-4 h-4 text-emerald-400" />
                  Bảng Phân Cảnh Kịch Bản 4 Cột (Production Storyboard)
                </h3>
              </div>

              {selected.blueprint.production_script.map((scene) => (
                <div
                  key={scene.scene_id}
                  className="p-3.5 rounded-xl bg-slate-900/75 border border-slate-800 space-y-2.5 text-xs"
                >
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold">
                        Cảnh #{scene.scene_id}
                      </span>
                      <span className="font-mono text-slate-300 font-semibold">{scene.estimated_time}</span>
                    </div>
                    <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-cyan-300">
                      {scene.beat_function}
                    </span>
                  </div>

                  {/* Cột 1 & 2: Lời thoại Voiceover + Chỉ dẫn Dựng hình */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800/80">
                      <div className="text-[10px] font-bold uppercase text-emerald-400 mb-1">
                        🎙️ Lời Thoại (Voiceover / TTS)
                      </div>
                      <p className="text-slate-100 leading-relaxed">{scene.voiceover_script}</p>
                    </div>

                    <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800/80">
                      <div className="text-[10px] font-bold uppercase text-cyan-400 mb-1">
                        🎬 Chỉ Dẫn Dựng Hình (Editor Notes)
                      </div>
                      <p className="text-slate-300 leading-relaxed">{scene.visual_direction}</p>
                    </div>
                  </div>

                  {/* Cột 3: Prompt tạo Ảnh/Video AI */}
                  <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800/80">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] font-bold uppercase text-purple-400">
                        🖼️ Visual AI Prompt (Copy sang Whisk / Midjourney)
                      </span>
                      <button
                        onClick={() => handleCopy(scene.visual_generation_prompt, `scene-${scene.scene_id}`)}
                        className="text-[11px] text-slate-400 hover:text-white flex items-center gap-1"
                      >
                        {copiedIndex === `scene-${scene.scene_id}` ? (
                          <Check className="w-3 h-3 text-emerald-400" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                        Copy
                      </button>
                    </div>
                    <p className="font-mono text-[11px] text-slate-300">{scene.visual_generation_prompt}</p>
                  </div>

                  {/* Cột 4: Hiệu ứng âm thanh SFX / BGM */}
                  <div className="flex items-center gap-2 text-[11px] text-amber-300 bg-amber-950/20 px-3 py-1.5 rounded-lg border border-amber-500/20">
                    <Volume2 className="w-3.5 h-3.5 shrink-0" />
                    <span>
                      <strong>Audio / SFX Cue:</strong> {scene.audio_sfx_cues}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
