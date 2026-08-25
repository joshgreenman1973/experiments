#!/usr/bin/env python3
"""Generate one mp3 per line in tools/lines.json using edge-tts neural voices.
Each character gets a distinct voice; skips files that already exist.
Run from the project root: python3 tools/generate-audio.py
"""
import asyncio, json, os, sys
import edge_tts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The cast.
#
# Two rules, learned the hard way. First, prefer the Conversation-tier
# voices over the News/Novel ones: newsreader voices are trained to read
# copy at a camera, and they make a friend saying "come in, come in" sound
# like a bulletin. Second, keep pitch shifting near zero. Shifting a neural
# voice by 20-25Hz is what makes it sound like a machine — it resamples
# away exactly the breath and warmth the model produced. Characters are
# told apart by timbre and pace instead, which costs nothing.
VOICES = {
    'en': {
        'you':      ('en-US-AnaNeural',               '+0%',  '+0Hz'),   # a real child voice
        'poppy':    ('en-US-AvaMultilingualNeural',   '+5%',  '+0Hz'),   # bright, warm cat
        'pim':      ('en-US-EmmaMultilingualNeural',  '+6%',  '+0Hz'),
        'coco':     ('en-US-JennyNeural',             '+2%',  '+6Hz'),   # bright bird
        'gertrude': ('en-US-MichelleNeural',          '+3%',  '+0Hz'),
        'bo':       ('en-US-AndrewMultilingualNeural','-6%',  '+0Hz'),   # calm doctor
        'mo':       ('en-US-BrianMultilingualNeural', '-10%', '-6Hz'),   # big soft monster
        'bart':     ('en-US-BrianNeural',             '+7%',  '+0Hz'),   # same family as Mo,
                                                                        # much quicker, so the
                                                                        # two never blur
        'uno':      ('en-US-RogerNeural',             '-2%',  '+0Hz'),   # precise
        'house':    ('en-US-AvaMultilingualNeural',   '-8%',  '+0Hz'),   # the house murmurs
    },
    # Spanish used to be two voices for the whole cast, so every girl in the
    # house sounded like the same person. Four now, split the same way the
    # English side is.
    'es': {
        'you':      ('es-US-PalomaNeural',            '+4%',  '+0Hz'),
        'poppy':    ('es-MX-DaliaNeural',             '+4%',  '+0Hz'),
        'pim':      ('es-US-PalomaNeural',            '+6%',  '+0Hz'),
        'coco':     ('es-MX-DaliaNeural',             '+0%',  '+6Hz'),
        'gertrude': ('es-US-PalomaNeural',            '+2%',  '+0Hz'),
        'bo':       ('es-MX-JorgeNeural',             '-6%',  '+0Hz'),
        'mo':       ('es-US-AlonsoNeural',            '-10%', '-6Hz'),
        'bart':     ('es-US-AlonsoNeural',            '+7%',  '+0Hz'),
        'uno':      ('es-MX-JorgeNeural',             '+0%',  '+0Hz'),
        'house':    ('es-MX-DaliaNeural',             '-8%',  '+0Hz'),
    },
}

def voice_for(who, lang):
    table = VOICES.get(lang, VOICES['en'])
    return table.get(who, table['you'])

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
