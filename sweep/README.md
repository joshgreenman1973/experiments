# Sweep

An iPhone app for New York City alternate side parking. Tap "I parked here" and Sweep finds the
block and side of the street in the city's street-cleaning sign records, then sends a
notification the evening before cleaning (8 pm by default) and an hour before it starts. Both
times can be changed in the app. Grew out of the private "Street cleaning near 160 5th Ave and
47 Plaza St W" artifact, which covered two quarter-mile circles; this covers the whole city.

"Map of cleaning days" draws every block face with a broom sign, on the side of the street it
applies to: colored by weekday, by one chosen day, or by how soon the next cleaning is if you
park now (holiday suspensions skipped). Tap a line to see both sides and park there.

TestFlight only, internal group "Me". App Store Connect app 6834559962, bundle id
`com.joshgreenman.sweep`. Never submit to the public App Store without asking Josh.

## Data

- **Signs:** NYC DOT Parking Regulation Locations and Signs (`nfid-uabd`), every current sign with
  the sanitation broom (about 195,000). `python3 tools/build_data.py --refresh` re-downloads them
  and writes `ios/Sweep/Data/faces.json` + `points.bin`, about 56,600 block faces. About 2,100 faces
  have no sign with coordinates and are left out. Where a face's signs disagree (about 740), the app
  uses the most common rule and says that another sign reads differently.
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
