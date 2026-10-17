// ============================================================================
// RICHTUBE - YouTube Intelligence & Autonomous Production Engine
// Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
// Module: FastAPI Client Connector
// ============================================================================

import type { EngineHealth, Job, OutlierRecord } from "@/types/richtube";

const API_BASE_URL = process.env.NEXT_PUBLIC_RICHTUBE_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_RICHTUBE_API_KEY || "";

function headers(): HeadersInit {
  return {
    "Content-Type": "application/json",
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
  };
}

async function readError(res: Response, fallback: string): Promise<Error> {
  try {
    const data = await res.json();
    return new Error(typeof data.detail === "string" ? data.detail : fallback);
  } catch {
    return new Error(fallback);
  }
}

export async function triggerVideoSpy(videoUrl: string): Promise<Job> {
  const res = await fetch(`${API_BASE_URL}/api/v1/spy/video`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ video_url: videoUrl, notify_telegram: true }),
  });
  if (!res.ok) throw await readError(res, "Không thể kích hoạt lệnh Spy Video");
  return res.json();
}

export async function triggerChannelDiscovery(seedChannelUrl: string, targetMarkets: string[]): Promise<Job> {
  const res = await fetch(`${API_BASE_URL}/api/v1/discover/channel`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      seed_channel_url: seedChannelUrl,
      target_markets: targetMarkets,
    }),
  });
  if (!res.ok) throw await readError(res, "Không thể kích hoạt lệnh Truy vết Kênh");
  return res.json();
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}`, { cache: "no-store" });
  if (!res.ok) throw await readError(res, "Không đọc được trạng thái lệnh");
  return res.json();
}

export async function fetchOutliers(): Promise<OutlierRecord[]> {
  const res = await fetch(`${API_BASE_URL}/api/v1/outliers`, { cache: "no-store" });
  if (!res.ok) throw await readError(res, "Không tải được danh sách Outlier");
  return res.json();
}

export async function checkEngineHealth(): Promise<EngineHealth> {
  try {
    const res = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
    if (!res.ok) throw new Error();
    return await res.json();
  } catch {
    return {
      status: "offline",
      gemini_pool_size: 0,
      youtube_configured: false,
      lark_configured: false,
      telegram_configured: false,
      records: 0,
    };
  }
}
