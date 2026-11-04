#!/usr/bin/env bash
# PDF-версии резюме: страницы печатаются headless Chrome прямо с диска.
# Запуск: ./scripts/build.sh  (нужен Google Chrome; шрифты подтянутся из сети, если она есть)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
PROFILE="$(mktemp -d)"
trap 'rm -rf "$PROFILE"' EXIT

print_pdf() {
    local page="$1" out="$2"
    "$CHROME" --headless=new --disable-gpu --no-first-run --no-default-browser-check \
        --user-data-dir="$PROFILE" --no-pdf-header-footer --virtual-time-budget=8000 \
        --print-to-pdf="$ROOT/$out" "file://$ROOT/$page" 2>/dev/null
    echo "ok: $out"
}

print_pdf index.html       resume-ru.pdf
print_pdf en/cv/index.html resume-en.pdf
