# Who runs New York City, corrected

A navigable organizational chart of the Mamdani administration. It exists because
the chart everyone is passing around, circulated by the lobbying firm Immortal
Strategies on July 27, 2026, has errors in it. Then it goes further than that chart
does: click a department and its own org chart opens in place, down to the division
level.

**Live: https://joshgreenman1973.github.io/experiments/mamdani-org-chart/**

## Two layers

**The top layer** is 140 sourced appointees, built from `../mamdani-appointee-tracker/data.json`,
where every person carries a link to the press release or news report that named
them. A snapshot of exactly what went into the page is written to `data/roster.json`
on every build, so this folder can rebuild itself even if the tracker is not checked
out beside it.

**The department layer** is fetched at runtime from
[the Greener Book](https://joshgreenman1973.github.io/nyc-green-book/), which rebuilds
from the city's Green Book, the agency governance file and the City Record every four
hours. Both sites are on the same origin, so the chart reads its sibling's data file
directly. That layer therefore stays current with no rebuild here. 48 boxes open into
a published chart; the rest say so rather than inventing one.

## What it fixes

| The circulated chart says | It is actually | Where |
|---|---|---|
| Melanie Herzog | Melanie **Hartzog** | MTA board |
| Phylisa Wilson | Phylisa **Wisdom** | Office to Combat Antisemitism |
| Dr. Helen Artega | Helen **Arteaga** | deputy mayor for health and human services |
| Jason Graham, Chief Medical Officer | Chief Medical **Examiner** | a different job |
| Kristin Booth Glen | **Kristen** Booth Glen | judiciary committee |
| Jared M. Trujilio | Jared M. **Trujillo** | judiciary committee |
| Trisha Shimamura | **Tricia** Shimamura | Parks and Recreation |
| Christine Clark | Christine **Clarke** | Commission on Human Rights |
| Maya Hanada | Maya **Handa** | World Cup |
| Emily Liss | **Emmy** Liss | Child Care |
| 17 committee members | **18** | it omits Everett Hopkins |
| 4 rent board members | **6** | it omits Maksim Wynn and Adan Soltren |
| Office of MBWE, LGBTIA+, Nonprofit Servies, Close Riker's | M/WBE, LGBTQIA+, Services, Rikers | spelling |

Every one was checked against the source PDF and against an official announcement.
The chart also lists the chancellor of the City University of New York, who is chosen
by the university's trustees rather than the mayor, so that entry is not reproduced.
Roughly 50 missing appointees are restored.

## Build

```
python3 build.py
python3 -m http.server 8155
# open http://localhost:8155
```

`build.py` fills `template.html`. No name, title, date or link is typed by hand, so
the chart cannot drift from the tracker. The two things this project owns are the
`COLUMNS` mapping, which says who reports to whom, and `DEPTS`, which maps a box to
its Green Book agency. `DEPTS` was written by hand and the build fails loudly if an
agency name in it stops matching, because fuzzy matching produced false positives bad
enough to mislead: it paired the public utility advocate with the public advocate,
and the tenant protection office with the commission to combat police corruption.

Rebuild after any change to the tracker.

## Using it

- Click any box to open the person, their announcement, the agency page and the
  department's own chart.
- Every open box is deep-linkable: `#gregory-anderson` opens Sanitation.
- Search matches names and agencies. The status filter narrows to new, retained or
  pending appointees. Zoom fits more columns on screen. Escape closes.
- The page prints in landscape.

## Reporting lines

The city publishes very few of them. Where the circulated chart asserts a line that no
official source states, this chart does not adopt it, and offices with no published
line sit in their own column rather than being assigned to a guess. Where the Green
Book and the governance file name different agency heads, both are shown with the
reason one is preferred.
