#!/usr/bin/env python3
"""
Fetch latest DOC data from NYC Open Data Socrata APIs and update data.json.

Metrics updated:
  - Jail population (live snapshot count) from 7479-ugqb
  - Assaults on staff (incident count by month) from erra-pzy8
  - Fights (incident count by month) from k548-32d3
  - Stabbings/slashings (incident count by month) from gakf-suji

Also updates:
  - deaths-data.json and rikers-death-tracker/data.json monthlyPopulation
  - Top-line "cards" array with latest values and month-over-month change
  - currentYear.adpSnapshot with fresh population count

Population note: dataset 7479-ugqb is a live daily snapshot of all people
currently in DOC custody (pre-trial detainees, city-sentenced, state-ready,
parole violators -- all statuses). It does NOT retain historical records for
discharged individuals, so we can only get today's count, not reconstruct
past months. Historical population data comes from the NYC Comptroller DOC
Dashboard and must be updated manually or via that source.

Run: python3 doc-dashboard/update-data.py
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime, date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent  # /Users/.../Experiments
DOC_DATA = REPO / "doc-dashboard" / "data.json"
DEATHS_DATA = REPO / "doc-dashboard" / "deaths-data.json"
RIKERS_DATA = REPO / "rikers-death-tracker" / "data.json"

BASE = "https://data.cityofnewyork.us/resource"

# Socrata dataset IDs
POPULATION_ID = "7479-ugqb"   # Daily Inmates In Custody (live snapshot)
ASSAULTS_ID = "erra-pzy8"     # Inmate Assault on Staff
FIGHTS_ID = "k548-32d3"       # Inmate Incidents - Inmate Fights
STABBINGS_ID = "gakf-suji"    # Inmate Incidents - Slashing and Stabbing


def socrata_get(dataset_id, query):
    """Fetch from Socrata API with SoQL query."""
    url = f"{BASE}/{dataset_id}.json?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def month_label(year, month):
    """Return 'Mon YYYY' format, e.g. 'Jan 2026'."""
    return datetime(year, month, 1).strftime("%b %Y")


def month_key_to_tuple(label):
    """Parse 'Jan 2026' -> (2026, 1)."""
    dt = datetime.strptime(label, "%b %Y")
    return (dt.year, dt.month)


def existing_months(series):
    """Return set of (year, month) tuples already in a series."""
    result = set()
    for entry in series:
        try:
            result.add(month_key_to_tuple(entry["month"]))
        except (KeyError, ValueError):
            pass
    return result


def get_last_month(series):
    """Get the (year, month) of the last entry in a series."""
    if not series:
        return (2019, 1)
    last = series[-1]["month"]
    return month_key_to_tuple(last)


def get_pop_for_month(pop_series, yr, mo):
    """Look up population for a given month from the population series."""
    label = month_label(yr, mo)
    for entry in pop_series:
        if entry["month"] == label:
            return entry["population"]
    return None


# ── POPULATION: live snapshot count ──

def fetch_current_population():
    """Count all people currently in DOC custody (all status codes)."""
    query = {"$select": "count(*) as pop", "$limit": 1}
    try:
        rows = socrata_get(POPULATION_ID, query)
        if rows and "pop" in rows[0]:
            pop = int(rows[0]["pop"])
            print(f"  Current population (today): {pop}")
            return pop
    except Exception as e:
        print(f"  Population fetch FAILED: {e}")
    return None


# Status code labels for the breakdown
STATUS_LABELS = {
    "DE": "Pre-trial detainee",
    "DEP": "Detainee pending",
    "DPV": "Detainee parole violator",
    "CS": "City sentence",
    "CSP": "City sentence parolee",
    "SSR": "State sentence ready",
    "DNS": "Detained, not sentenced",
}


def fetch_population_breakdown():
    """Get population count by inmate status code."""
    query = {
        "$select": "inmate_status_code, count(*) as cnt",
        "$group": "inmate_status_code",
        "$order": "cnt DESC"
    }
    try:
        rows = socrata_get(POPULATION_ID, query)
        breakdown = []
        for row in rows:
            code = row["inmate_status_code"]
            cnt = int(row["cnt"])
            breakdown.append({
                "code": code,
                "label": STATUS_LABELS.get(code, code),
                "count": cnt
            })
        return breakdown
    except Exception as e:
        print(f"  Population breakdown FAILED: {e}")
        return None


# ── INCIDENT COUNTS: group by month ──

def fetch_incident_months(dataset_id, date_field, after_year, after_month):
    """Fetch monthly incident counts after the given month."""
    # Start from the 1st of the month AFTER the last one we have
    next_mo = after_month + 1
    next_yr = after_year
    if next_mo > 12:
        next_mo = 1
        next_yr += 1
    start = f"{next_yr}-{next_mo:02d}-01"

    query = {
        "$select": f"date_trunc_ym({date_field}) as month, count(*) as cnt",
        "$where": f"{date_field} >= '{start}'",
        "$group": f"date_trunc_ym({date_field})",
        "$order": f"date_trunc_ym({date_field})",
        "$limit": 50
    }
    try:
        rows = socrata_get(dataset_id, query)
    except Exception as e:
        print(f"  Fetch failed for {dataset_id}: {e}")
        return []

    results = []
    today = date.today()
    for row in rows:
        if "month" in row and "cnt" in row:
            dt = datetime.fromisoformat(row["month"].replace("T00:00:00.000", ""))
            # Only include complete months (not the current partial month)
            if date(dt.year, dt.month, 1) < date(today.year, today.month, 1):
                results.append((dt.year, dt.month, int(row["cnt"])))
    return results


def update_cards(data, pop_series, assault_series, stab_series, current_pop):
    """Update the top-line cards with latest values."""
    cards = data.get("cards", [])

    # Update population card with live count
    if current_pop is not None:
        for card in cards:
            if card["metric"] == "jail population":
                prev_val = card.get("value", 0)
                card["value"] = current_pop
                card["change"] = current_pop - prev_val
                card["asOf"] = date.today().strftime("%B %-d")
                break

    # Update incident cards
    def update_incident_card(metric_name, series):
        if len(series) < 2:
            return
        latest = series[-1]
        prev = series[-2]
        for card in cards:
            if card["metric"] == metric_name:
                card["value"] = latest["count"]
                card["change"] = latest["count"] - prev["count"]
                card["asOf"] = latest["month"]
                return

    update_incident_card("assaults on staff", assault_series)
    update_incident_card("slashing stabbing", stab_series)

    data["cards"] = cards


def update_monthly_population(deaths_data, yr, mo, pop):
    """Update a single month in monthlyPopulation."""
    mp = deaths_data.get("monthlyPopulation", {})
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    yr_str = str(yr)
    if yr_str not in mp:
        mp[yr_str] = {}
    mp[yr_str][month_names[mo - 1]] = pop
    deaths_data["monthlyPopulation"] = mp


def main():
    print("Loading data files...")
    with open(DOC_DATA) as f:
        data = json.load(f)
    with open(DEATHS_DATA) as f:
        deaths = json.load(f)
    with open(RIKERS_DATA) as f:
        rikers = json.load(f)

    pop_series = data["population"]
    assault_series = data["assaults"]
    fight_series = data["fights"]
    stab_series = data["stabbings"]

    pop_last = get_last_month(pop_series)
    assault_last = get_last_month(assault_series)
    fight_last = get_last_month(fight_series)
    stab_last = get_last_month(stab_series)

    print(f"Current data ends: pop={month_label(*pop_last)}, "
          f"assaults={month_label(*assault_last)}, "
          f"fights={month_label(*fight_last)}, "
          f"stabbings={month_label(*stab_last)}")

    changed = False

    # ── Fetch current population ──
    print("\nFetching current population...")
    current_pop = fetch_current_population()
    breakdown = fetch_population_breakdown()
    if breakdown:
        data["populationBreakdown"] = {
            "asOf": date.today().isoformat(),
            "categories": breakdown
        }
        changed = True
        print("  Breakdown: " + ", ".join(b["code"] + "=" + str(b["count"]) for b in breakdown))
    if current_pop is not None:
        today = date.today()
        label = month_label(today.year, today.month)
        if (today.year, today.month) not in existing_months(pop_series):
            pop_series.append({"month": label, "population": current_pop})
            changed = True
            print(f"  Added {label}: {current_pop}")
        else:
            # Update existing month's value with fresh count
            for entry in pop_series:
                if entry["month"] == label:
                    if entry["population"] != current_pop:
                        entry["population"] = current_pop
                        changed = True
                        print(f"  Updated {label}: {current_pop}")
                    break

        # Update monthlyPopulation in deaths files
        update_monthly_population(deaths, today.year, today.month, current_pop)
        update_monthly_population(rikers, today.year, today.month, current_pop)

        # Update adpSnapshot
        for d in [deaths, rikers]:
            cy = d.get("currentYear", {})
            cy["adpSnapshot"] = current_pop
            cy["adpSnapshotDate"] = today.strftime("%Y-%m-01")

    # ── Fetch assaults ──
    print("\nFetching assaults on staff...")
    new_assaults = fetch_incident_months(ASSAULTS_ID, "reported_dt", *assault_last)
    for yr, mo, count in new_assaults:
        label = month_label(yr, mo)
        if (yr, mo) not in existing_months(assault_series):
            pop = get_pop_for_month(pop_series, yr, mo)
            entry = {"month": label, "count": count}
            if pop:
                entry["population"] = pop
            assault_series.append(entry)
            changed = True
            print(f"  Assaults {label}: {count}")

    # ── Fetch fights ──
    print("\nFetching fights...")
    new_fights = fetch_incident_months(FIGHTS_ID, "incident_dt", *fight_last)
    for yr, mo, count in new_fights:
        label = month_label(yr, mo)
        if (yr, mo) not in existing_months(fight_series):
            pop = get_pop_for_month(pop_series, yr, mo)
            entry = {"month": label, "count": count}
            if pop:
                entry["population"] = pop
            fight_series.append(entry)
            changed = True
            print(f"  Fights {label}: {count}")

    # ── Fetch stabbings ──
    print("\nFetching stabbings/slashings...")
    new_stabs = fetch_incident_months(STABBINGS_ID, "reported_dt", *stab_last)
    for yr, mo, count in new_stabs:
        label = month_label(yr, mo)
        if (yr, mo) not in existing_months(stab_series):
            pop = get_pop_for_month(pop_series, yr, mo)
            entry = {"month": label, "count": count}
            if pop:
                entry["population"] = pop
            stab_series.append(entry)
            changed = True
            print(f"  Stabbings {label}: {count}")

    if not changed:
        print("\nNo new data available.")
        return False

    # Update cards
    update_cards(data, pop_series, assault_series, stab_series, current_pop)

    # Update lastUpdated
    today_str = date.today().isoformat()
    data["lastUpdated"] = today_str

    # Write files
    print("\nWriting updated data files...")
    with open(DOC_DATA, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(DEATHS_DATA, "w") as f:
        json.dump(deaths, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(RIKERS_DATA, "w") as f:
        json.dump(rikers, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print("Done. Files updated.")
    return True


if __name__ == "__main__":
    main()
