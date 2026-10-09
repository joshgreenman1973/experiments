# Download the Oyez transcript (speaker turns with timestamps) and the argument audio for the case in case.json.
# Usage: python fetch.py CASE.json WORKDIR
# Sources: oyez.org and supremecourt.gov were blocked from Claude's cloud sandbox, so this uses
#   - transcript: the walkerdb/supreme_court_transcripts GitHub mirror of the Oyez API (updated weekly)
#   - audio: the Oyez S3 bucket link stored in that transcript's media_file field
import json, os, sys, urllib.request

case_path, work = sys.argv[1], sys.argv[2]
case = json.load(open(case_path))
os.makedirs(work, exist_ok=True)
hearing = case.get('hearing', '01')
url = ('https://raw.githubusercontent.com/walkerdb/supreme_court_transcripts/master/oyez/cases/'
       f"{case['term']}.{case['docket']}-t{hearing}.json")
print('transcript:', url)
raw = urllib.request.urlopen(url, timeout=60).read()
tr = json.loads(raw)
if not tr or not tr.get('transcript'):
    sys.exit('No transcript in the mirror for this case yet (it updates weekly). Check term/docket in case.json.')
open(os.path.join(work, 'transcript.json'), 'wb').write(raw)
mp3 = [m['href'] for m in (tr.get('media_file') or []) if m and m.get('mime') == 'audio/mpeg']
if not mp3:
    sys.exit('Transcript has no mp3 link.')
print('audio:', mp3[0])
dst = os.path.join(work, 'audio.mp3')
with urllib.request.urlopen(mp3[0], timeout=600) as r, open(dst, 'wb') as f:
    while True:
        b = r.read(1 << 20)
        if not b:
            break
        f.write(b)
turns = [t for s in tr['transcript']['sections'] for t in s['turns']]
names = sorted({(t.get('speaker') or {}).get('name') for t in turns} - {None})
print(f"{len(turns)} turns, {turns[-1]['stop'] / 60:.1f} min; speakers:")
for n in names:
    print('  ', n)
