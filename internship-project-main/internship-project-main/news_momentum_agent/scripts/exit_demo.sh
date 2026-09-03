#!/usr/bin/env bash
# Resume live agent mode after a demo presentation.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f state/demo.lock ]]; then
  rm state/demo.lock
  echo "Demo mode OFF. You can run ./venv/bin/python main.py for live data again."
else
  echo "Demo lock not found — already in live mode."
fi
