#!/bin/zsh
# Flatten the Claude desktop app's Code sidebar (same as Filter -> Group by -> None),
# by writing the setting straight into the app's Local Storage.
# Run this from Terminal.app AFTER quitting Claude (Cmd+Q). It refuses to run while Claude is open,
# because the app rewrites Local Storage on quit and would discard the edit.
set -e
if pgrep -xq "Claude"; then
  echo "Quit the Claude app first (Cmd+Q), then run this again."; exit 1
fi
LDB="$HOME/Library/Application Support/Claude/Local Storage/leveldb"
BK="$HOME/Library/Application Support/Claude/Local Storage/leveldb.bak-$(date +%Y%m%d-%H%M%S)"
cp -R "$LDB" "$BK" && echo "Backup of the store: $BK"
W=$(mktemp -d); cd "$W"
npm init -y >/dev/null 2>&1
npm install classic-level@1 --silent
cat > setflat.mjs <<'EOF'
import { ClassicLevel } from 'classic-level';
const db = new ClassicLevel(process.argv[2], { keyEncoding: 'buffer', valueEncoding: 'buffer' });
await db.open();
const KEY = Buffer.concat([Buffer.from('_https://claude.ai'), Buffer.from([0,1]), Buffer.from('dframe-store')]);
const dec = b => b[0]===0 ? Buffer.from(b.subarray(1)).toString('utf16le') : b[0]===1 ? b.subarray(1).toString('utf8') : b.toString('utf8');
const cur = JSON.parse(dec(await db.get(KEY)));
console.log('before:', JSON.stringify(cur.state.groupByByMode));
cur.state.groupByByMode = { ...(cur.state.groupByByMode||{}), code: 'none' };
await db.put(KEY, Buffer.concat([Buffer.from([1]), Buffer.from(JSON.stringify(cur),'utf8')]));
console.log('after: ', JSON.stringify(JSON.parse(dec(await db.get(KEY))).state.groupByByMode));
await db.close();
EOF
node setflat.mjs "$LDB"
echo "Done. Open Claude: the Code sidebar is now one flat list."
