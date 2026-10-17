// ============================================================================
// RICHTUBE - YouTube Intelligence & Autonomous Production Engine
// Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
// Module: FastAPI Client Connector
// ============================================================================

const API_BASE_URL = process.env.NEXT_PUBLIC_RICHTUBE_API_URL || "http://localhost:8000";

export async function triggerVideoSpy(videoUrl: string) {
  const res = await fetch(`${API_BASE_URL}/api/v1/spy/video`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_url: videoUrl, notify_telegram: true }),
  });
  if (!res.ok) throw new Error("Không thể kích hoạt lệnh Spy Video");
  return res.json();
}

export async function triggerChannelDiscovery(seedChannelUrl: string, targetMarkets: string[]) {
  const res = await fetch(`${API_BASE_URL}/api/v1/discover/channel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      seed_channel_url: seedChannelUrl,
      target_markets: targetMarkets,
    }),
  });
  if (!res.ok) throw new Error("Không thể kích hoạt lệnh Truy vết Kênh");
  return res.json();
}

export async function checkEngineHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
    if (!res.ok) throw new Error();
    return await res.json();
  } catch {
    return { status: "offline", gemini_pool_size: 0 };
  }
}
