import pytest


@pytest.fixture(autouse=True)
def _no_auto_scan(monkeypatch):
    """Lịch tự quét chạy theo giờ thật; tắt trong bài kiểm thử để kết quả không đổi theo giờ chạy."""
    monkeypatch.setenv("SNAKEPOD_NO_SCHEDULER", "1")
