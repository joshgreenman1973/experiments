# SCOTUS puppets

Turns a complete U.S. Supreme Court oral argument into a puppet video. Muppet-style 3D caricatures of the nine justices and the advocates are lip-synced to the Court's own unedited audio, with captions, name tags and chapter cards. The output is a full-length MP4, a highlight clip, and a self-contained web player you can publish as a private page.

First run: *United States v. Rahimi* (No. 22-915, argued Nov. 7, 2023), 92:49. `docs/cast_sheet.jpg` shows the puppets.

## Quick start

```bash
./setup.sh               # once: Python 3.13 venv with Blender-as-a-module (bpy 5.2.2), OpenCV, SciPy. Needs ffmpeg.
# edit case.json for the argument you want
./run.sh fetch           # transcript + audio                                   ~1 min
./run.sh lineup          # cast sheet for a likeness check: work/lineup/cast_sheet.png   ~4 min
./run.sh assets          # courtroom plates + puppet layers                      ~75 min on 4 CPU cores
./run.sh timeline        # lip-sync, head motion, edit list, captions            ~1 min
./run.sh highlight       # the excerpt named in case.json: work/highlight/final.mp4      ~2 min
./run.sh video           # the full argument: work/full/final.mp4                ~35 min
./run.sh web             # compact copy in 13 MB pieces + player: work/web/       ~20 min
```

Steps skip files that already exist, so a crashed or edited run resumes cheaply. To re-render one puppet after changing its look, delete `work/assets/<name>/` and the `<name>_*` files in `work/assets/wide/`, then run `assets` again. Everything generated lives in `work/` (ignored by git).

In a Claude Code session, the skill at `.claude/skills/scotus-puppets/SKILL.md` walks Claude through the same steps.

## Doing a different argument

Everything case-specific is in `case.json`:

| Field | What it does |
|---|---|
| `term`, `docket`, `hearing` | Which Oyez transcript to fetch (`hearing` defaults to `"01"`; use `"02"` for a second argument). |
| `case_name`, `short_name`, `argued`, `argued_short`, `decided`, `outcome`, `oyez_url` | Text for the title card, corner label, end card and web page. |
| `advocates` | One entry per lawyer. `oyez` must match the speaker name `fetch` prints exactly. `spec` is the puppet: skin, hair style and color, face shape, brows, suit. Copy an existing one and adjust. |
| `sections` | Chapter card shown at the start of each section of the argument (opening, response, rebuttal). |
| `highlight` | Start and end seconds plus a label for the excerpt clip. |
| `web` | Page title, dek, chapter list (seconds, text, optional quote) and an optional note, such as flagging a stand-in puppet. |
| `glasses` | `{"justice_key": {"hex": "#3a3a3a"}}` puts frames on a puppet. |
| `bench_order`, `justices` | Only for a different Court. The defaults are the nine who sat from June 2022 (Jackson's arrival) on. For an older term, add specs for the other justices (see `scripts/characters.py`) and list the bench as seen from the gallery, left to right. Associates alternate outward from the Chief by seniority: the most senior sits at the Chief's right (gallery left), the second most senior at the Chief's left, and so on. For 2023 that gives Barrett, Gorsuch, Sotomayor, Thomas, Roberts, Alito, Kagan, Kavanaugh, Jackson. |

The justices' puppets are in `scripts/characters.py`. Run `lineup` and look at the cast sheet before the 75-minute `assets` step.

## How it works

1. **Sources** (`scripts/fetch.py`). From Claude's cloud sandbox, oyez.org and supremecourt.gov are blocked, so the transcript comes from the [walkerdb/supreme_court_transcripts](https://github.com/walkerdb/supreme_court_transcripts) mirror of the Oyez API (speaker turns with timestamps), and the audio comes from the Oyez S3 link stored in that transcript.
2. **Puppets** (`scripts/puppet.py`). Each head is a lofted mesh split at the mouth into an upper head and a hinged jaw, with fleece shading, short "fuzz" fibers, ping-pong-ball eyes with lids, and procedurally groomed fur hair (side part, bob, long, buzz, locs). Bodies are robes with a white shirt V and arms resting on the bench.
3. **Set and cameras** (`scripts/court.py`). The courtroom has an arced mahogany bench, tall leather chairs, red velvet drapes, fluted marble columns, the clock at 10:00, the lectern with its white and red lights, and a gallery of background puppets. Cameras: a wide shot from the gallery, a close-up per justice from the lectern, and a close-up per advocate from the bench.
4. **Layers** (`scripts/render_assets.py`, Cycles on CPU). Per camera there is an empty plate, plus per character a body layer and five head layers at different jaw angles. The bench and lectern are rendered as holdouts, so occlusion is exact, and heads can move in 2D on top.
5. **Performance** (`scripts/timeline.py`). Within each speaker's Oyez turn, the band-passed loudness envelope (35 ms windows, 24 fps, mouth leading the sound by 45 ms) picks one of the five jaw positions. Head tilt, bob and sway follow speech energy, and listeners nod now and then. Edit rules: close-up on whoever talks for more than 2.2 seconds, bench cutaways every 10 to 19 seconds during long answers, an advocate reaction shot inside long questions.
6. **Compositing** (`scripts/compose.py`, `scripts/assemble.sh`). OpenCV composites the layers with drop shadows, captions with speaker labels, name tags, chapter cards, a title card and an end card. Four processes encode chunks in parallel, which are then joined and muxed with the original audio.
7. **Web player** (`web/template.html`, `scripts/build_web.py`). Artifact hosting caps files at 15 MB, so the video ships as 330-second MP4 pieces. Two `<video>` elements trade places at each boundary, giving one seamless 90-minute timeline with chapters, per-speaker jump links and resume-where-you-left-off.

## Publishing

- The full MP4 (about 300 MB) is over the 30 MiB file limit for sending in chat. `run.sh web` makes a compact copy (CRF 27, 64 kbps mono audio, about 200 MB) cut into pieces under 13 MB.
- To publish, ask Claude to publish `work/web/index.html` as an Artifact with `poster.jpg` and `v/p*.mp4` as files, about four pieces per publish (each publish is capped at 64 MB, and a page at 256 MB total). Artifacts are private until you share them.

## Things learned the hard way

- The Gemini key bundled with the Nano Banana image skill is on Google's free tier, with zero image-generation quota, so AI-generated likenesses weren't possible. A paid key could make photo-style portrait sprites, but the 3D route keeps jaws and camera angles consistent.
- Two `render_assets.py` processes running at once overwrite each other's `meta.json`. `run.sh assets` finishes with a render-free pass that writes complete metadata to `work/meta/`, and the compositor reads that copy.
- Justice close-ups were framed with little headroom. The compositor shifts them down 70 px and extends the blurred background upward, which costs nothing and avoids a re-render.
- Fair-skinned puppets wash out under the lectern key light, so advocate cameras render at −0.35 EV.
- The sandbox's Chromium can't decode H.264. To test the web player there, transcode a few pieces to WebM.
- None of the 2022–present justices wears glasses in the official portraits, so none have them by default.

## Credits

Audio and transcript timing come from [Oyez](https://www.oyez.org), licensed CC BY-NC 4.0: noncommercial use with attribution, which the end card and page carry. The puppets are caricatures and the on-screen label says so.
