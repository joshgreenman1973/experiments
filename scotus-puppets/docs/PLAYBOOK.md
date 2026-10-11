# Puppet transcript animations: playbook

Everything needed to make another one: what to hand Claude, the settings that worked, and what went wrong the first time. It covers two kinds of project built on the same puppets and the same browser player:

- **A court argument.** A Supreme Court oral argument, or a whole term of them, made from Oyez's recording and timed transcript. The puppets are the nine justices plus the lawyers.
- **A recorded conversation.** An interview, roundtable or panel, made from your own audio, a Whisper transcript, the published transcript and a photo of each person. The first one was the New York Editorial Board's breakfast with Rep. Mike Lawler.

The code is in `scotus-puppets/`. Two Claude Code skills drive it: `.claude/skills/scotus-puppets/` for court arguments and `.claude/skills/puppet-interview/` for conversations. Rendered media never goes in git; the repo is public.

---

## 1. How to start a new one

**Before anything else:** a new Claude Code session only sees the skills on the branch it starts from. Cloud sessions clone `main`. Until branch `claude/scotus-puppets` is merged into `main`, start a cloud session on that branch, or check it out locally (`git checkout claude/scotus-puppets`).

Start a **fresh session** for each new project instead of continuing an old one. Every step Claude takes re-reads the whole conversation, so a two-day session gets expensive (see section 8).

**What to say, court argument:**

> Use the scotus-puppets skill to animate [case name, docket number, term]. Use real likenesses for [names]; photos attached. Everyone else can be a stand-in.

For a slate: "...animate the most important 10 to 15 arguments of the [year] term as one screening-room page, with quotes from the decisions layered in."

**What to say, conversation:**

> Use the puppet-interview skill to animate this [interview / roundtable]. Attached: the audio (mono MP3), Whisper's JSON with word timestamps, the published transcript (.docx or .txt), one color photo of each person, and a photo of the room. Seat us at [kind of table] with [props].

**What to gather first**, because each of these cost a round of re-rendering last time:

| Item | Why |
|---|---|
| One **color, recent, front-facing photo** per real person | A black-and-white photo produced the wrong hair and beard colors. A 20-year-old portrait had to be aged by hand. |
| A note on anything the photo doesn't show | Facial hair or not, glasses or not, what they'd wear. Don't let Claude guess: it guessed a mustache that wasn't there, a suit and tie on a woman, and no glasses on two justices who wear them. |
| A photo of the actual room | The first set was a bright room with a round table; the real room was dark wood paneling with a long table. |
| The audio as a **mono MP3** small enough to upload | The original MP3 was too big to send in chat. `ffmpeg -i in.mp3 -ac 1 -b:a 64k out_mono.mp3` |
| **Whisper JSON with word timestamps**, run on your own machine | e.g. `whisper audio.mp3 --model medium --word_timestamps True --output_format json`. Whisper's text can stay uncorrected (mishearings, no speaker labels); the published transcript supplies the words and speakers, and Whisper supplies only the timing. |
| The **published transcript** | Each turn starts with the speaker's full name; see 5.1. |

---

## 2. Running it on your own computer instead of the cloud

Everything runs locally too. Clone the repo, check out the branch, then:

```bash
cd scotus-puppets
./setup.sh            # Python 3.13 venv in bvenv/ with bpy 5.2.2 (Blender as a Python module), numpy, scipy, pillow, opencv
```

