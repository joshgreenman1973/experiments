# Sasha's Dollhouse

**Live: https://joshgreenman1973.github.io/experiments/sasha-dollhouse/** — add it to the tablet home screen from the browser share menu and it opens full-screen with its own icon, and works offline after the first visit.

A low-demand social-communication game for Sasha — 5, autistic, hyperlexic with excellent decoding, a gestalt language processor, probable perfect pitch, particular about music, strong at math and interested in Spanish.

**Files:** `index.html` (the whole app), `sw.js` (offline cache), `manifest.webmanifest` + `icon.svg` (home-screen install). No build step. Nothing is uploaded anywhere; state lives in `localStorage` only: `th_said` (phrase counts), `th_visited` (rooms visited today), `th_voice` (chosen voice), `th_stage` (growth dial), `th_custom` (parent-added phrases).

---

## Status as of 2026-07-31

**Working and complete:**

| Piece | State |
|---|---|
| House hub — 6 rooms | done |
| Scene engine (comic-strip conversation, speech bubbles, no fail state) | done |
| 10 written scenes across kitchen / play / doctor / garden / music / numbers | done |
| Phrase bank ("My phrases") with the five-move color system | done |
| Mitigation builder (whole gestalt → parts → swap the orange slot), 10 phrases | done |
| Music room: 13-key keyboard with note names + hertz; melodic-intonation "sing a phrase" | done |
| Number room: number → full sentence, English + Spanish, plus times tables | done |
| Spanish toggle throughout | done |
| Voice on/off toggle (Web Speech API) | done |
| "For grown-ups" methodology page with sources and an honest evidence caveat | done |
| AI caution button | done |

**Done since first draft (2026-07-31, same session):**
- Verified in the browser: house, kitchen scene end-to-end (choice → reply → next beat), music room keys and sing-a-phrase melody, number room sentences and dots. No console errors.
- Fixed: SVG portraits had opaque white backgrounds; now transparent.
- Voice overhaul: ranked natural-voice selection (Premium/Enhanced/Google/Siri first), novelty macOS voices (Albert, Bad News, Bubbles...) filtered out, and a voice picker on the For grown-ups page that saves the choice to `localStorage` (`th_voice`). This Mac only has legacy voices installed — the README-worthy fix is downloading a Premium voice (System Settings → Accessibility → Spoken Content → Manage Voices → Ava/Zoe Premium), which the grown-ups page explains.
- AI caution button removed per Josh.
- Tablet check (768×1024): layout verified good — full-width finger-sized choice cards, readable bubbles. Added `touch-action:manipulation` (kills double-tap zoom delay) and apple-touch meta tags + inline SVG icon so it can be added to an iPad home screen as "Sasha's Dollhouse" with no browser chrome.

## Presentation vision (per Josh: "think bigger about how to present this")

The current hub is a menu of cards. The bigger version is an actual dollhouse:

1. **The house is the interface.** One full-screen illustrated cutaway house — like a dollhouse with the front swung open — six rooms visible at once, each character visibly *in* their room doing something (Poppy stirring, Mo mid-stack, Coco on a perch). Tap a room to zoom in. This matches how she already reads Gabby's Dollhouse spatially without borrowing anything from it.
2. **A front door, not a menu.** App opens on the closed front door with her name on the mailbox. Tap the door, it swings open into the cutaway. First-run magic, and a natural ritual for starting.
3. **The house has a day.** Morning light in the kitchen, rain sometimes in the garden window, night mode that dims everything and has characters saying goodnight phrases — a wind-down mode a parent can use before bed.
4. **Characters wave when you've visited.** The house remembers (localStorage) which friends she talked to today; visited friends' windows glow. Gentle pull toward the rooms she hasn't tried, with zero demand.
5. **Printable companion.** A print stylesheet that turns the phrase bank into physical phrase cards (five moves = five colors) for the fridge or backpack — the bridge from screen to real rooms with real people.
6. **The generic fork.** Later: a `?name=` parameter or setup screen turning this into "____'s Dollhouse" for other kids — shareable with her SLP, classmates, other parents. Sasha's copy stays hers.

Item 1–2 are the design overhaul; 5 is cheap and high-value; 4 is an evening's work.

