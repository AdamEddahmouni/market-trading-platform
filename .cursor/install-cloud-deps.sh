#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python3.11 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install tzdata numpy pymongo scikit-learn

if [ -f ui/package-lock.json ]; then
  (cd ui && npm ci)
elif [ -f ui/package.json ]; then
  (cd ui && npm install)
fi

echo "Cloud dependencies installed: Python $(python --version), Node $(node --version)"
