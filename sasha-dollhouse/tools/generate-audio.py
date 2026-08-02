#!/usr/bin/env python3
"""Generate one mp3 per line in tools/lines.json using edge-tts neural voices.
Each character gets a distinct voice; skips files that already exist.
Run from the project root: python3 tools/generate-audio.py
"""
import asyncio, json, os, sys
import edge_tts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VOICES = {
    'en': {
        'you':      ('en-US-AnaNeural',        '+0%',  '+0Hz'),   # a real child voice
        'poppy':    ('en-US-JennyNeural',      '+4%',  '+15Hz'),
        'bo':       ('en-US-ChristopherNeural','-8%',  '+0Hz'),   # calm doctor
        'pim':      ('en-US-EmmaNeural',       '+4%',  '+20Hz'),
        'mo':       ('en-US-GuyNeural',        '-10%', '-15Hz'),  # big soft monster
        'uno':      ('en-US-EricNeural',       '-4%',  '+5Hz'),   # precise
        'coco':     ('en-US-AriaNeural',       '+6%',  '+25Hz'),  # bright bird
        'gertrude': ('en-US-MichelleNeural',   '+2%',  '+15Hz'),
        'bart':     ('en-US-BrianNeural',      '+2%',  '+10Hz'),
        'house':    ('en-US-JennyNeural',      '-10%', '-10Hz'),  # the house murmurs
    },
    'es': {
        '_female':  ('es-MX-DaliaNeural',      '+0%',  '+10Hz'),
        '_male':    ('es-MX-JorgeNeural',      '-6%',  '+0Hz'),
    },
}
ES_MALE = {'bo', 'mo', 'uno', 'bart'}

def voice_for(who, lang):
    if lang == 'es':
        return VOICES['es']['_male' if who in ES_MALE else '_female']
    return VOICES['en'].get(who, VOICES['en']['you'])

async def gen(sem, e):
    path = os.path.join(ROOT, e['f'])
    if os.path.exists(path) and os.path.getsize(path) > 500:
        return True
    v, rate, pitch = voice_for(e['w'], e['l'])
    async with sem:
        for attempt in range(3):
            try:
                await edge_tts.Communicate(e['t'], v, rate=rate, pitch=pitch).save(path)
                return True
            except Exception as ex:
                if attempt == 2:
                    print(f"FAIL {e['f']} {e['w']}|{e['t'][:40]}: {ex}", flush=True)
                    return False
                await asyncio.sleep(2 * (attempt + 1))

async def main():
    with open(os.path.join(ROOT, 'tools/lines.json')) as f:
        entries = json.load(f)
    sem = asyncio.Semaphore(6)
    results = await asyncio.gather(*[gen(sem, e) for e in entries])
    ok = sum(1 for r in results if r)
    print(f"done: {ok}/{len(entries)} generated", flush=True)
    if ok < len(entries):
        sys.exit(1)

asyncio.run(main())
