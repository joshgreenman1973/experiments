---
name: puppet-interview
description: Animate a recorded interview, roundtable or panel (for example an editorial-board meeting) with Muppet-style 3D puppets of the real participants, seated in a re-creation of the room and lip-synced to the recording, with captions and chapters from the published transcript, published as a private web page. Use when given an audio recording plus a transcript and photos of the people and asked to turn it into a puppet animation. For Supreme Court arguments use the scotus-puppets skill instead.
---

# Puppet interview

It shares the puppets, renderer and browser player with the court pipeline in `scotus-puppets/`. Its own scripts are in `scotus-puppets/interview/`. Read `scotus-puppets/docs/PLAYBOOK.md` sections 1, 2, 4 and 5 before starting. The first one made was the New York Editorial Board's breakfast with Rep. Mike Lawler.

## What to get from the user before rendering anything

- The audio as a mono MP3 small enough to upload.
- Whisper JSON with word timestamps, run on their machine. Raw and uncorrected is fine.
- The published transcript, where each turn starts with the speaker's full name.
- One color, recent photo per person. Ask about facial hair, glasses and clothing rather than guessing.
- A photo of the room.

## Runbook

1. `cd scotus-puppets && ./setup.sh` if `bvenv/` is missing. Pick a work folder and `export W=work/<name>`, then put `audio.mp3`, `whisper.json` and `transcript.txt` in it. `chapters.json` is optional; see `interview/chapters_lawler.json`.
2. The interview scripts still hard-code the Lawler cast. Before anything else, move the cast into one config, or edit these consistently:
   - `align.py` `SPEAKERS`;
   - `build.py` `KEYS`, `LABEL`, `DISPLAY`;
   - `cast.py`;
   - `breakfast.py` (seats and room);
   - `run.sh` `KEYS`.
3. `python interview/align.py`, then `python interview/build.py`.
   - The cut rule: chatter before and after the interview goes; untranscribed speech of 10 s or more goes; shorter asides stay.
   - Show the user `cuts_report.md`.
4. Likenesses: write the specs in `cast.py` (keys in PLAYBOOK section 4), then run `interview/run.sh lineup` and show the cast sheet beside the photos. Iterate until the user is happy.
5. The set: edit `breakfast.py` from the room photo, then run `interview/run.sh preview` and show a still. A long table with everyone on the far side and the ends is easiest to animate.
6. `interview/run.sh assets` (hours; one Blender process; resumable), then `meta`, `check` and `export`.
7. `python interview/finish_page.py`, `python interview/validate.py`, then `node interview/web_check.js $W/page $W/page_check`.
8. Publish `$W/page/` as a new, private Artifact. Credit line: "Made by Josh Greenman with Claude."

## Rules of thumb

- The court-only player effects (listener motion, blinks, mouse, clock) stay off unless the user asks for them on this project. Leaving `page.motion` out of the page data keeps them off.
- When a court project runs in the same session, label every update with the project it's about.
- Commit code only. Never commit the audio, the transcript, photos or renders; the repo is public.
