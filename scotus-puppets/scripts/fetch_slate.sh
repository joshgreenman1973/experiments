#!/bin/bash
# Fetch transcript, Oyez case record and audio for each docket in a slate.
# Usage: fetch_slate.sh WORKROOT TERM DOCKET...   (writes WORKROOT/cases/<docket>/{transcript,case}.json + audio.mp3)
# Source: the walkerdb/supreme_court_transcripts mirror of the Oyez API (oyez.org itself is blocked from Claude's sandbox).
S=$1; TERM_=$2; shift 2
B=https://raw.githubusercontent.com/walkerdb/supreme_court_transcripts/master/oyez/cases
for d in "$@"; do
  D=$S/cases/$d; mkdir -p "$D"
  [ -s "$D/transcript.json" ] || curl -sf --retry 3 --max-time 120 -o "$D/transcript.json" "$B/$TERM_.$d-t01.json" || { echo "$d: no transcript in the mirror"; continue; }
  [ -s "$D/case.json" ] || curl -sf --retry 3 --max-time 120 -o "$D/case.json" "$B/$TERM_.$d.json"
  url=$(python3 -c "import json;print([m['href'] for m in json.load(open('$D/transcript.json'))['media_file'] if m and m.get('mime')=='audio/mpeg'][0])")
  [ -s "$D/audio.mp3" ] || curl -sf --retry 3 --max-time 900 -o "$D/audio.mp3" "$url"
  echo "$d $(du -h "$D/audio.mp3" | cut -f1) $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$D/audio.mp3")s"
done