- **Python 3.13** is required by the bpy 5.2 wheels. `uv` (`brew install uv`) makes the venv painless. If `pip install bpy==5.2.2` finds no wheel for your machine, check pypi.org/project/bpy for the platforms and Python version it supports.
- **ffmpeg** must be on PATH (`brew install ffmpeg` on a Mac). **Node** is needed for the player syntax check. **Playwright with Chromium** is optional, for the headless page tests (`web_check.js`).
- **Network:** the cloud sandbox blocks oyez.org, supremecourt.gov and many restaurant and venue sites, so the pipeline fetches from a GitHub mirror and the Oyez S3 bucket instead. That works locally as well.
- **Speed:**
  - All the published renders ran on 4 CPU cores and 15 GB of RAM: about 75 minutes for one case's eleven puppets, about 3 minutes per extra lawyer, and hours for the interview.
  - An Apple Silicon Mac could render on its GPU (Cycles' Metal backend) much faster, but the scripts currently force CPU. Ask Claude to add a GPU switch before a big local render.
- **Memory:** a slate config that builds all 39 lawyers at once needs about 8 GB, and runs crashed when two of those overlapped. `ONLY=name1,name2` limits which lawyers get built.
- **Viewing a page:** opening `index.html` straight from disk won't work. Serve the folder: `python3 -m http.server -d work/.../page 8000`, then open http://localhost:8000. The player copes with servers that ignore Range requests.
- **Publishing:** if your local Claude Code can publish Artifacts, it's the same as in the cloud (section 7). Otherwise any static host works; the page is plain files.
- **Disk:** the 14-case screening room is about 220 MB published, and the working folders were about 5 GB.

---

## 3. Court arguments

### 3.1 One argument, the original MP4 route

`README.md` covers it: `./run.sh fetch | lineup | assets | timeline | highlight | video | web`, driven by `case.json`. Use it if you want a downloadable video file. Otherwise use the browser player.

### 3.2 A slate of arguments, the browser-player route (preferred)

```bash
./slate.sh slates/ot2025.json WORKROOT
```

It runs these steps, each skipping work that's already done:

1. `scripts/fetch_slate.sh` fetches each transcript (from the walkerdb/supreme_court_transcripts mirror), the Oyez case record and the audio (Oyez S3).
2. `scripts/slate.py` writes `cases/<docket>/cfg.json`, `advocates.json` and `slate_case.json`:
   - Every lawyer gets a stand-in felt puppet: deliberately non-human colors, so nobody mistakes it for a likeness.
   - A lawyer's hair and clothes follow how the justices addressed them ("Mr." or "Ms.").
   - `advocate_overrides` in the slate file, keyed by the exact Oyez name, turns a lawyer into a photo likeness. The page's stand-in note then names who is modeled on photos.
3. `render_assets.py` renders each lawyer once (wide plus lectern close-up), reused in every case they argue.
4. The extra renders for the motion effects:
   - `BLINK=1`: an eyes-closed head per puppet and camera.
   - `GALLERY=1`: the audience as separate layers over an empty lectern background.
5. Per case:
   - `timeline.py` writes `tl_web.json`.
   - `export_web.py --motion` writes the backgrounds, sprite sheets and `layout.json`.
   - `build_page.py --outcome outcome.json --notes notes_ok.json` writes `data.json` and `index.html`.
6. `scripts/assemble_theater.py SLATE WORKROOT OUT` folds all the cases into one screening-room page:
   - one player and a grid of cases with thumbnails;
   - images shared between cases are stored once;
   - audio is re-encoded small (section 6).

The justices' layers come from `./run.sh assets` with any case argued before the same nine.

**Done by hand, not yet scripted:**

- **Decision notes** (quotes from the opinions shown during the argument).
  - Opinions come from CourtListener's public S3 bucket: list `pdf/YYYY/MM/DD/` for the decision date, download the PDF, then `pdftotext`.
  - Claude reads the majority, concurrences and dissents and writes notes JSON. Each note has the time of the justice's question, the asker, the question, a label, a quote, a citation and a one-line connection.
  - `scripts/verify_notes.py NOTES.json OPINION.txt OUT.json` keeps only quotes found word for word in the opinion and schedules them. It dropped a few every case.
- **Outcomes.** Write each outcome sentence from the opinion itself. Two search-result summaries got the outcome wrong; one invented a dollar figure.
- **Thumbnails** (`WORKROOT/thumbs/<docket>.jpg`): a frame grab of each case's player, taken in headless Chromium.
- **The wall clock's start time per case.**
  - "This morning" in the Chief's opening means 10:00 (`clock_start` 36000).
  - "We'll hear argument next" means it was the second case that day, so start it where the first one ended. B.P.J. was 42900 and Monsanto 43260.

### 3.3 Justices

`scripts/characters.py` holds the justices' specs and seating; `BENCH_ORDER`, as seen from the gallery, is Barrett, Gorsuch, Sotomayor, Thomas, Roberts, Alito, Kagan, Kavanaugh, Jackson. Thomas (dark rectangular frames) and Jackson (plum frames) wear glasses; the first version wrongly gave glasses to no one. For an older Court, add `justices` and `bench_order` to `case.json` (README explains the seniority rule).

---

## 4. Likenesses (both kinds)

Workflow: photo → spec → lineup sheet → compare side by side with the photo → fix → only then the long render. Render the photo-likeness characters last, so a late correction re-renders only them.

A puppet spec is a dict merged over `DEFAULT` in `scripts/puppet.py`. These keys did the work:

| Key | Use |
|---|---|
| `skin` | Hex. Real skin tones for likenesses; felt colors for stand-ins. |
| `H`, `W`, `Wc`, `Wm`, `zb`, `chin_fwd` | Head height, cheek/crown/mouth width, jaw drop, chin jut. Long narrow face: raise `H`, lower `W`/`Wm`, more negative `zb`. |
| `sculpt` | `brow`, `cheek`, `jowl`, `chin`, `temple` bulges. |
| `smile`, `lid`, `low_lid`, `lid_hex`, `iris` | Mouth curve, upper and lower lid coverage, lid color, colored iris `{hex}`. |
| `nose` | `w`, `h`, `l`, `droop`. |
| `brows` | `hex`, `thick`, `arch`, `angle`. |
| `hair.style` | `side_part`, `short`, `buzz`, `cut` (short cuts: `length`, `side_len`, `front_z` for the hairline, `temple` for receding temples, `sweep`, `up`, `side`, `tousle`), `bob`, `long` (`length`, `fringe`, `volume`), `curls`, `locs`, `none`. Also `hex`, `rand` (gray flecks), `part`, `density`. |
| `beard` | `hex`, plus `hex2` with `frac` for salt-and-pepper. `chin` is a gradient of `hex2` toward the chin, placed by `chin_from` and `chin_span`. `len`, `chin_len`. `beard`/`mustache` true or false. `shadow` (and `shadow_hex`) is stubble drawn on the skin, with no fur. |
| `glasses` | `hex`, `metal` (0–1), `r` (size), `wire` (thickness), `n` (2 = oval, about 3 = rectangular), `up` (pushed up on the head). |
| `lipstick`, `necklace` | `{hex}`; necklace `{hex, drop, star}` is a thin chain only (no beads). |
| `ears.show` | False when hair covers them. |
| `body` | `robe` (the suit or robe color), `shirt`, `tie` (None for no tie), plus the interview clothes in `interview/cast.py` (sweaters, cardigans, patterns). |

Rules that came out of the mistakes:

- Read colors only from color photos. Check facial hair, glasses and clothing explicitly with the user, not from assumptions.
- A woman's puppet must not default to a suit and tie. Check that the face reads as intended: softer jaw, lip color, earrings.
- Old official portraits: age the hair.
- Label every tile on the lineup sheet, and put the photo next to it when one is on disk.
- Name on the page who is modeled on photos and who is a stand-in.

---

## 5. Recorded conversations

The scripts in `interview/` were written for the Lawler breakfast and still hard-code its cast. For a new conversation, first move the cast into one config (or copy and edit consistently):

- the speaker names in `align.py` (`SPEAKERS`);
- the seat order, caption labels and display names in `build.py` (`KEYS`, `LABEL`, `DISPLAY`);
- the specs in `cast.py`;
- the seats and room in `breakfast.py`;
- `KEYS` in `run.sh`.

### 5.1 Steps

Work folder `W` (env var; default `work/interview`) holds the inputs:

- `audio.mp3`;
- `whisper.json`;
- `transcript.txt`: the first 5 lines are the header (title, dek, intro, participants, "Full Transcript"). After that, every turn starts with the speaker's full name glued to the text, which is what a .docx with bold names exports to;
- optionally `chapters.json`; see `interview/chapters_lawler.json`.

```bash
W=work/myinterview python interview/align.py      # transcript words -> Whisper word times (99.3% matched last time)
W=work/myinterview python interview/build.py      # cuts, edited audio, timeline, captions, chapters, page data
#   read W/cuts_report.md and show the user what was cut
interview/run.sh lineup       # likeness sheet -> W/cast_sheet.png   (iterate with the user)
interview/run.sh preview      # rough stills of the set              (iterate with the user: room, table, food)
interview/run.sh assets       # full render, ONE Blender process, resumable (hours on 4 cores)
interview/run.sh meta && interview/run.sh check && interview/run.sh export
W=work/myinterview python interview/finish_page.py && W=work/myinterview python interview/validate.py
node interview/web_check.js W/page W/page_check     # headless Chromium: plays, seeks, captions, chapters
```

Then publish `W/page/` as its own new private Artifact.

### 5.2 Settings that worked (Lawler)

- **Cuts:**
  - The 2 min 50 s of pre-interview chatter (introductions, food orders, ground rules) and the 6 seconds after the final thank-you were removed.
  - Untranscribed speech under 10 s was kept (`MIN_CUT=10`); three such asides were listed in the report for the user to decide.
  - Splices use 12 ms crossfades and room tone taken from the recording itself.
  - The audio was attenuated about 0.9 dB, because the source clipped.
  - The page says the recording was "trimmed to match the published transcript."
- **Shots:**
  - A wide shot of the whole table, plus a close-up per person.
  - During the guest's long answers, cutaways every 10 to 20 s go to the asker, the wide shot or half the table.
  - Shots run at least 1.4 s, and every boundary falls in a quiet moment, never inside a word.
- **Set:**
  - A long table, everyone along the far side and the two ends, the guest in the middle facing the camera, and the near side open for the camera. It's the easiest layout to animate.
  - A square or round table puts someone's back to the camera.
- **Chapters:** 22 of them, one per new line of questioning, named "Asker asks about topic."

---

## 6. Settings reference

**Rendering** (Cycles on CPU, OIDN denoiser, AgX view transform)

| Setting | Value |
|---|---|
| Plate samples `S_PLATE` | 96 for a single case; 48 for the slate and the interview |
| Layer samples `S_LAYER` | 64 for a single case; 32 for the slate and the interview |
| Resolution | Wide 2560×1440; close-ups 1280×720 |
| Exposure | −0.35 EV on the lawyer cameras, because fair skin washed out under the lectern key light |
| Jaw angles `JAW` | 0.015, 0.105, 0.195, 0.285, 0.375 rad: five mouth shapes, `head0` to `head4` |
| `head5` | Eyes closed, jaw shut (blinks) |
| `meta.json` | Crops and pivots. Write it with a render-free pass (`__none__`): parallel renders overwrite each other's copy. |

**Lip sync** (`scripts/timeline.py`; `interview/build.py` uses the same rule)

| Setting | Value |
|---|---|
| Loudness | Band-pass 180–3400 Hz, 35 ms RMS windows, 24 fps |
| Timing | The mouth leads the audio by 45 ms |
| Mouth state | `min(4, floor(openness × 4.6))` |
| Silence floor | `GFLOOR` = the 8th percentile of the whole recording's dB |
| Per-turn threshold | `max(GFLOOR+5, min(max(p12+7, GFLOOR+13), p97−16))`. The `p97−16` cap keeps quiet speakers moving; the `GFLOOR+5` floor keeps room noise from opening mouths. |
| Clean-up | Speech runs shorter than 3 frames are dropped; release decays by ×0.45 per frame |

Results with these settings: on Rahimi, 7.6% of silent frames open (Roberts 2.7%, down from 19%) and 93% of clear speech. In the interview the quiet speakers went from 13–20% to 44–56% open.

**Editing:** a close-up on whoever talks for more than 2.2 s; bench cutaways every 10 to 19 s during long answers; a reaction shot inside long questions; captions of about 90 to 96 characters; audio cut points at the quietest moment near every 600 s.

**Player motion** (court pages only: `page.motion` flags, set by `build_page.py`; the interview has none)

| Effect | Setting |
|---|---|
| Listeners | Hold a pose 6–20 s, ease 0.8–1.5 s, roll about ±2°; glance at a new speaker after 0.2–1.2 s; 15% chance of a nod at each phrase end |
| Breathing | Bodies stretch ±0.4% from the bottom, period 3.5–4.5 s; the head rides along |
| Blinks | Every 2.5–7 s for 3 frames, occasionally double; speakers blink only with the mouth shut |
| Camera drift | About 1.5% push-in on close-ups; 8–12 px pan at scale 1.012 on wide shots |
| Gallery | Roll ±1°, a pixel or two of shift, a rare twitch |
| Mouse | Counsel-table corner of the wide shot. Absent for the first 3.5–6 min, then in most wide shots. Looks at the camera every 1–3 min; laughs 2 s at each "(Laughter.)" |
| Clock | Hands drawn live from `clock_start + t` |

Performance cost: 6–8 ms per frame, against a 41.7 ms budget. The user chose to leave the curtains still: heavy velvet indoors doesn't move.

**Audio for publishing:** the screening room uses AAC at 16 kbps, 16 kHz mono, in about 30-minute `.mp4` segments. Single pages use MP3 segments. The interview used 40 kbps mono MP3 in 8 segments.

---

## 7. Publishing (claude.ai Artifacts)

| Limit | Value |
|---|---|
| Page | 16 MB |
| Each file | 15 MB |
| Per publish | 64 MB and 255 files |
| Per version | 256 MB and 511 files |

- Large pages go up over several publishes to the same URL.
- Audio types served: `.mp3 .wav .ogg .mp4 .webm`. `.m4a` is refused, so put AAC in `.mp4`.
- `assemble_theater.py` names images by content hash, so a rebuild changes only the files that changed. Republish just those, and remove stale ones by passing `null`.
- Pages are private until the user shares them. They depict real people, so sharing is the user's call. Never write private artifact URLs into the public repo.
- Credits: "Made by Josh Greenman with Claude." Court pages also credit Oyez (audio and transcript timing, CC BY-NC 4.0) and CourtListener (opinions).

---

## 8. Process lessons

- **Keep projects separate.** When two projects run at once, label every update with the project it's about. An instruction for one must not leak into the other (court-only motion effects stayed out of the interview).
- **Look before the long render.** Do the lineup sheet and set stills first, every time.
- **Helpers:**
  - Use subagents on the cheaper model for the heavy lifting.
  - Give each helper its own files: two helpers editing `layers.py` at once corrupted it.
  - Run one Blender process per helper. With 4 cores and 15 GB, more processes just thrash or get killed.
- **Usage:**
  - Cloud sessions count against the plan's 5-hour and weekly limits. Both helpers hit the weekly limit mid-render and stopped until it reset.
  - The session's "cost" figure is what its tokens would cost at API prices (about $151 over the first two days), not a bill. Most of it is the conversation re-read at each step.
  - Fresh sessions per project, fewer status check-ins and cheaper-model helpers all cut it.
  - Whether cloud credits apply before the plan limits is set in claude.ai's usage and billing settings, not from inside a session.
- **The cloud machine:**
  - Renders exist only in the container until published, and a container reclaimed after inactivity loses them. Publish as soon as a page passes its test.
  - The code is pushed to GitHub after every step.
- **Testing:**
  - The cloud sandbox's Chromium can't decode H.264 or AAC; test with MP3 or WebM.
  - Test seeking on a server without Range support.
  - Check that `[hidden]` isn't overridden by CSS `display`.
- **Small traps:**
  - `pkill -f script.py` also kills the shell that runs it.
  - Scaling a prop group also scaled its absolute height, so platters floated above the table.
  - Gemini image generation had zero quota, which is why the puppets are 3D (it keeps jaws and camera angles consistent anyway).
