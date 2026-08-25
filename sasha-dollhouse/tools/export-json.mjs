// Exports the app's content (characters, scenes, phrase builds, number
// things) to JSON so the iOS port can generate Swift from the same source
// of truth the web app uses, rather than anyone retyping 23 scenes.
import { readFileSync, writeFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
function slice(name, open, close){
  const start = html.indexOf(`const ${name} = ${open}`);
  const end = html.indexOf(`\n${close};`, start);
  return html.slice(start, end + close.length + 2);
}
const src = [
  slice('CHARS','{','}'), slice('SCENES','[',']'),
  slice('BUILDS','[',']'), slice('THINGS','[',']'), slice('ROOMS','[',']'),
].join('\n');
const { CHARS, SCENES, BUILDS, THINGS, ROOMS } =
  new Function(src + '\nreturn {CHARS, SCENES, BUILDS, THINGS, ROOMS};')();
writeFileSync(join(root, 'tools/content.json'),
  JSON.stringify({ CHARS, ROOMS, SCENES, BUILDS, THINGS }, null, 1));
console.log(`rooms ${ROOMS.length}  scenes ${SCENES.length}  chars ${Object.keys(CHARS).length}  builds ${BUILDS.length}`);
let beats = 0, picks = 0, lines = 0;
for (const s of SCENES) for (const b of s.beats) {
  beats++;
  if (b.say) lines++;
  if (b.pick) { picks++; for (const p of b.pick) { lines++; if (p.reply) lines++; } }
}
console.log(`beats ${beats}  choice points ${picks}  spoken lines ${lines}`);
