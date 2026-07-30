#!/usr/bin/env bash
# Double-click this file in Finder to start the explorer and open it.
cd "$(dirname "$0")"

if [ ! -f data/imdb.duckdb ]; then
  echo "The database is missing. Rebuild it with:"
  echo "  ./scripts/fetch_imdb.sh && ./.venv/bin/python scripts/build_db.py"
  echo
  read -r -p "Press return to close."
  exit 1
fi

PORT=8077
echo "Starting IMDb Explorer on http://127.0.0.1:$PORT"
echo "Close this window (or press control-C) to stop it."
echo

./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT" &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT

# Give uvicorn a moment to bind before the browser goes looking for it.
for _ in $(seq 1 40); do
  curl -fs -o /dev/null "http://127.0.0.1:$PORT/" && break
  sleep 0.25
done
open "http://127.0.0.1:$PORT"

wait $SERVER
