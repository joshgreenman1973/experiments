#!/bin/zsh
# Save each 2024-25 NYSED Financial Transparency Report for the high schools in data/hs_2025_instids.csv
cd "$(dirname $0)/.."
tail -n +2 data/hs_2025_instids.csv | while IFS=, read beds dbn inst; do
  f=raw/fin2025/$inst.html
  [[ -s $f ]] && continue
  curl -sfL -o $f "https://data.nysed.gov/expenditures.php?year=2025&instid=$inst" || echo "fail $dbn $inst"
  sleep 0.3
done
ls raw/fin2025 | wc -l