**Second session pass (same day), all verified in browser and deployed:**
- **Front door screen**: house facade on a grass hill with flowers, characters peeking from windows, chimney smoke, day/night sky (stars + moon after 8pm), doorbell two-note chime on tap.
- **Hub is now a house**: roof + attic sun/moon + chimney over an even 2×4 room grid; cards tilt alternately; portraits bob; visited rooms get a star (resets daily).
- **Two new rooms**: **The game room** (Mo hosts; 3 scenes quietly about not getting what you want — someone else picks, the spinner decides, someone else goes first; the rule holds, the feeling is named and survivable, refusal acknowledged without changing the outcome) and **The ice cream porch** (Gertrude the duck, 7½, and Bartholomew the frog, 7 — Josh's own characters, best friends, second grade at the Benjamin Franklin school).
- **Ages everywhere**: every character has an age, shown in scene pickers ("with Pim · age 5"); Uno has an ages scene (Mo 4, Pim 5, Poppy 6 consecutive; Coco 100).
- **20 scenes total** (was 10), including a mishearing-repair scene and a Coco wrong-note scene for her ear.
- **Grows-with-her stage dial** (grown-ups page): A whole phrases → B swappable chunk highlighted orange inside scene choices → C every choice adds "I have my own thing to say." Never switches itself; shows usage stats (distinct phrases, total picks) and suggests considering B after 15 distinct phrases.
- **Parent-added phrases**: form on grown-ups page, brackets mark the swappable slot ("We can fix [the truck]"), becomes a card + builder under a "Sasha's own" filter.
- **Print cards** button on My phrases (print stylesheet → fridge cards).
- **Richer character art**: stripes, bell collar, bow, freckles, antennae, blush, band-aid, dice pips — verified cohesive on screen, not cluttered.
- **PWA**: manifest, SVG icon, service worker (cache-first incl. fonts).
- **Deployed** to joshgreenman1973/experiments on main (commit e7b69240). Manifest CI will pick it up.
- **Nano banana art blocked**: Josh's Gemini key is free-tier (quota 0 for image models, $0 spent). If he enables billing, generate 8 consistent portraits (~$0.40 flash) and swap into the avatar slots, keeping SVGs as fallback.

**Third session pass — real voices and a real music room:**
- **Every scripted line is now pre-recorded neural audio** — 811 mp3 clips (19MB) in `audio/`, generated free with `edge-tts` (Microsoft neural voices, no API key). Each character has a distinct voice: Ana (an actual child voice) for Sasha's lines, Jenny/Poppy, Christopher slowed for Dr. Bo, Guy pitched down for Mo, Eric/Uno, Aria brightened for Coco, Emma/Pim, Michelle/Gertrude, Brian/Bartholomew, Dalia + Jorge for Spanish. The Web Speech robot voice is now only a fallback for parent-added custom phrases.
- **Regeneration workflow**: edit dialogue in `index.html`, then `node tools/extract-lines.mjs && python3 tools/generate-audio.py` (idempotent — only new lines are generated), commit `audio/` + `audio-map.js`.
- **Scene pacing fixed**: the engine now advances on speech-end (with safety timers), so lines are never cut off mid-sentence. macOS novelty voices (Bells, Boing...) filtered from the voice picker.
- **Music room is now an ear game**: three modes — Free play, **Guess the note** (Coco plays one, she finds it on the keys; a miss gets "It was E. Listen again!" and a replay, no fail state), **Copy me** (Coco plays a growing sequence of naturals, 2→6 notes, she plays it back). All Coco game lines recorded; all feedback also shown as large text.
- **The attic**: tap the sun/moon in the roof — a secret little room where her most-said phrases hang in frames, with a daypart line from the house itself.
- **Smaller delights**: a snail crossing the house very slowly (tap it, it wiggles), sparkles on the scene end-card, a daypart greeting under the title, real iPad home-screen icons (180/192/512 PNG), iOS audio unlock on the door tap, service worker v2 pre-caches all voice clips for full offline.
- **Audio architecture**: one reusable `Audio` element (`AUD`) — setting `.src` stops the previous clip, so lines never overlap; `speak()` looks up `AUDIO_MAP[lang]["who|text"]` and falls back to speech synthesis for unknown text.

**Fourth session pass — the music room becomes Pitch Pals-grade:**
- **Sing it back**: Coco plays a note, Sasha sings it, the app hears her through the microphone (autocorrelation pitch detection, no libraries) and celebrates when she holds the note for ~half a second. Octave-agnostic pitch-class matching with ±45 cent tolerance. Mic denied → "The microphone is shy today. Ask a grown-up to help."
- **What am I singing?**: free tuner mode — a live display of whatever note she sings. For a kid with perfect pitch this is a toy in itself.
- **"Sing a phrase" removed** — it mapped words to arbitrary notes and was neither music nor language; confusing.
- **Notes now actually play in the note scenes**: scene beats support a `notes:[...]` field; Coco's climbing-stairs song and wrong-note scale really sound (the wrong note is F♯ where sol belongs).
- **Tone volume fixed**: keyboard/game tones were far too quiet next to the neural voices — now a 3-partial additive tone at ~3× the gain, warmer and clearly audible.
- **Dialogue naturalism pass**: removed adultisms and invented metaphor ("very second grade of you", "pocket-brain", "that is the whole dance", "fair fixed it", "cooks say that to helpers", "even numbers feel good in my blocks") in favor of plain child-speech, en + es both.
- **Audio filenames are now content hashes** (sha1 of who|lang|text) — index-based names silently re-paired texts with wrong recordings when lines changed. Full set regenerated (814 clips). Service worker bumped to v4.

**Original session — not done, now superseded or still open:**

1. **Never opened in a browser.** It was written but not run. First thing to do is load it and click through every room. Likely small bugs, not structural ones.
2. **Known suspect spots** worth checking first:
   - The `#playMelody` / `#saySpoken` handlers are assigned twice — once as no-ops at load, once inside `drawSing()`. The `drawSing()` assignment should win, but confirm the buttons actually play.
   - The music room's `singPick` chips call `renderMusic()`, which re-renders and re-wires. Confirm selecting a phrase doesn't reset the keyboard state oddly.
   - `redrawScene()` on the Español toggle mid-scene — confirm it doesn't duplicate or lose the pending choices.
   - Spanish TTS depends on an installed `es-*` voice. On macOS Safari it works; elsewhere it may silently fall back to English.
   - The builder's Spanish line only shows for `pick === 0`; the swapped-phrase Spanish isn't generated. Either write per-swap Spanish into `BUILDS[].swaps[].es` (the field exists and is populated — it just isn't rendered) or drop the Spanish line from the builder.
3. **Not deployed.** No GitHub Pages URL yet. Confirm which account before pushing — this is a personal project, so `joshgreenman1973`.
4. **Not in the gallery manifest.** Decide whether it belongs there at all; it is a personal family project, not a civic one.

---

## How it's built

### Design rules encoded in the app

These came out of the research and are the reason the app looks the way it does. Changing them changes what it is.

1. **No wh-questions are ever asked of her.** Characters comment; she picks a reply. Early gestalt processors have to disassemble a question before answering it, which is the skill still under construction. Wh-questions belong at NLA stages 4–6.
2. **Every phrase option is a whole, mitigable gestalt.** It can be split and recombined later. "Can I have a turn?" splits. "Boy oh boy, here we go!" does not. Everything written into `SCENES` was tested against that.
3. **Text is the primary channel, audio is optional.** Because her decoding is excellent. Every line is written large before it is ever spoken.
4. **Nothing sings unless she presses a button that says so.** She's particular about music; the music room is opt-in twice.
5. **No score, no timer, no wrong answer.** Every option advances the story and gets a warm, specific reply.
6. **Saying no is one of the five moves.** Refusal is communication. Every refusal is accepted immediately and without cost by the character.
7. **Declarative language.** Characters narrate what they notice, think and feel rather than issuing directives.

### The five moves (color-coded everywhere)

| Move | Color | Function |
|---|---|---|
| Hello | marigold | opening and closing |
| Asking | teal | requesting object, action, turn, information |
| Saying no | rose | declining, protesting, limit-setting |
| Telling | grape | commenting, sharing an inner state |
| Fixing it | sky | repair after rupture, offering a plan |

### Characters — all original

Poppy (orange cat), Dr. Bo (rabbit who fixes toys), Pim (pig), Mo (blue monster), Uno (number cubes), Coco (bird). Original names, original inline-SVG art, original writing and melodies.

**Deliberate constraint:** no characters, names, art or music from Gabby's Dollhouse, Peppa Pig, Sesame Street, Doc McStuffins, Sago Mini or Numberblocks are used, and none should be added. Her affection for a show isn't a license to use it, and it would make the thing unshareable. The cast was built to occupy the same emotional slots instead.

### Code map (`index.html`)

- `CHARS`, `svgFor()` — cast and their SVG portraits
- `FN` — the five moves
- `ROOMS` — the six rooms
- `SCENES` — all dialogue. **This is the main thing to extend.** Each scene is `{room, id, title, who, beats: [...]}`; a beat is either `{say:{who,t,es}}` or `{pick:[{fn,t,es,reply:{who,t,es}}]}`.
- `BUILDS` — the mitigation data: `{whole, pre, slot, post, es, swaps:[{t,es}]}`
- `speak()` / `tone()` — Web Speech API and Web Audio
- `renderHouse` / `openRoom` / `startScene` / `advance` / `renderChoices` — the scene engine
- `renderPhrases` / `renderBuilder` / `renderMusic` / `renderNumbers` / `renderGrownups` — the other screens

Adding a scene is just appending an object to `SCENES`. The room page picks it up automatically.

---

## Obvious next moves

- **More scenes.** Ten is thin. The garden, doctor and play rooms carry the most social weight and could take three or four each. The music room has only one scene.
- **A hard case worth writing:** a scene where the other character misunderstands her and she has to repair it — that's the "Fixing it" move doing real work, and it's underused.
- **Her real scripts.** The app can't know them. A screen where a grown-up types in a phrase she already uses, and it gets a mitigation card built for it, would be the single highest-value addition.
- **Offline.** Add a service worker and self-host Fredoka so it works on a plane or in a waiting room.
- **Install as an app.** Add a web app manifest and icons so it can go on a home screen without a browser bar.

---

## Honest note on the evidence

The frameworks behind this are not equally well supported, and the app says so on its own "For grown-ups" page rather than hiding it.

- **Natural Language Acquisition** (Blanc's staged gestalt model) is the organizing idea here and is widely used clinically, but its peer-reviewed base is thin. A 2024 critical analysis argues the framework has outrun its evidence.
- **Social narratives** (Gray's Social Stories, Comic Strip Conversations) have a real evidence base, with effects that vary by child and by delivery consistency.
- **Music-assisted language intervention** has promising small trials including a 2024 randomized feasibility trial; effects are modest, samples small.
- **Declarative language** is a clinical style, not a tested protocol. Used because it lowers demand, which stands on its own.

No speech-language pathologist has reviewed any of this. Show it to hers before treating it as more than a toy.

## Sources

- [Using the Natural Language Acquisition Protocol to Support Gestalt Language Development](https://pubs.asha.org/doi/10.1044/2023_PERSP-23-00098) — *Perspectives of the ASHA Special Interest Groups*
- [Natural language acquisition and gestalt language processing: a critical analysis](https://pubmed.ncbi.nlm.nih.gov/38784430/) (2024) — the skeptical read
- [Embracing gestalt language development as a fundamental neurodiversity-affirmative practice](https://journals.sagepub.com/doi/10.1177/13623613241234598) — *Autism* (2024)
- [IEP and treatment plan considerations for gestalt language processors](https://www.meaningfulspeech.com/blog/iep-considerations) — on why wh-questions belong at stages 4–6
- [Writing and using social narratives](https://iidc.indiana.edu/irca/articles/writing-and-using-social-narratives.html) — Indiana Resource Center for Autism
- [The links between Social Stories, Comic Strip Conversations and cognitive models](https://www.tonyattwood.com.au/books-by-tony-m/archived-papers/78-the-links-between-social-stories-comic-strip-conversations-a-cognitive-models) — Attwood on Gray's methods
- [Using music to assist language learning in autistic children with minimal verbal language: the MAP feasibility RCT](https://journals.sagepub.com/doi/10.1177/13623613241233804) (2024)
- [From intuition to intervention: developing an intonation-based treatment for autism](https://pmc.ncbi.nlm.nih.gov/articles/PMC6127010/)
- [Perfect pitch: autism's rare gift](https://www.kennedykrieger.org/stories/interactive-autism-network-ian/perfect-pitch-autism-rare-gift) — Kennedy Krieger Institute
- [Supporting communication and regulation with declarative language](https://uniquelyhuman.com/2024/08/16/communication-regulation-declarative-language-linda-murphy/) — Linda Murphy on Uniquely Human
