# Sweep

An iPhone app for New York City alternate side parking. Tap "I parked here" and Sweep finds the
block and side of the street in the city's street-cleaning sign records, then sends a
notification the evening before cleaning (8 pm by default) and an hour before it starts. Both
times can be changed in the app. Grew out of the private "Street cleaning near 160 5th Ave and
47 Plaza St W" artifact, which covered two quarter-mile circles; this covers the whole city.

"Map of cleaning days" draws every block face with a broom sign, on the side of the street it
applies to: colored by weekday, by one chosen day, or by how soon the next cleaning is if you
park now (holiday suspensions skipped). Tap a line to see both sides and park there.

"How to parallel park" is the six-step lesson from the "Parallel parking two Kias" artifact
(`ios/Sweep/Web/parking.html`, shown in a web view, offline). It defaults to the 2027 Kia Seltos;
anyone can pick a typical compact, midsize sedan, midsize SUV or large SUV/pickup, or enter their
own length and turning circle. For each car it searches for a stopping point, angle and gap that
clear the parked cars, so the drawn path never touches anything.

"Share the car with someone" shares the parked car between two phones through iCloud (CloudKit,
container `iCloud.com.joshgreenman.sweep`, `ios/Sweep/CarShare.swift`). The first person's phone
makes a private zone ("Car") holding one record ("car": the parked spot as JSON in `payload`, and
`changedAt`) and shares the whole zone; the invitation goes out by Messages or Mail, and the other
person taps it once. Either phone can park or mark the car moved; the newest change wins. A silent
push tells the other phone to fetch, so its reminders and calendar events move too. The record type
is deployed to Production in the CloudKit console. Not available in the Mac preview (unsigned).

**In the car and on the lock screen** (no CarPlay app; that needs Apple's parking entitlement):
- Siri, also through CarPlay: "I parked with Sweep" parks on the nearest block side with a broom
  sign; "When do I move the car with Sweep"; "I moved the car with Sweep" (`ios/Sweep/Intents.swift`).
- The "Move by" widget (`ios/SweepWidget/`), small, lock-screen rectangle and inline. iOS 26 and later
  show small widgets in CarPlay too. The widget has no sign data: the app writes the next four
  weeks of windows into the app group `group.com.joshgreenman.sweep` (`ios/SweepShared/CarSnapshot.swift`)
  each time the car or schedule changes, so it says "Open Sweep to update" if the app goes unopened
  for a month.
- A live card (lock screen, Dynamic Island, CarPlay dashboard) when cleaning starts within eight
  hours. Apple caps a live card at eight hours and lets an app start one only while it's open or
  from Siri, so it appears when you open Sweep or park by voice on cleaning day.

The widget is its own target with its own bundle id (`com.joshgreenman.sweep.widget`) and profile
(`ios/widget_profile_uuid.txt`, `python3 tools/asc_setup.py widget`). `release.sh` gives the app
and widget the same build number.

TestFlight only: internal group "Me" and external group "Friends" (add each new build to "Friends" by hand). App Store Connect app 6834559962, bundle id
`com.joshgreenman.sweep`. Never submit to the public App Store without asking Josh.

## Data

- **Signs:** NYC DOT Parking Regulation Locations and Signs (`nfid-uabd`), every current sign with
  the sanitation broom (about 195,000). `python3 tools/build_data.py --refresh` re-downloads them
  and writes `ios/Sweep/Data/faces.json` + `points.bin`, about 56,600 block faces. About 2,100 faces
  have no sign with coordinates and are left out. Where a face's signs disagree (about 740), the app
  uses the most common rule and says that another sign reads differently.
- **Block geometry:** signs only stand along part of a block, and a side with one sign would draw
  as a dot. So the build matches each face to NYC Street Centerline (`inkn-q76z`, cached in
  `tools/cache/centerline.json`) by street name and distance, follows that street to the corners,
  trims a few meters at each end and pushes the line out to the curb on the side the signs are on.
  About 93 percent of faces get a full block this way; the rest (no same-name street within 25 m,
  mostly named plazas, ramps and service roads) keep the sign points.
- **Holidays:** DOT's suspension calendar file,
  `https://www.nyc.gov/html/dot/downloads/misc/<year>-alternate-side.ics`. 2026 ships in the app;
  the app downloads this year and next each time it opens. nyc.gov returns 403 to curl's default
  user agent, so the app sends its own.
- **Not covered:** snow and emergency suspensions (311 has them through an API that needs a key).

## Build and ship (from `ios/`)

- `../tools/test_logic.sh` runs the matching, schedule and holiday checks on the Mac.
- `../tools/mac_preview.sh -sweepPick 40.674783,-73.976351` builds a Mac Catalyst copy in a temp
  folder and opens the block picker; `-sweepDemoParked <lat,lon>` opens the parked screen.
  `-sweepMap` opens the map from the park screen; `-sweepMapTap <lat,lon>` selects the nearest block once
  (clicks from computer use arrive as accessibility presses, so they can't tap the map itself).
  (No iOS simulator runtime is installed on this Mac.)
- `python3 tools/asc_setup.py profile` mints and installs the App Store profile (manual signing,
  distribution certificate Q2742CLDGU).
- `./tools/release.sh --upload` archives, exports and uploads. Build numbers are minutes since 1970.
- `python3 tools/testflight.py --wait` checks the internal group and build processing.
- `swift tools/make_icon.swift` redraws the icon.
