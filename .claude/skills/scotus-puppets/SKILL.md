---
name: scotus-puppets
description: Make a puppet reenactment of a complete U.S. Supreme Court oral argument (Muppet-style 3D caricatures of the justices and advocates lip-synced to the real Oyez audio, with captions) and publish it as a private web page. Use when asked to redo the Rahimi puppet video, animate another Supreme Court argument with puppets, change a puppet's look, or rebuild the video or its web player.
---

# SCOTUS puppets

The pipeline lives in `scotus-puppets/`. Read `scotus-puppets/README.md` first; it has the step list, timings, `case.json` fields and known pitfalls.

## Runbook

1. `cd scotus-puppets && ./setup.sh` (needs ffmpeg; installs bpy 5.2.2 into `bvenv/`).
2. Edit `case.json` for the argument. For a new case, set `term` and `docket`, then run `./run.sh fetch`. It prints the speakers' Oyez names; every advocate in `case.json` needs an `oyez` value matching one exactly, plus a puppet `spec` (copy one and adjust skin, hair and suit). Cases from before June 2022 also need `bench_order` and extra `justices` specs.
3. `./run.sh lineup`, then send the user `work/lineup/cast_sheet.png` and fix likeness complaints before the long render. Base likeness on skin tone, hair color, texture and style, face shape and brows, with glasses only when the person actually wears them.
4. `./run.sh assets` takes about 75 minutes on 4 cores. Run it in the background and watch `work/assets/` fill.
5. `./run.sh timeline`, then `./run.sh highlight`. Send the highlight (under 30 MiB) as an early look.
6. `./run.sh video` (about 35 minutes). The full file is too big to send in chat; say so instead of trying.
7. `./run.sh web`, then publish `work/web/index.html` as an Artifact with `poster.jpg` and `v/p*.mp4` in `files`, about four pieces per publish to the same file path. Keep it private; the puppets depict real people, so sharing is the user's call.

## Rules of thumb

- Check one composited frame from each new camera or puppet before a long render or encode.
- Audio and transcript are CC BY-NC 4.0 from Oyez; keep the attribution on the end card and page.
- Commit code changes to the repo, never the rendered media; the repo is public and published as a site.
