# Singing Stairs — App Store submission kit

Everything needed to put **Singing Stairs 1.0** on the App Store at **$0.99**,
sorted by who can actually do it.

**Target is 1.0, not 2.0.** 2.0 has the upgraded painted artwork but doesn't
work as well, so it stays on the shelf. The kit below is version-agnostic
where it can be — if 2.0 is ever fixed, the same metadata, privacy policy and
support page carry over to it as an update.

---

## 1. The short version

The app is the finished part. Native SwiftUI, no dependencies, no networking,
a full XCUITest suite, already on TestFlight and already carrying a
provisioning profile named "Singing Stairs App Store" — which means the App
Store side is further along than a first submission usually is. Nothing about
the code blocks a release.

What blocks it is paperwork, and one item dominates: **charging 99 cents
requires the Paid Applications Agreement**, which means bank details and tax
forms filed under Apple's Account Holder. Nobody but Josh can do that, it is
maybe 30 focused minutes, and Apple then takes anywhere from a few hours to a
couple of days to mark the agreement active. Until it is active, the price
field offers nothing but Free.

Realistic timeline: **half a day of Josh's attention, then 1–3 days of Apple
waiting, then a 24–48 hour review.**

---

## 2. One thing I should flag up front

**1.0's source is not on GitHub.** It lives only on your Mac at
`../singing-stairs/`, next to the 2.0 checkout. I searched every repo this
session can reach — `singing-stairs-2` is the only one that exists.

That is the single biggest limit on how much of this I can do alone. I can
write every word of the store listing, the privacy policy and the review
notes without seeing 1.0 (they describe behaviour the two versions share),
but I cannot touch 1.0's project file, bump its build number, or write it a
screenshot test.

**If you push 1.0 to a private GitHub repo, items 18–20 below become mine.**
It is a two-minute `git init && git remote add && git push`. I already have
push access to `singing-stairs-2`, so the same would apply to a 1.0 repo.

---

## 3. Who does what

### Only Josh can do these (Apple account, money, legal)

| # | Task | Where | Notes |
|---|------|-------|-------|
| 1 | Confirm Apple Developer Program membership is current ($99/yr) | developer.apple.com | Almost certainly yes — 1.0 is on TestFlight |
| 2 | **Sign the Paid Applications Agreement** | ASC → Business | The gate on 99¢. Account Holder only |
| 3 | **Bank account** for payouts | ASC → Business → Payments | Routing + account number |
| 4 | **Tax forms** (US: W-9) | ASC → Business → Tax | Address, SSN/EIN |
| 5 | Enrol in the **Small Business Program** | ASC | Apple's cut drops 30% → 15%. Worth two minutes |
| 6 | Confirm the App Store Connect **app record** exists | ASC → Apps | Likely already there — see §4. If not, create it; the API can't, it's web UI only |
| 7 | Paste the metadata from §5, set price to $0.99 | ASC | Or hand me the API key and I'll do it |
| 8 | Press **Submit for Review** | ASC | Always a human action |

### Needs Josh's Mac (this container is Linux — no macOS, no Xcode)

| # | Task | Notes |
|---|------|-------|
| 9 | Archive and upload the build | I can write the commands; the machine has to be yours |
| 10 | Run the screenshot pass | See §7 |

### I've already done these, on my own

| # | Task | Status |
|---|------|--------|
| 11 | Privacy policy, written from an audit of the actual source | ✅ `privacy.html` |
| 12 | Support page (Apple requires a reachable support URL) | ✅ `support.html` |
| 13 | Host both at a public URL | ✅ this repo's GitHub Pages |
| 14 | All store copy — name, subtitle, keywords, description, promo text | ✅ §5 |
| 15 | App Privacy questionnaire answers, verified against source | ✅ §6 |
| 16 | Age rating answers | ✅ §6 |
| 17 | App Review notes (the microphone needs explaining) | ✅ §8 |

### I could do these — blocked only on 1.0 being reachable

