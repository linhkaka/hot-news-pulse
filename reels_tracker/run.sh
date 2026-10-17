#!/usr/bin/env bash
# Chạy tool trên macOS / Linux. Lần đầu sẽ tự cài thư viện.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Đã tạo file .env — hãy mở file .env, điền token rồi chạy lại ./run.sh"
  exit 0
fi
exec .venv/bin/python tracker.py "$@"
