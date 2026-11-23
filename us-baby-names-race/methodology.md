# The baby name horserace: methodology

## Source

Social Security Administration, national baby names file ("Beyond the Top 1000 Names," national data):
https://www.ssa.gov/oact/babynames/limits.html

The file has one text file per year, `yobYYYY.txt`, with one row per name and sex: `name,sex,count`. A name appears only if at least five babies of that sex got it that year.

SSA's server refuses automated downloads (it returns "Access Denied" to scripts), so `names.zip` was downloaded by hand from that page on Nov. 23, 2026. It is SSA's current release, 1880 through 2025.

Each release revises earlier years slightly as late card applications come in. Against the previous release (a GitHub copy, `dcadata/name-finder`, used for the first version of this page), 123 of the 145 overlapping years differ by a few births here and there; Linda's 1950 count went from 80,431 to 80,433. Figures here follow the current release.

Checks: Mary (7,065) and John (9,655) are No. 1 in 1880; Olivia (13,544) and Liam (20,818) are No. 1 in 2025; every name SSA lists as a No. 1 since 1880 comes out as No. 1 here (boys: John, Robert, James, Michael, David, Jacob, Noah, Liam; girls: Mary, Linda, Lisa, Jennifer, Jessica, Ashley, Emily, Emma, Isabella, Sophia, Olivia).

The data starts in 1880 because SSA's records do. There is no national count of baby names before 1880.

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

## Limits

- Ties are broken alphabetically. SSA's own rank lists can differ by a place in rare ties.
- Spellings are separate names (Catherine and Katherine), as in the source.
- The share denominator leaves out names given to fewer than five babies, so shares run slightly high.
- Social Security cards became common only after 1937. Records for earlier births mostly come from later applications, so early years undercount births and lean toward people who lived long enough to apply.
- Sex is as recorded on the application, female or male.
- 2025 is the latest year SSA has published.

Idea: the Institute for Family Studies' U.S. baby name browser, https://ifstudies.org/resources-and-tools/us-baby-name-browser