| # | Task | Blocker |
|---|------|---------|
| 18 | Release config: build number bump, signing settings | 1.0 not on GitHub (§2) |
| 19 | A UI test that emits store-sized screenshots | 1.0 not on GitHub (§2) |
| 20 | Set price and push metadata via the ASC API | Needs the `.p8` key, and items 2–4 done first |

---

## 4. What 1.0 already has

Worth checking before assuming this is a from-scratch submission. The 2.0
README records that 1.0 carries a provisioning profile called **"Singing
Stairs App Store"** — an App Store *distribution* profile, not a development
or Ad Hoc one. Those are issued against an existing App Store Connect app
record, so in all likelihood the record, the bundle id and the app name are
already registered and item 6 is a five-second confirmation.

**Verify on your Mac before pasting anything:**

- 1.0's exact bundle id (2.0 uses `com.joshgreenman.singingstairs2` and the
  README says it was deliberately given a *separate* id so both could coexist,
  which puts 1.0 at `com.joshgreenman.singingstairs` — confirm, don't assume)
- Whether the ASC record is already there, and what name it reserved
- 1.0's `MARKETING_VERSION` and `CURRENT_PROJECT_VERSION`
- That `ITSAppUsesNonExemptEncryption` is set to `false` in 1.0's `Info.plist`
  (it is in 2.0's; if 1.0 lacks it, every upload will stop to ask)

The API key ids in `singing-stairs-2/tools/asc.py` (`ZRL2ZT22XY`, issuer
`cd73ce4b-…`) are account-level, so they work for 1.0 too.

---

## 5. Store metadata — ready to paste

Written from the feature set the two versions share. Flagged items in §5.1
should be checked against the 1.0 build before pasting.

### Name (30 char limit) — 14 used
```
Singing Stairs
```

### Subtitle (30 char limit) — 27 used
```
Ear training for little kids
```

### Keywords (100 char limit) — 93 used
```
pitch,music,piano,notes,solfege,preschool,melody,intervals,toddler,learn,listening,montessori
```
No spaces after commas — Apple counts them. Words already in the name and
subtitle are indexed automatically, so "singing", "stairs", "ear", "training"
and "kids" are deliberately absent.

### Promotional text (170 char limit) — editable any time, no review needed
```
Nine listening games in one night sky. Tap a letter and it sings its real note. No scores, no timers, nothing to get wrong. Everything works offline.
```

### Description
```
Singing Stairs teaches a young child to hear pitch.

Pitch is height, so the app is built that way: a staircase climbs the night
sky from low C to high C, one letter per step. The letters are the characters
— big cut-paper letterforms with eyes that follow whoever is singing and
mouths that open when they sing. They are coloured by the Boomwhacker
convention, so they agree with the colour-coded instruments at school.

Tap any letter and it sings its true note in a real recorded piano, and says
"I sing G!"

NINE GAMES

The playground — eight pieces of equipment, each carrying one musical idea,
where the thing a child already knows about the equipment is the thing the
music is doing. The slide goes down and so do the notes. The swing goes
higher and so does the pitch. The roundabout goes all the way round and lands
on the letter it started from, higher — which is what an octave is.

Sing together — her voice becomes a star riding the staircase in real time,
and the letter she is singing dances with its name huge on the screen.

The mystery singer — a note floats out from behind the theatre curtain.
Hunting for it by tapping letters IS the game: every tap plays a real note,
and that comparison is the thing that trains an ear.

Sing it back — the app plays a note and she sings it back. It listens, names
the note she actually sang, and tells her to go higher or lower until the
ring around the target letter fills up. Any octave counts.

Higher or lower — two little stages sing; tap the one the round asks for. The
gap between the notes narrows invisibly as she succeeds.

Song time — real songs played by tapping the glowing letter, with the lyric
lighting up syllable by syllable. Twinkle, the alphabet song, Old MacDonald,
Hot Cross Buns, Jingle Bells, Ode to Joy and more.

Happy or sad — major and minor chords, named on the face of a smiling sun or
a rain cloud.

Echo clouds — eight clouds hide four pairs of notes. Sound-memory matching.

How many singers — one, two or three notes sound at once. Tap the count.

HOW IT IS BUILT

Nothing is scored. Nothing is timed. Nothing can be done wrong — a wrong tap
just teaches ("the mystery note is higher than E"). Refusing to play costs
nothing. Stars gather in the sky but are never counted out loud.

Nothing makes a sound until a child taps something.

The piano is a real sampled grand, not a synth tone, across three octaves,
and a Low / Middle / High control moves the whole staircase to suit the voice
of the child using it.

FOR GROWN-UPS

Press and hold the Grown-ups button for a second and a half. You can add
sharps and flats, switch letter names to solfège, or put individual letters
to sleep to shrink the games for a younger player.

PRIVACY

The app has no networking code. It never contacts a server, and works
identically in airplane mode. There are no accounts, no advertising, no
analytics, no third-party code, no in-app purchases and no links out of the
app.

Two games listen to singing so they can work out which note it is. That audio
is examined in memory to estimate pitch and immediately discarded. It is
never recorded, never saved and never sent anywhere. Everything else in the
app works without the microphone.

Requires iOS 17 or later. iPhone.
```

### 5.1 Check these against 1.0 before pasting

- **The game list.** The description names nine games and no "Copy me". If
  1.0 still ships Copy me, or is missing a game 2.0 has, fix the list.
- **The song count.** I left the number out of the description on purpose and
  named six songs instead — verify those six are all in 1.0's songbook.
- **Sharps and flats, solfège, Low/Middle/High.** All described as present.
- **iOS 17 minimum**, and iPhone-only.

### What's New
Not used on a first submission. For later updates, a sentence or two.

### Category
- Primary: **Education**
- Secondary: **Music**

On the "Made for Kids" / Kids Category question: my recommendation is **no**.
The app would qualify comfortably — it collects nothing and has no outbound
links — but the Kids Category adds review scrutiny and an age-band commitment
in exchange for a shelf almost nobody browses. Education plus a 4+ rating is
the lower-friction path. Worth a deliberate decision either way, not a
default.

### Price
**USD 0.99** — Apple's lowest non-free tier, so 99 cents is available exactly
as asked. Selectable only once items 2–4 are complete and active.

Net per sale: about 70¢ at the standard 30% commission, about 84¢ at the 15%
Small Business Program rate. Hence item 5.

---

## 6. Questionnaires — verified answers

### App Privacy → **Data Not Collected**

Checked against the 2.0 source rather than the README, and 2.0's non-art code
is 1.0's code. There is no `URLSession`, no `URLRequest`, no http/https
string, no analytics or advertising SDK, no `AdSupport`, no
`ATTrackingManager`, no location, and no third-party dependency anywhere in
`SingingStairs/`. Persistence is `UserDefaults` holding game settings only.
The microphone path is an `AVAudioEngine` `installTap` feeding a pitch
estimator — there is no `AVAudioRecorder` and nothing writes a file.

So: answer **"No, we do not collect data from this app"** and the section is
done. On-device audio processed and discarded without leaving the device is
explicitly not "collection" under Apple's definition — that is the correct
answer, not a loophole.

### Age Rating → **4+**

Every content question answers None / No: no violence of any kind, no
profanity, no sexual content, no nudity, no alcohol/tobacco/drugs, no
gambling, no horror, no contests, no unrestricted web access, no
user-generated content, no messaging, no advertising, no purchases.

### Export compliance

2.0's `Info.plist` sets `ITSAppUsesNonExemptEncryption = false`, so uploads
don't stop to ask. Confirm the same key is in 1.0's `Info.plist` — the app
uses no encryption, so `false` is correct.

---

## 7. Screenshots

Required: one iPhone set at the **6.9-inch** size. (Apple's required sizes
shift; confirm what App Store Connect asks for at upload time.) Up to ten
images, and the first two or three are the only ones most people see.

Suggested order:
1. The staircase in the night sky, letters awake — the whole idea in one picture
2. The playground picker
3. The swing, mid-arc, with the note showing
4. Song time with a lyric lit syllable by syllable
5. Sing it back with the star riding the staircase
6. The mystery singer, curtain open

If 1.0's UI test suite matches 2.0's, it already drives every one of these
screens and already exports `XCTAttachment` screenshots — turning that into a
store-screenshot generator is a small, well-scoped change. It has to run on a
Mac, and I'd need 1.0 reachable (§2).

---

## 8. App Review notes — paste into the review form

```
Singing Stairs is an offline ear-training app for young children. It requires
no account and no sign-in, and there is nothing to purchase.

MICROPHONE: two of the nine games ("Sing together" and "Sing it back") ask
for microphone access so the app can estimate the pitch of a sung note and
display it on the staircase. Audio is analysed in memory and discarded
immediately — it is never recorded, stored or transmitted. The app contains
no recording feature and no networking code of any kind. If microphone
permission is declined, those two games explain that they need it and the
other seven games plus the playground are fully usable.

TO TEST THE MICROPHONE GAMES quickly: open "Sing it back", allow the
microphone, and hum any steady note. An on-screen level meter shows the app
is hearing input, and a readout names the note being sung. Humming is
detected more reliably than sung words. The app judges pitch class only, so
humming in any octave will register.

The app works fully in airplane mode; this is expected.

"Grown-ups" settings are behind a deliberate 1.2-second press-and-hold on the
button in the bottom right.
```

---

## 9. Build and upload — commands for Josh's Mac

Written against 2.0's project layout; adjust the scheme and project names if
1.0's differ. From 1.0's repo root:

```sh
# 1. Run the tests first — they catch real regressions
xcodebuild test -project SingingStairs.xcodeproj -scheme SingingStairs \
  -destination "platform=iOS Simulator,name=iPhone 16 Pro"

# 2. Archive
xcodebuild archive -project SingingStairs.xcodeproj -scheme SingingStairs \
  -destination "generic/platform=iOS" \
  -archivePath build/SingingStairs.xcarchive

# 3. Export for the App Store (needs an ExportOptions.plist with
#    method=app-store-connect and the team id)
xcodebuild -exportArchive -archivePath build/SingingStairs.xcarchive \
  -exportOptionsPlist ExportOptions.plist -exportPath build/export

# 4. Upload
xcrun altool --upload-app -f build/export/SingingStairs.ipa -t ios \
  --apiKey ZRL2ZT22XY --apiIssuer cd73ce4b-4549-4afb-ab2f-ec1d8c5fab7a
```

Bump `CURRENT_PROJECT_VERSION` for each upload — Apple rejects a build number
it has already seen. Since 1.0 has been to TestFlight, the next build number
must be higher than whatever is up there now.

---

## 10. Order of operations

1. Josh: Paid Apps agreement + bank + tax + Small Business Program
   **(start here — it has the longest wait and everything else is quick)**
2. Josh: confirm the ASC app record and bundle id (§4)
3. Merge this branch so the privacy and support URLs go live
4. Optional: push 1.0 to GitHub, which hands me items 18–19
5. Josh's Mac: run tests, archive, upload
6. Josh or me (with the key): metadata, screenshots, $0.99
7. Josh: Submit for Review
8. Review: usually 24–48 hours. Microphone-plus-children is the combination
   most likely to draw a question, which is what §8 is written to pre-empt.

---

## 11. URLs (live once this branch merges to `main`)

- **Privacy Policy URL** — `https://joshgreenman1973.github.io/experiments/singing-stairs/privacy.html`
- **Support URL** — `https://joshgreenman1973.github.io/experiments/singing-stairs/support.html`

Both are required fields, and Apple rejects submissions where they 404.
Confirm they load before submitting.
