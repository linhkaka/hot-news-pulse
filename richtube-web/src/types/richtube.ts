// ============================================================================
// RICHTUBE - YouTube Intelligence & Autonomous Production Engine
// Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
// Module: TypeScript Interfaces for 3-Column Studio Dashboard
// ============================================================================

export type Market = "US" | "JP" | "KR" | "ES" | "DE" | "FR";

export interface EngineHealth {
  status: "online" | "offline";
  gemini_pool_size: number;
  youtube_configured: boolean;
  lark_configured: boolean;
  telegram_configured: boolean;
  records: number;
}

export interface Job {
  job_id: string;
  kind: "spy" | "discover";
  status: "queued" | "running" | "done" | "failed";
  input: string;
  created_at: string;
  finished_at?: string | null;
  error?: string | null;
  result_video_ids: string[];
}

export interface HeatmapPoint {
  time_range: string;
  intensity: number; // 0.0 -> 1.0
  note: string;
}

export interface NarrativeBeat {
  time_range: string;
  beat_name: string;
  retention_technique: string;
  structural_purpose: string;
}

export interface ProductionScene {
  scene_id: number;
  estimated_time: string;
  beat_function: string;
  voiceover_script: string;
  visual_direction: string;
  visual_generation_prompt: string;
  audio_sfx_cues: string;
}

export interface OutlierRecord {
  video_id: string;
  title: string;
  channel_name: string;
  // Thị trường ngoài danh sách chính sẽ là mã quốc gia khác (vd: "VN") hoặc "GLOBAL"
  market: Market | (string & {});
  url: string;
  thumbnail_url: string;
  tae_score: number;
  current_vph: number;
  baseline_vph: number;
  published_hours_ago: number;
  lark_synced: boolean;
  lark_record_id?: string | null;
  analyzed_at?: string;

  // Dữ liệu Cột 2: Deep Anatomy (Nevlex Core)
  heatmap_peaks: {
    retention_spikes: HeatmapPoint[];
    retention_drops: HeatmapPoint[];
  };
  deconstruction: {
    packaging_analysis: {
      visual_trigger: string;
      curiosity_gap: string;
      psychological_angle: string;
    };
    hook_30s_breakdown: {
      opening_mechanism: string;
      pacing_notes: string;
      core_loop_opened: string;
    };
    narrative_beats: NarrativeBeat[];
    exploitable_gaps: {
      unanswered_questions: string[];
      viewer_complaints_or_debates: string;
      superior_angle_proposal: string;
    };
  };

  // Dữ liệu Cột 3: Production Spec (SNAKEMEDIA Generator)
  blueprint: {
    packaging_blueprint: {
      titles: string[];
      thumbnail_concepts: {
        layout_description: string;
        ai_image_prompt: string;
      }[];
    };
    production_script: ProductionScene[];
  };
}
