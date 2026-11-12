# Who represents New York City

A contact directory for everyone elected to represent the five boroughs: the two U.S. senators, the 13 House members whose districts take in part of the city, the governor and other statewide officials, 28 State Senate seats, 65 Assembly seats, the mayor, comptroller and public advocate, five borough presidents, five district attorneys and the 51 City Council members. People who won seats on Nov. 3, 2026 that they do not hold yet are listed beside the officials they are set to replace.

Each row gives the office's published phones, addresses and email, and under "Named staff" the people who work there whose direct line or address the office has published.

## Build

```
python3 scrape/build_base.py     # official rosters in raw/ -> data/base.json
python3 scrape/verify_staff.py   # re-fetch the source page behind every researched contact
python3 build.py                 # -> index.html, data/directory.csv, data/staff.csv
python3 -m http.server 8172
```

`raw/` (the pages as fetched on Nov. 10, 2026, 22 MB) and the research files (`data/staff_*.json`, `data/elect_research.json`, `data/unverified.json`) are kept on the build machine and out of the repository. The research files include notes about contacts that failed the check, which should not be republished. What is committed is the result: `data/base.json`, `index.html` and the two CSVs. Rerunning the build needs those local files.

## Sources

| What | Source |
|---|---|
| House members, Washington offices | House Clerk member roster (`clerk.house.gov/xml/lists/MemberData.xml`) |
| House district offices | each member's own office page |
| U.S. senators | Senate contact directory XML and each senator's office-locations page |
| State senators | each senator's contact page on nysenate.gov |
| Assembly members | nyassembly.gov/mem/ |
| City Council | council.nyc.gov/districts/ and each member's page |
| Statewide, citywide, borough offices | each office's contact page |
| Senior staff lines in city offices | the city Green Book, through `../nyc-green-book/docs/data/greenbook.json` |
| Other named staff | press releases, newsletters and staff pages found by web research (`data/staff_*.json`), each with its source URL |
| Election winners | NYC Board of Elections unofficial election night results (enr.boenyc.gov) |
| Which boroughs a district covers | the county breakdown in those same results |

## Rules the build enforces

**Nothing is typed from memory.** Rosters are parsed. Where an office's page has no common layout (House district offices, the executive offices), the address and phone are written out in `build_base.py` and `must_have()` checks every one against the saved page. The build stops if a string is missing.

**No address is constructed.** An email or phone appears only if a page published it.

**Researched contacts are checked twice.** Staff contacts came from web research, and a search tool can return an address that only looks right. `verify_staff.py` downloads each cited page again and looks for the same characters. Anything it cannot find goes to `data/unverified.json` and stays out of the directory. A phone that turns out to be the office's main line is dropped from the staff member's entry, since it is already in the row.

**Old contacts are left out or marked.** A staff contact whose source page dates to 2022 or earlier is dropped. One from 2023 or 2024, or from an undated staff page, carries a caution. Where the Green Book and an office's own page disagree, the office's page wins, and for the two city offices that changed hands on Jan. 1, 2026 (comptroller, Manhattan borough president) the Green Book's staff listing is not used at all because it still shows the previous officeholder's staff.

**Close races stay open.** A seat is marked "not final" where the leader was ahead by fewer than six points in the unofficial count.

## Known limits

- Results are unofficial and uncertified. For the four districts that cross the city line (NY-3, NY-16, Senate 34 and 36) the city count covers the city portion only.
- Staff rosters go stale. Each staff entry carries the date of the page it came from where one exists.
- The Green Book lags after staff changes in city offices.
- governor.ny.gov blocks scripted requests. The governor's and lieutenant governor's contacts are checked against the Internet Archive's copies of the same pages (`data/archive_copies.json` pins the copy used).
- Assembly offices publish little: 22 of the 65 city members have a named staff member with a contact. Direct phone numbers are rare everywhere outside the borough presidents' and district attorneys' offices.
- Titles for some congressional staff come from the invitee lists attached to House Clerk travel filings, which a trip's sponsor writes, not the office.
