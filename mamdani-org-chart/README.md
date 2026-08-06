# Who runs New York City

An organizational chart of the Mamdani administration: every senior appointee
arranged by who reports to whom, each linked to its source, with departments that
open into their own charts.

**Live: https://joshgreenman1973.github.io/experiments/mamdani-org-chart/**

## Three sources

**The top layer** is 140 appointees, built from `../mamdani-appointee-tracker/data.json`,
where every person carries a link to the press release or news report that named
them. A snapshot of exactly what went into the page is written to `data/roster.json`
on every build, so this folder can rebuild itself even if the tracker is not checked
out beside it.

**Reporting lines and the offices no announcement covered** come from the city's own
agency file, `t3jq-9nkf`, snapshotted by `refresh_governance.py` into `data/governance.json`
so a change in it shows up as a reviewable diff. 132 of its 306 organizations carry a
published reporting line. 59 boxes are sourced to it, and 24 offices it lists that no
announcement covered are carried at the foot of the column it assigns them to, marked
as the city's listing rather than an announcement. Matching is exact or by a hand-written
alias, never by containment: a containment match tied Children's Services to an office
under Mass Engagement.

**The department layer** is fetched at runtime from
[the Greener Book](https://joshgreenman1973.github.io/nyc-green-book/), which rebuilds
from the city's Green Book, the agency governance file and the City Record every four
hours. Both sites are on the same origin, so the chart reads its sibling's data file
directly. That layer therefore stays current with no rebuild here. 48 boxes open into
a published chart, down to the division level; the rest have none published and say so.
Where the City Record has published a personnel action for someone in that chart, their
last action and salary appear under their name.

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

Rebuild after any change to the tracker. Run `python3 refresh_governance.py` to pull a
fresh snapshot of the city's agency file; it refuses to write a short read.

## Using it

- Click any box to open the person, their announcement, the agency page, the
  department's own chart, and the published contacts: the officeholder's direct line
  where the Green Book lists one, the agency main line, and the press office with its
  email. Emails come only from the city's published press-contact page; none is
  inferred from a name pattern.
- Columns run deputy mayors first, then the other officials who report to the mayor.
- Where a bare reporting line would misdescribe an office, the Charter provision that
  governs it is quoted. The Department of Investigation is the case that prompted it.
- Every open box is deep-linkable: `#gregory-anderson` opens Sanitation.
- Search covers both layers. It matches the chart's own boxes and every person
  inside every department chart, by name, title or division, so searching a deputy
  commissioner's surname finds them even though their name is three clicks deep. The
  directory feed is fetched on the first search; matches appear above the chart, the
  boxes their departments sit behind light up, and clicking a result opens that
  department and scrolls to the person.
- The status filter narrows to new, retained or pending appointees. Zoom fits more
  columns on screen. Escape closes.
- The page prints in landscape.

## Reporting lines

The city publishes 132 of them in `t3jq-9nkf`, which is the source used here. Open any
box and it shows where that file puts the office, and says so plainly if this chart
shows it somewhere else. The file is updated annually and still carries a few portfolio
names from the last administration; those are mapped to the post that absorbed the work
in `CITY_PORTFOLIO`, and the ones with no successor are left out rather than guessed at.
Offices with no published line sit in their own column. Where the Green Book and the
governance file name different agency heads, both are shown with the reason one is
preferred.
