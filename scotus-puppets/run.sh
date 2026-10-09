#!/bin/bash
# Puppet reenactment of a Supreme Court oral argument. Edit case.json, then run the steps in order:
#   ./run.sh fetch      transcript + audio for the case                      (~1 min)
#   ./run.sh lineup     cast sheet of all puppets for a likeness check        (~4 min)  -> work/lineup/cast_sheet.png
#   ./run.sh assets     courtroom plates + puppet layers, 5 jaw positions     (~75 min on 4 CPU cores)
#   ./run.sh timeline   lip-sync envelope, head motion, edit list, captions   (~1 min)
#   ./run.sh highlight  excerpt set in case.json "highlight"                  (~2 min)  -> work/highlight/final.mp4
#   ./run.sh video      the full argument                                     (~35 min) -> work/full/final.mp4
#   ./run.sh web        compact copy cut into 13 MB pieces + player page      (~20 min) -> work/web/
#   ./run.sh all        fetch, assets, timeline, video, web
# Re-running a step skips files that already exist; delete work/assets/<name>/ to re-render one puppet.
set -euo pipefail
cd "$(dirname "$0")"
HERE=$PWD
WORK=${WORK:-$HERE/work}; export WORK
PY=$HERE/bvenv/bin/python; export PY
CASE=${SCOTUS_CASE:-$HERE/case.json}; export SCOTUS_CASE=$CASE
mkdir -p "$WORK"
step=${1:-all}

fetch()    { $PY scripts/fetch.py "$CASE" "$WORK"; }
lineup()   { mkdir -p "$WORK/lineup"; SAMPLES=32 RX=480 RY=560 OUT="$WORK/lineup" $PY scripts/lineup.py
             names=$($PY -c "import sys; sys.path.insert(0,'scripts'); import characters as c; print(' '.join(c.BENCH_ORDER + c.ADVOCATES))")
             $PY scripts/tile.py "$WORK/lineup" "$WORK/lineup/cast_sheet.png" 6 $names; echo "$WORK/lineup/cast_sheet.png"; }
assets()   { mkdir -p "$WORK/assets" "$WORK/meta"
             S_PLATE=${S_PLATE:-48} S_LAYER=${S_LAYER:-32} $PY scripts/render_assets.py "$WORK/assets"
             # layout metadata for the compositor, written by a render-free pass (safe even if renders ran in parallel)
             $PY scripts/render_assets.py "$WORK/meta" __none__ >/dev/null; }
timeline() { mkdir -p "$WORK/tl"; $PY scripts/timeline.py "$WORK/transcript.json" "$WORK/audio.mp3" "$WORK/tl/timeline.npz" "$WORK/tl/timeline.json"; }
highlight(){ read F0 F1 LABEL < <($PY -c "import json;h=json.load(open('$CASE'))['highlight'];print(round(h['start']*24),round(h['end']*24),h['label'])")
             DUR=$($PY -c "print(($F1-$F0)/24)"); FADE=$($PY -c "print($DUR-0.8)")
             rm -rf "$WORK/highlight"
             META="$WORK/meta/meta.json" AUDIO="$WORK/audio.mp3" CLIP="$F0,$F1,$LABEL" PRESET=medium CRF=22 \
               AFADE=",afade=t=in:d=0.4,afade=t=out:st=$FADE:d=0.8" scripts/assemble.sh "$WORK/assets" "$WORK/tl" "$WORK/highlight" 4 4 $F0 $F1; }
video()    { META="$WORK/meta/meta.json" AUDIO="$WORK/audio.mp3" PRESET=medium CRF=23 \
               scripts/assemble.sh "$WORK/assets" "$WORK/tl" "$WORK/full" 8 4; }
web()      { mkdir -p "$WORK/web/v"; rm -f "$WORK/web/v/"*.mp4
             # 720p at CRF 27 with 64 kbps mono audio is ~200 MB for 90 minutes: under the 256 MB artifact limit
             ffmpeg -v error -y -i "$WORK/full/final.mp4" -c:v libx264 -preset medium -crf 27 -pix_fmt yuv420p -g 96 \
               -c:a aac -b:a 64k -ac 1 -movflags +faststart "$WORK/full/compact.mp4"
             ffmpeg -v error -y -i "$WORK/full/compact.mp4" -c copy -map 0 -f segment -segment_time 330 -reset_timestamps 1 \
               -segment_format_options movflags=+faststart "$WORK/web/v/p%02d.mp4"
             ffmpeg -v error -y -ss 63 -i "$WORK/full/final.mp4" -frames:v 1 -q:v 4 "$WORK/web/poster.jpg"
             $PY scripts/build_web.py "$CASE" "$WORK/transcript.json" "$WORK/web"; }

case $step in
  fetch|lineup|assets|timeline|highlight|video|web) $step ;;
  all) fetch; assets; timeline; video; web ;;
  *) echo "unknown step: $step"; exit 1 ;;
esac
