#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -f data/imdb.duckdb ]; then
  echo "data/imdb.duckdb is missing. Run:" >&2
  echo "  ./scripts/fetch_imdb.sh && ./.venv/bin/python scripts/build_db.py" >&2
  exit 1
fi

exec ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 "$@"
