#!/usr/bin/env bash
# Сборка статики: копия главной в /ru/cv/ и PDF-версии резюме через headless Chrome.
# Запуск: ./scripts/build.sh  (нужен Google Chrome и python3)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
PORT="${PORT:-8765}"

cd "$ROOT"

# 1. /ru/cv/ — та же страница, что и главная (старый адрес должен жить).
cp index.html ru/cv/index.html

# 2. PDF печатаем с локального сервера: абсолютные пути (/styles.css, /assets/…) должны резолвиться.
python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
SERVER=$!
PROFILE="$(mktemp -d)"
trap 'kill "$SERVER" 2>/dev/null; wait "$SERVER" 2>/dev/null || true; rm -rf "$PROFILE"' EXIT
sleep 1

print_pdf() {
    local path="$1" out="$2"
    "$CHROME" --headless=new --disable-gpu --no-first-run --no-default-browser-check \
        --user-data-dir="$PROFILE" --no-pdf-header-footer --virtual-time-budget=8000 \
        --print-to-pdf="$ROOT/$out" "http://127.0.0.1:$PORT/$path" 2>/dev/null
    echo "ok: $out"
}

print_pdf ""       resume-ru.pdf
print_pdf "en/cv/" resume-en.pdf
