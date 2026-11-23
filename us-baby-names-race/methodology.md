# The baby name horserace: methodology

## Source

Social Security Administration, national baby names file ("Beyond the Top 1000 Names," national data):
https://www.ssa.gov/oact/babynames/limits.html

The file has one text file per year, `yobYYYY.txt`, with one row per name and sex: `name,sex,count`. A name appears only if at least five babies of that sex got it that year.

SSA's server refuses automated downloads (it returns "Access Denied" to scripts), so `names.zip` was downloaded by hand from that page on Nov. 23, 2026. It is SSA's current release, 1880 through 2025.

Each release revises earlier years slightly as late card applications come in. Against the previous release (a GitHub copy, `dcadata/name-finder`, used for the first version of this page), 123 of the 145 overlapping years differ by a few births here and there; Linda's 1950 count went from 80,431 to 80,433. Figures here follow the current release.

Checks: Mary (7,065) and John (9,655) are No. 1 in 1880; Olivia (13,544) and Liam (20,818) are No. 1 in 2025; every name SSA lists as a No. 1 since 1880 comes out as No. 1 here (boys: John, Robert, James, Michael, David, Jacob, Noah, Liam; girls: Mary, Linda, Lisa, Jennifer, Jessica, Ashley, Emily, Emma, Isabella, Sophia, Olivia).

The data starts in 1880 because SSA's records do. There is no national count of baby names before 1880.

## States

Source: SSA's state file, `namesbystate.zip`, from the same page, downloaded by hand Nov. 23, 2026. One file per state plus D.C. (`XX.TXT`, rows `ST,sex,year,name,count`), 1910 through 2025, counted by the state where the card application was filed. Same five-baby cutoff, applied within each state.

`python3 build.py states <folder of XX.TXT> states/` writes `states/XX.json` in the same format as `names.json`, ranked within each state.

Small states are thin. Wyoming, 2025: the 50th-ranked name went to 7 girls and 9 boys. Wyoming, 1910: only 23 girls' names and 14 boys' names cleared five babies. The page shows a warning above the charts when a state's 50th-ranked name in its latest year went to fewer than 25 babies of either sex, or when any year lists fewer than 50 names. In those states lower ranks rest on a handful of births and many ties, and top-50 coverage runs high because the uncounted names are missing from the denominator.

## Calculations

Done by `build.py` in this folder (`python3 build.py <folder of yobYYYY.txt files> names.json`; it uses whatever run of years the folder holds):

1. For each year and sex, sort names by count, highest first; ties go alphabetically. Rank = position in that list. Only the top 1,000 ranks are kept.
2. Keep every name that ranked 50th or better in at least one year from 1880 to 2025: 209 boys' names, 316 girls' names.
3. For each kept name, store its rank each year (0 = outside the top 1,000) and its share: count ÷ total of all listed names of that sex that year × 1,000 (the page shows this divided by 10, as a percent).
4. "First reached the top 50" = the earliest year the name ranked 50th or better. Names already in the top 50 in 1880 are grouped separately, since the data cannot say when they arrived.
5. For each year and sex, store top-50 coverage (counts of the 50 highest-ranked names ÷ all listed names × 100) and names in use (number of distinct names listed).

Output: `names.json` (`years`, `top`, then `sexes.boys` and `sexes.girls`, each a list of `{n, r, p, first, best, bestYr, yrsTop}` plus yearly `births` totals, `top50pct` and `distinct`).

## Figures on the page

- In the top 50 in both 1880 and 2025: 13 boys' names (Benjamin, Charles, Daniel, David, Henry, Jacob, James, John, Joseph, Michael, Samuel, Thomas, William) and 5 girls' names (Elizabeth, Ella, Emma, Grace, Lucy).
- In the top 50 every year, 1880 to 2025: John, James, William, Joseph and David for boys; Elizabeth for girls.
- Top-50 coverage: 1880, 70.3 percent of boys and 58.4 percent of girls; 2025, 25.0 and 21.4 percent. Boys' low point is 2025 (25.05 percent); girls' was 2023 (21.13 percent).
- Names in use: girls 942 (1880) and 17,297 (2025); boys 1,058 and 13,930. Only names given to five or more babies count, and early years are held down by the early-birth undercount.
- No. 1 shares: Mary, 7,065 of 90,994 girls listed in 1880 (7.8 percent); Olivia, 13,544 of 1,607,267 in 2025 (0.8 percent).

## Comebacks and all-time totals (national only)

Done by `analyze.py` (`python3 analyze.py <folder of yobYYYY.txt> analysis.json`), ranking every name in each year's file (not just the top 1,000), ties alphabetical.

- A **stretch** is a run of consecutive years at or above the cutoff (50th or 100th). More than one stretch = fell out and came back. Categories: never left (one stretch, 1880 to 2025); arrived and stayed (one stretch, began after 1880, in the list in 2025); left once, never came back (one stretch, out in 2025); left, came back, in now / gone again (two or more stretches, in or out in 2025). Names in the list in 1880 count as arriving in 1880.
- **Longest time away:** years between the end of one stretch and the start of the next.
- **Fastest arrivals:** years from the last year a name ranked below 1,000th (or was absent from the file) to its first year in the list. Limited to names first reaching the list after 1920; the 1880s files list so few names that "below 1,000th" is nearly meaningless then.
- **One year and done:** one stretch, one year long, before 2025.
- Repeat comebacks are often names hovering at the cutoff (Herman: eight stretches in the boys' top 50, 1880 to 1912). They are counted as they are.

Top 50, 1880 to 2025:
- Girls: 316 names ever; 266 first arrived after 1880; 215 left once and never came back; 60 came back at least once, 11 of them two or more times; 9 comebacks in now; 40 arrived and stayed; Elizabeth never left. Longest away: Lucy, 132 years (out after 1886, back 2019). Fastest arrival: Ailany, No. 1,055 in 2022 to No. 14 in 2025.
- Boys: 209 names ever; 159 after 1880; 122 left once for good; 51 came back, 17 of them two or more times; 14 comebacks in now; 31 arrived and stayed; 5 never left. Longest away: Theodore, 109 years (out after 1908, back 2018).

Top 100: girls 509 names ever, 126 came back at least once; boys 394, 95 came back; 12 boys' names and 1 girls' name never left.

**All-time totals:** each name's counts summed over 1880 to 2025. "Girls and boys together" adds both sexes' counts for the same spelling (James: 5,250,638 boys and 23,882 girls = 5,274,520). Shares divide by all babies listed: 375,362,447 (185,559,287 girls, 189,803,160 boys). Top 10 boys' names = 19.8 percent of all boys listed; top 10 girls' names = 8.8 percent of all girls. Pre-1937 undercounting understates names that peaked early.

## Limits

- Ties are broken alphabetically. SSA's own rank lists can differ by a place in rare ties.
- Spellings are separate names (Catherine and Katherine), as in the source.
- The share denominator leaves out names given to fewer than five babies, so shares run slightly high.
- Social Security cards became common only after 1937. Records for earlier births mostly come from later applications, so early years undercount births and lean toward people who lived long enough to apply.
- Sex is as recorded on the application, female or male.
- 2025 is the latest year SSA has published.

Idea: the Institute for Family Studies' U.S. baby name browser, https://ifstudies.org/resources-and-tools/us-baby-name-browser
