#!/bin/bash
# Editorial-board breakfast interview: puppets, set, layers, web export. Independent of the Supreme Court pipeline.
#   interview/run.sh lineup   seven-puppet likeness sheet                         -> $W/cast_sheet.png     (~4 min)
#   interview/run.sh preview  low-res wide + close-ups of the set                 -> $W/prev/              (~3 min)
#   interview/run.sh assets   plates + layers (wide and 7 close-ups), 2 workers   -> $W/assets/           (~70 min on 4 cores)
#   interview/run.sh meta     render-free pass that writes complete metadata      -> $W/meta/meta.json
#   interview/run.sh check    composited wide_check.png / closeups_check.png      -> $W/
#   interview/run.sh export   browser images + layout.json                        -> $W/page/
# Re-running skips files that exist. W defaults to ./work/interview.
set -euo pipefail
cd "$(dirname "$0")/.."
HERE=$PWD
W=${W:-$HERE/work/interview}; export W
PY=$HERE/bvenv/bin/python
KEYS=smith,gelinas,greenman,lawler,katz,zagare,facciola
mkdir -p "$W"
step=${1:-all}

lineup()  { mkdir -p "$W/lineup"; SAMPLES=32 OUT="$W/lineup" $PY interview/lineup.py
            $PY interview/cast_sheet.py "$W/lineup" "$W/cast_sheet.png"; }
preview() { WORK="$W" OUT="$W/prev" SAMPLES=${SAMPLES:-16} CAMS=${CAMS:-wide,lawler,smith} RES=${RES:-960x540} $PY interview/preview.py; }
assets()  { mkdir -p "$W/assets"
            # two workers with two Cycles threads each: the serial scene-build time of one overlaps the other's sampling
            # (the workers skip existing files and write no meta.json; the meta step below is the single source of truth)
            export S_PLATE=${S_PLATE:-48} S_LAYER=${S_LAYER:-32} WORK="$W" THREADS=2 META_OUT=/dev/null
            $PY interview/render_interview.py "$W/assets" wide/ > "$W/render_wide.log" 2>&1 &
            P1=$!
            $PY interview/render_interview.py "$W/assets" smith/ gelinas/ greenman/ lawler/ katz/ zagare/ facciola/ > "$W/render_closeups.log" 2>&1 &
            P2=$!
            wait $P1 $P2; }
meta()    { mkdir -p "$W/meta"; WORK="$W" META_OUT="$W/meta/meta.json" $PY interview/render_interview.py "$W/meta" __none__ > "$W/meta.log" 2>&1
            echo "$W/meta/meta.json"; }
check()   { $PY interview/check.py "$W/assets" "$W/meta/meta.json" "$W"; }
export_() { rm -rf "$W/page"; $PY scripts/export_web.py "$W/assets" "$W/meta/meta.json" "$W/page" --advocates "" --bench $KEYS --bench-shift 0; }

case $step in
  lineup|preview|assets|meta|check) $step ;;
  export) export_ ;;
  all) lineup; assets; meta; check; export_ ;;
  *) echo "unknown step: $step"; exit 1 ;;
esac
