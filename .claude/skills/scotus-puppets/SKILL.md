---
name: scotus-puppets
description: Make a puppet reenactment of a complete U.S. Supreme Court oral argument, or a whole term of them, as a private web page. Muppet-style 3D caricatures of the justices and the lawyers are lip-synced to the real Oyez audio, with captions, chapters and quotes from the decision. Use when asked to redo the Rahimi or OT2025 puppet pages, animate another Supreme Court argument or term with puppets, change a puppet's look, or rebuild the player.
---

# SCOTUS puppets

The pipeline lives in `scotus-puppets/`. Read `scotus-puppets/docs/PLAYBOOK.md` first: it holds the settings that worked, the likeness rules and the mistakes to avoid. `scotus-puppets/README.md` has the step-by-step commands and the `case.json` fields. For a recorded interview or roundtable instead of a court argument, use the `puppet-interview` skill.

## Runbook (browser-player route; the MP4 route is in the README)

1. `cd scotus-puppets && ./setup.sh` (Python 3.13 and bpy 5.2.2 in `bvenv/`; needs ffmpeg). Locally or in the cloud.
2. For one argument, edit `case.json` and run `./run.sh fetch`. For a slate, write `slates/<name>.json` like `slates/ot2025.json`.
3. Likenesses:
   - Lawyers without photos become felt stand-ins.
   - For anyone the user sends a photo of, add an `advocate_overrides` entry, keyed by the exact Oyez name.
   - Justices live in `scripts/characters.py`; Thomas and Jackson wear glasses.
   - Render a labeled lineup sheet beside the photos and get the user's OK before the long render.
4. `./run.sh assets` for the justices if they aren't rendered yet, then `./slate.sh slates/<name>.json WORKROOT`. That covers lawyers, blink and gallery layers, timelines, `export_web --motion` and `build_page`. Run it in the background, one Blender process at a time.
5. Decision notes:
   - Get the opinions from CourtListener's S3 bucket and convert them with pdftotext.
   - Write notes tied to the justices' questions, then keep only quotes that `verify_notes.py` finds word for word.
   - Write outcomes from the opinion text, never from search summaries.
6. `assemble_theater.py` builds the screening room. Test it in headless Chromium using MP3 audio, since the sandbox can't decode AAC. Then publish as a private Artifact in batches under 64 MB and 255 files, republishing only changed files on rebuilds.

## Rules of thumb

- Check one composited frame from each new camera or puppet before a long render.
- When another project is running in the same session, label every update with the project it's about, and keep each project's instructions to that project.
- Credit Oyez (CC BY-NC 4.0) and CourtListener on the page. Credit line: "Made by Josh Greenman with Claude."
- Commit code, never rendered media or private artifact URLs. The repo is public.
