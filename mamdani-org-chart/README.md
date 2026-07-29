# Who runs New York City

An organizational chart of the Mamdani administration: every senior appointee
arranged by who reports to whom, each linked to its source, with departments that
open into their own charts.

**Live: https://joshgreenman1973.github.io/experiments/mamdani-org-chart/**

## Two layers

**The top layer** is 140 appointees, built from `../mamdani-appointee-tracker/data.json`,
where every person carries a link to the press release or news report that named
them. A snapshot of exactly what went into the page is written to `data/roster.json`
on every build, so this folder can rebuild itself even if the tracker is not checked
out beside it.

**The department layer** is fetched at runtime from
[the Greener Book](https://joshgreenman1973.github.io/nyc-green-book/), which rebuilds
from the city's Green Book, the agency governance file and the City Record every four
hours. Both sites are on the same origin, so the chart reads its sibling's data file
directly. That layer therefore stays current with no rebuild here. 48 boxes open into
a published chart, down to the division level; the rest have none published and say so.

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

The city publishes very few of them. Each office is grouped under the principal named
in official releases, and the offices whose line the city has not published sit in
their own column rather than being assigned to a guess. Where the Green Book and the
governance file name different agency heads, both are shown with the reason one is
preferred.
