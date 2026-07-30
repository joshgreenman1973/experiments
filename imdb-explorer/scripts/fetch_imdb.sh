#!/usr/bin/env bash
# Download the IMDb bulk datasets (free, non-commercial use).
# https://developer.imdb.com/non-commercial-datasets/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="$ROOT/data/raw"
mkdir -p "$RAW"

FILES=(name.basics title.basics title.principals title.ratings)

for f in "${FILES[@]}"; do
  out="$RAW/$f.tsv.gz"
  echo "==> $f.tsv.gz"
  curl -fL --retry 3 --retry-delay 2 -o "$out.part" \
    "https://datasets.imdbws.com/$f.tsv.gz"
  # Fail loud: a truncated or HTML error page is not a dataset.
  if ! gzip -t "$out.part" 2>/dev/null; then
    echo "FATAL: $f.tsv.gz is not a valid gzip file (download failed)." >&2
    rm -f "$out.part"
    exit 1
  fi
  size=$(stat -f%z "$out.part")
  if [ "$size" -lt 1000000 ]; then
    echo "FATAL: $f.tsv.gz is only ${size} bytes -- refusing to accept it." >&2
    rm -f "$out.part"
    exit 1
  fi
  mv "$out.part" "$out"
  echo "    ok  $(du -h "$out" | cut -f1)"
done

echo
echo "All four datasets downloaded to $RAW"
