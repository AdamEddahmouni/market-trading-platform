#!/usr/bin/env bash
# One-command professor demo: seed state + launch dashboard.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Loading demo state (watchlist, signals, portfolio, options)..."
./venv/bin/python scripts/seed_demo_state.py

echo ""
echo "==> Starting dashboard at http://localhost:8501"
echo "    (main.py is NOT started — demo.lock protects your state)"
echo ""
./venv/bin/python -m streamlit run dashboard/app.py
