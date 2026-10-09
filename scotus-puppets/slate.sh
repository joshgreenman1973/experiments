#!/bin/bash
# A whole slate of arguments as browser-player pages (no video encoding). See README, "Doing a whole term".
#   ./slate.sh slates/ot2025.json [WORKROOT]
# Steps (each skips work already done): fetch -> configs + stand-in lawyers -> render lawyers -> timelines -> pages.
# Needs the justices' layers in WORKROOT/assets (./run.sh assets with any case argued before the same nine renders them).
set -euo pipefail
cd "$(dirname "$0")"
SLATE=$1; WORK=${2:-$PWD/work}; export WORK
PY=$PWD/bvenv/bin/python
TERM_=$($PY -c "import json;print(json.load(open('$SLATE'))['term'])")
DOCKETS=$($PY -c "import json;print(' '.join(c['docket'] for c in json.load(open('$SLATE'))['cases']))")

scripts/fetch_slate.sh "$WORK" "$TERM_" $DOCKETS
$PY scripts/slate.py "$SLATE" "$WORK"

# lawyers: every advocate shares one lectern background; only their own layers render (~3 min each on 4 cores)
KEYS=$($PY -c "import json;print(' '.join(json.load(open('$WORK/advocates.json'))))")
# the lectern background: any real (non-symlink) advocate close-up plate already rendered, e.g. from ./run.sh assets
LECTERN=${LECTERN:-$($PY -c "
import os, sys; sys.path.insert(0, 'scripts'); import characters as c
a = '$WORK/assets'
print(next(os.path.join(a, d, 'plate.png') for d in sorted(os.listdir(a)) if d not in c.BENCH_ORDER + ['wide']
           and os.path.isfile(os.path.join(a, d, 'plate.png')) and not os.path.islink(os.path.join(a, d, 'plate.png'))))")}
for k in $KEYS; do mkdir -p "$WORK/assets/$k"; [ -e "$WORK/assets/$k/plate.png" ] || ln -s "$(realpath "$LECTERN")" "$WORK/assets/$k/plate.png"; done
SCOTUS_CASE=$WORK/slate_case.json S_LAYER=${S_LAYER:-32} $PY scripts/render_assets.py "$WORK/assets" $(for k in $KEYS; do printf "wide/%s_ %s/%s_ " $k $k $k; done)
mkdir -p "$WORK/meta_slate"; SCOTUS_CASE=$WORK/slate_case.json $PY scripts/render_assets.py "$WORK/meta_slate" __none__ >/dev/null

# the browser player's motion extras (each pass skips files that exist; SKIP_MOTION_RENDERS=1 leaves them out, and the pages then just don't blink etc.):
#  - eyes-closed heads (head5) for every justice and lawyer, for blinks; they reuse the crops the open-eye renders recorded in assets/meta.json
#  - the audience behind the lawyer as separate layers over an empty lectern background (once, shared by every case)
if [ -z "${SKIP_MOTION_RENDERS:-}" ]; then
  BLINK=1 SCOTUS_CASE=$WORK/slate_case.json S_LAYER=${S_LAYER:-32} $PY scripts/render_assets.py "$WORK/assets"
  GALLERY=1 ONLY=${KEYS%% *} SCOTUS_CASE=$WORK/slate_case.json S_LAYER=${S_LAYER:-32} $PY scripts/render_assets.py "$WORK/assets"
fi

for d in $DOCKETS; do
  C=$WORK/cases/$d; mkdir -p "$C/page"
  [ -s "$C/tl_web.json" ] || NO_MOTION=1 SCOTUS_CASE=$C/cfg.json $PY scripts/timeline.py "$C/transcript.json" "$C/audio.mp3" "$C/tl.npz" "$C/tl.json" "$C/tl_web.json"
  ADVS=$($PY -c "import json;print(','.join(json.load(open('$C/cfg.json'))['advocates']))")
  SCOTUS_CASE=$C/cfg.json $PY scripts/export_web.py "$WORK/assets" "$WORK/meta_slate/meta.json" "$C/page" --advocates "$ADVS" --motion
  $PY scripts/build_page.py "$C/cfg.json" "$C/transcript.json" "$C/audio.mp3" "$C/tl_web.json" "$C/page" \
      $( [ -s "$C/outcome.json" ] && echo --outcome "$C/outcome.json" )
done
echo "Pages are in $WORK/cases/<docket>/page/. Publish each (index.html plus its files), then:"
echo "  $PY scripts/build_index.py $SLATE $WORK URLS.json $WORK/index.html"
