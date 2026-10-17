# ============================================================================
# RICHTUBE - YouTube Intelligence & Autonomous Production Engine
# Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
# Module: Telegram Bot - ra lệnh cho Engine từ điện thoại
#
# Lệnh:
#   /spy <link video>        Mổ xẻ 1 video outlier
#   /discover <link kênh>    Tìm đối thủ đa quốc gia (US, JP, KR, ES, DE, FR)
#   /top                     5 video TAE cao nhất đã phân tích
#   /status                  Trạng thái Engine
#   /id                      Xem Chat ID của bạn
#   (Dán thẳng link video cũng tự chạy /spy)
# ============================================================================

import asyncio
import logging
import os

import httpx

from richtube.config import get_settings
from richtube.models import MARKETS
from richtube.youtube import parse_video_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("richtube.bot")

settings = get_settings()
API_URL = os.getenv("RICHTUBE_API_URL", "http://localhost:8000").rstrip("/")
TG = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

HELP = (
    "🐍 <b>RICHTUBE OS · SNAKEMEDIA</b>\n\n"
    "/spy &lt;link video&gt; — mổ xẻ video outlier\n"
    "/discover &lt;link kênh&gt; — tìm đối thủ đa quốc gia\n"
    "/top — 5 video TAE cao nhất\n"
    "/status — trạng thái Engine\n"
    "/id — xem Chat ID\n\n"
    "Hoặc dán thẳng link video YouTube."
)


async def reply(http: httpx.AsyncClient, chat_id: int, text: str) -> None:
    await http.post(
        f"{TG}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=20,
    )


async def call_engine(http: httpx.AsyncClient, method: str, path: str, **kwargs) -> httpx.Response:
    headers = {"X-API-Key": settings.richtube_api_key} if settings.richtube_api_key else {}
    return await http.request(method, f"{API_URL}{path}", headers=headers, timeout=30, **kwargs)


def error_detail(res: httpx.Response) -> str:
    try:
        return str(res.json().get("detail", res.text))
    except ValueError:
        return res.text[:200]


async def handle(http: httpx.AsyncClient, message: dict) -> None:
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    if not text:
        return

    command, _, arg = text.partition(" ")
    command = command.split("@")[0].lower()
    arg = arg.strip()

    if command == "/id":
        await reply(http, chat_id, f"Chat ID của bạn: <code>{chat_id}</code>")
        return

    if str(chat_id) not in settings.allowed_chat_ids:
        await reply(
            http, chat_id,
            f"⛔ Chat này chưa được cấp quyền.\nChat ID: <code>{chat_id}</code>\n"
            "Hãy thêm ID này vào TELEGRAM_CHAT_ID hoặc TELEGRAM_ALLOWED_CHAT_IDS trong file .env rồi khởi động lại.",
        )
        return

    if command in ("/start", "/help"):
        await reply(http, chat_id, HELP)
        return

    if not command.startswith("/") and parse_video_id(text):
        command, arg = "/spy", text

    try:
        if command == "/spy":
            if not parse_video_id(arg):
                await reply(http, chat_id, "Cú pháp: /spy https://www.youtube.com/watch?v=...")
                return
            res = await call_engine(
                http, "POST", "/api/v1/spy/video",
                json={"video_url": arg, "notify_telegram": True, "telegram_chat_id": str(chat_id)},
            )
            if res.status_code == 202:
                await reply(http, chat_id, "🔬 Đã nhận lệnh. Đang mổ xẻ video (1-3 phút)...")
            else:
                await reply(http, chat_id, f"⚠️ Lỗi: {error_detail(res)}")

        elif command == "/discover":
            if not arg:
                await reply(http, chat_id, "Cú pháp: /discover https://www.youtube.com/@tenkenh")
                return
            res = await call_engine(
                http, "POST", "/api/v1/discover/channel",
                json={"seed_channel_url": arg, "target_markets": MARKETS, "notify_telegram": True, "telegram_chat_id": str(chat_id)},
            )
            if res.status_code == 202:
                await reply(http, chat_id, "🌐 Đang truy vết kênh tương tự ở 6 thị trường (3-10 phút)...")
            else:
                await reply(http, chat_id, f"⚠️ Lỗi: {error_detail(res)}")

        elif command == "/top":
            res = await call_engine(http, "GET", "/api/v1/outliers")
            records = sorted(res.json(), key=lambda r: r["tae_score"], reverse=True)[:5]
            if not records:
                await reply(http, chat_id, "Chưa có video nào được phân tích.")
                return
            lines = [f"{i+1}. [{r['market']}] <b>{r['tae_score']}x</b> — {r['title']}\n{r['url']}" for i, r in enumerate(records)]
            await reply(http, chat_id, "🔥 <b>Top Outlier</b>\n\n" + "\n\n".join(lines))

        elif command == "/status":
            h = (await call_engine(http, "GET", "/health")).json()
            await reply(
                http, chat_id,
                f"🟢 Engine: {h['status']}\nGemini keys: {h['gemini_pool_size']}\n"
                f"YouTube: {'✅' if h['youtube_configured'] else '❌'} · Lark: {'✅' if h['lark_configured'] else '❌'}\n"
                f"Đã phân tích: {h['records']} video",
            )
        else:
            await reply(http, chat_id, HELP)
    except httpx.HTTPError:
        await reply(http, chat_id, "🔴 Không kết nối được RICHTUBE Engine. Kiểm tra container richtube-api.")


async def main() -> None:
    if not settings.telegram_bot_token:
        log.error("Chưa cấu hình TELEGRAM_BOT_TOKEN — Bot không chạy.")
        while True:  # giữ container sống, tránh restart liên tục
            await asyncio.sleep(3600)

    offset = 0
    async with httpx.AsyncClient() as http:
        log.info("RICHTUBE Bot đang chạy, Engine: %s", API_URL)
        while True:
            try:
                res = await http.get(f"{TG}/getUpdates", params={"offset": offset, "timeout": 50}, timeout=60)
                for update in res.json().get("result", []):
                    offset = update["update_id"] + 1
                    if "message" in update:
                        try:
                            await handle(http, update["message"])
                        except Exception:
                            log.exception("Lỗi khi xử lý tin nhắn")
            except (httpx.HTTPError, ValueError) as exc:
                log.warning("Mất kết nối Telegram: %s — thử lại sau 5s", exc)
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
