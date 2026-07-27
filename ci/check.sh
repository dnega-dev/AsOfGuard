#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

echo "==> Running unittest suite"
python3 -m unittest discover -s "$ROOT/tests" -v

echo "==> Compiling source and tests"
python3 -m compileall -q "$ROOT/src" "$ROOT/tests"

echo "==> Smoke-testing clean CLI verdict"
python3 -m asof_guard verify --fixture clean_historical --format json >/dev/null

echo "==> Smoke-testing contaminated CLI exit code"
status=0
python3 -m asof_guard verify --fixture post_cutoff_retrieval --format sarif >/dev/null || status=$?
if [ "$status" -ne 2 ]; then
  echo "expected contaminated exit code 2, got $status" >&2
  exit 1
fi

echo "All checks passed."
