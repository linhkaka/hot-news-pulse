import pytest

import config
import tracker
from telegram_bot import Telegram

TOKEN = "123456789:AAH" + "x" * 32


@pytest.mark.parametrize("pasted", [
    TOKEN,
    f"  {TOKEN}  ",
    f'"{TOKEN}"',
    f"bot{TOKEN}",
    f"https://api.telegram.org/bot{TOKEN}/getUpdates",
])
def test_clean_bot_token(pasted):
    assert config.clean_bot_token(pasted) == TOKEN


def test_placeholder_token_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-TOKEN-TU-BOTFATHER")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    with pytest.raises(ValueError, match="token mẫu"):
        config.load_config(tmp_path / "none.json")


class Resp:
    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


class FakeTelegramServer:
    """Answers like api.telegram.org does."""

    def __init__(self, get_me, get_chat=None):
        self.answers = {"getMe": get_me, "getChat": get_chat or {"ok": True, "result": {}}}

    def post(self, url, json=None, timeout=None):
        return Resp(self.answers[url.rsplit("/", 1)[1]])


def test_wrong_token_gives_help():
    tg = Telegram(TOKEN, "1", session=FakeTelegramServer(
        {"ok": False, "error_code": 401, "description": "Unauthorized"}))
    help_text = tracker.verify_telegram(tg)
    assert "Token bot Telegram không đúng" in help_text and "@BotFather" in help_text


def test_malformed_token_gives_help():
    tg = Telegram("abc", "1", session=FakeTelegramServer(
        {"ok": False, "error_code": 404, "description": "Not Found"}))
    assert "Token bot Telegram không đúng" in tracker.verify_telegram(tg)


def test_wrong_chat_gives_help():
    tg = Telegram(TOKEN, "999", session=FakeTelegramServer(
        {"ok": True, "result": {"username": "my_view_bot"}},
        {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}))
    help_text = tracker.verify_telegram(tg)
    assert "@my_view_bot" in help_text and "999" in help_text and "Start" in help_text


def test_good_setup_passes():
    tg = Telegram(TOKEN, "1", session=FakeTelegramServer(
        {"ok": True, "result": {"username": "my_view_bot"}}))
    assert tracker.verify_telegram(tg) is None


def test_main_stops_with_code_2_on_bad_token(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.setattr(tracker, "verify_telegram", lambda tg: "help")
    assert tracker.main(["--config", str(tmp_path / "none.json")]) == 2
