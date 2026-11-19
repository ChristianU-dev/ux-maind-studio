#!/usr/bin/env bash
# 1-Click Installer for UX-mAInd Studio on Linux & macOS (US-75)
set -euo pipefail
cd "$(dirname "$0")"

echo "=== UX-mAInd Studio · 1-Click Setup (Linux / macOS) ==="

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: python3 (>= 3.11) not found in PATH." >&2
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "[1/3] Creating virtual environment (.venv) ..."
  "$PYTHON_BIN" -m venv .venv
else
  echo "[1/3] Reusing existing .venv."
fi

echo "[2/3] Installing UX-mAInd & OSI-licensed dependencies ..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .

if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 && [ -f "frontend/package.json" ]; then
  echo "[3/3] Node.js detected — building frontend bundle ..."
  npm install --prefix frontend --no-audit --no-fund
  (cd frontend && node build.mjs)
else
  echo "[3/3] Using pre-bundled local web assets (Node.js not required at runtime)."
fi

echo ""
echo "Setup complete! Launch UX-mAInd Studio anytime via:"
echo "  .venv/bin/ux-maind"
