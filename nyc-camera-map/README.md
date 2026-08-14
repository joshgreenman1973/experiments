# Line of Sight — every camera (that we know about)

A layered map of every camera in New York City that can be accounted for from public
evidence: 5,697 individually located devices, plus a 2021 volunteer census that counted
28,950 cameras at 14,097 street corners.

New York City does not publish a map of the cameras watching its streets. This one is
assembled from four kinds of evidence, kept in separate layers because they are not
equally reliable.

## Layers

| Layer | Count | Evidence | Source |
|---|---:|---|---|
| DOT traffic cameras | 940 | Official | NYC DOT Traffic Management Center feed |
| School zone speed cameras | 2,107 | Derived from tickets | DOF violations, code 36 |
| Red light cameras | 628 | Derived from tickets | DOF violations, code 7 |
| Bus lane cameras | 170 | Derived from tickets | DOF violations, code 5 |
| Licence plate readers | 1,194 | Crowdsourced | OpenStreetMap / DeFlock |
| Other cameras logged | 635 | Crowdsourced | OpenStreetMap |
| Gunshot detectors | 23 | Crowdsourced | OpenStreetMap |
| Cameras counted at corners, 2021 | 28,950 at 14,097 corners | Volunteer census | Amnesty International |

## The derived layers

The city refuses to release the locations of its automated enforcement cameras. A DOT
spokesman told *West Side Rag* in August 2026 that keeping the sites secret makes the
program more effective.

Every ticket a camera writes, however, records the corner it was written at, and those
tickets are public. Grouping the Department of Finance's fiscal 2026 violations file
(`pvqr-7yc4`) by location collapses roughly 5.5 million camera tickets into the set of
corners that were issuing them.

Three violation codes are written by fixed cameras rather than by a person:

| Code | Description | Distinct locations | Mapped |
|---|---|---:|---:|
| 36 | PHTO SCHOOL ZN SPEED VIOLATION | 2,254 | 2,107 (93.5%) |
| 7 | FAILURE TO STOP AT RED LIGHT | 660 | 628 (95.2%) |
| 5 | BUS LANE VIOLATION | 183 | 170 (92.9%) |

Code 12 (mobile bus lane) is excluded: those cameras are mounted on buses and have no
fixed corner.

### Turning a ticket into a point

1. **Reassemble.** Finance splits each location across two 20-character columns,
   `street_name` and `intersecting_street`. `"SB WILDER AVE @ AMBE"` + `"R ST"` is one
   location, not two. Where the first column is full to 20 characters the two are
   concatenated directly; otherwise a trimmed space is restored.
2. **Parse.** Split on `@` and strip the travel direction, which appears either as a
   prefix (`WB N CONDUIT AVE`) or in parentheses (`ASTORIA BLVD S (E/B)`). The direction
   is kept — it says which way the camera faces.
3. **Normalize.** The two sources spell the same street differently. Centerline says
   `AVE N` and `88 ST`; a ticket says `AVENUE N` and `88TH ST`. Suffixes are collapsed to
   one canonical token, ordinals stripped, spelled-out ordinals converted (`THIRD` → `3`),
   and glued words separated (`235THST` → `235 ST`, `E149TH ST` → `E 149 ST`).
4. **Match.** Look the street pair up in an intersection gazetteer built from the city's
   Centerline file (`inkn-q76z`): all 122,244 segment endpoints snapped to an 11-metre
   grid, with the street names touching each node collected into pairs. 55,676 pairs.
5. **Fall back.** The location field caps at 40 characters, so the second street is often
   cut off mid-word (`SPRINGFIELD BL`, `MANHATTAN COLLE`). Unmatched names are retried
   against street names that begin with the fragment, then against close spellings.
   Anything matched this way is flagged **approximate** in the interface.

Roughly one location in fifteen still fails, almost all of them highway ramps and service
roads whose names in the ticket system have no counterpart in Centerline. They are
counted in the totals but not drawn.

### Caveats on the derived layers

- A camera that wrote no tickets in the period leaves no trace here.
- The fiscal 2026 file carries issue dates from July 2024 through June 2026. A corner in
  these layers was ticketing at some point in that window, not necessarily today. The
  first and last ticket dates are shown for each camera.
- Red light cameras expanded from 150 intersections to a planned 600 during 2026, so that
  layer is a snapshot of a moving target.

## Overlap between layers

Nothing here should be added into a single grand total.

- The headline figure of 5,697 counts only individually located devices. The 2021 survey
  is never added to it. That layer counts cameras *visible from* a corner, and about 3,317
  of its 28,950 were on poles and street furniture rather than buildings — which is to
  say, many of them are the traffic and enforcement cameras already drawn as their own
  layers.
- 162 of the 1,194 crowdsourced plate readers sit within 40 metres of an enforcement
  camera reconstructed independently here. Each is flagged in its detail panel. They are
  kept rather than deleted, because a plate reader and a ticketing camera can genuinely
  share a pole.
- The three enforcement layers cannot overlap each other; each comes from a different
  violation code.

## What is missing

The NYPD's own camera network (the Domain Awareness System draws on thousands of cameras,
none of them published), the SafeCam registry of private cameras, subway and bus cameras,
congestion pricing readers, and the great majority of private cameras beyond whatever the
2021 volunteers happened to see from an intersection.

There are no Flock Safety cameras in New York City. The NYPD, DOT and MTA have all said
they do not contract with the company.

## Rebuilding

```bash
./scripts/fetch_sources.sh              # every upstream input into raw/
python3 scripts/build_intersections.py   # gazetteer from Centerline
python3 scripts/locate_cameras.py            # tickets -> coordinates
python3 scripts/build_layers.py              # all layers -> data/
```

`raw/` is not tracked — it is roughly 60MB of upstream files that `fetch_sources.sh`
re-downloads on demand. Everything the map serves lives in `data/`.

Every step fails loudly on an empty or undersized result rather than writing a thin file.

## Sources

- NYC DOT Traffic Management Center, `webcams.nyctmc.org/api/cameras`
- NYC Open Data: Parking Violations Issued — Fiscal Year 2026 (`pvqr-7yc4`),
  Centerline (`inkn-q76z`), Borough Boundaries (`gthc-hcne`)
- Amnesty International, [Decode Surveillance NYC](https://github.com/amnesty-crisis-evidence-lab/decode-surveillance-nyc), 2021–22
- OpenStreetMap contributors, via the Overpass API, retrieved August 2026
- Gus Saltonstall, "An Upper West Side Flock Camera Map Misunderstanding,"
  [West Side Rag](https://www.westsiderag.com/2026/08/13/an-upper-west-side-flock-camera-map-misunderstanding), Aug. 13, 2026

Built with AI assistance. The enforcement layers are reconstructed by an automated
pipeline, not copied from an official list. Check any specific camera against the street
before relying on it.
