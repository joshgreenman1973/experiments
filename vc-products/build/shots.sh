#!/bin/zsh
# Screenshots each product's live page into vc-products/private/shots/<name>.jpg.
# Usage: zsh vc-products/build/shots.sh   (reads private/items.json; skips existing unless FORCE=1)
DIR=${0:A:h:h}
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TMP=$(mktemp -d)
python3 -c "
import json,sys
for p in json.load(open('$DIR/private/items.json')):
    u=p.get('screenshotUrl') or p.get('url')
    if u: print(p['name'], u)
" | while read name url; do
  out="$DIR/private/shots/$name.jpg"
  [[ -f $out && -z $FORCE ]] && continue
  "$CHROME" --headless=new --use-angle=swiftshader --enable-unsafe-swiftshader --hide-scrollbars --window-size=1440,900 --timeout=20000 \
    --user-data-dir="$TMP/profile" --screenshot="$TMP/$name.png" "$url" >/dev/null 2>&1 &
  pid=$!; for i in {1..45}; do kill -0 $pid 2>/dev/null || break; sleep 1; done
  kill -0 $pid 2>/dev/null && { pkill -P $pid; kill $pid; sleep 1; }
  if [[ -f $TMP/$name.png ]]; then
    sips -s format jpeg -s formatOptions 55 --resampleWidth 720 "$TMP/$name.png" --out "$out" >/dev/null && echo "ok  $name"
  else echo "ERR $name $url"; fi
done
rm -rf $TMP
