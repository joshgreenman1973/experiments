"""How fast do complaints arrive at the busiest addresses?

Reads build/cache/records/*.csv (from fetch_records.py) and writes
data/cadence.json plus a printed summary. All times are 311's created_date,
which is local New York time.

Measures, per address:
  busiest day and busiest clock hour
  most complaints in any rolling 60 minutes
  gaps between consecutive complaints: median, share under 1 minute and 10 seconds
  the longest stretch of complaints each under 2 minutes apart
  nights: on heavy days, the longest quiet stretch between noon and the next noon
  how complaints came in (phone, app, website)
"""
import glob, json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
HEAVY = 100   # a "heavy day" for the night test


def norm(s):
    return s.str.upper().str.strip().str.replace(r'\s+', ' ', regex=True)


def analyze(path):
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    name = os.path.basename(path)[:-4]
    addr, zipc = name.rsplit('_', 1)
    addr = addr.replace('_', ' ')
    d['a'] = norm(d.incident_address).str.replace(r' BLVD\b', ' BOULEVARD', regex=True)
    d = d[d.a == addr].copy()
    t = pd.to_datetime(d.created_date).sort_values().reset_index(drop=True)
    n = len(t)
    secs = (t - t.iloc[0]).dt.total_seconds().to_numpy()
    gaps = np.diff(secs)
    day = t.dt.normalize()
    per_day = day.value_counts()
    per_hour = t.dt.floor('h').value_counts()
    # Rolling 60 minutes: for each complaint, how many fall in the hour starting there.
    j = np.searchsorted(secs, secs + 3600, side='left')
    roll = int((j - np.arange(n)).max())
    # Longest run of complaints each under 2 minutes apart.
    brk = np.where(gaps >= 120)[0]
    starts, ends = np.r_[0, brk + 1], np.r_[brk, n - 1]
    i = int((ends - starts).argmax())
    best, best_span = int(ends[i] - starts[i] + 1), secs[ends[i]] - secs[starts[i]]
    run = t.iloc[starts[i]:ends[i] + 1]
    run_hours = run.dt.floor('h').value_counts().sort_index()
    runs_over_24h = int(((secs[ends] - secs[starts]) >= 86400).sum())
    # Nights: for days with >= HEAVY complaints, longest gap between noon and next noon.
    quiet = []
    for dd in per_day[per_day >= HEAVY].index:
        lo, hi = dd + pd.Timedelta(hours=12), dd + pd.Timedelta(hours=36)
        w = t[(t >= lo) & (t < hi)]
        if len(w) < 2:
            continue
        s = np.concatenate([[(lo - lo).total_seconds()], (w - lo).dt.total_seconds().to_numpy(),
                            [(hi - lo).total_seconds()]])
        quiet.append(np.diff(s).max() / 3600)
    quiet = np.array(quiet)
    hours = t.dt.hour.value_counts(normalize=True).reindex(range(24), fill_value=0)
    ch = d.open_data_channel_type.value_counts(normalize=True).round(3).to_dict()
    desc = (d.complaint_type + ': ' + d.descriptor).value_counts(normalize=True).head(3).round(3).to_dict()
    zero_sec = float((t.dt.second == 0).mean())
    yearly = t.dt.year.value_counts().sort_index().to_dict()
    busiest_year = max(yearly, key=yearly.get)
    yr = t[t.dt.year == busiest_year]
    yr_days = yr.dt.normalize().nunique()
    return {
        'address': addr, 'zip': zipc, 'n': n,
        'first': str(t.iloc[0]), 'last': str(t.iloc[-1]),
        'active_days': int(day.nunique()),
        'busiest_year': int(busiest_year), 'busiest_year_n': int(yearly[busiest_year]),
        'busiest_year_days': int(yr_days),
        'busiest_year_per_active_day': round(yearly[busiest_year] / yr_days, 1),
        'peak_day': str(per_day.idxmax().date()), 'peak_day_n': int(per_day.max()),
        'peak_clock_hour_n': int(per_hour.max()), 'peak_rolling_hour_n': roll,
        'median_gap_min': round(float(np.median(gaps)) / 60, 1) if n > 1 else None,
        'share_gaps_under_60s': round(float((gaps < 60).mean()), 3) if n > 1 else None,
        'share_gaps_under_10s': round(float((gaps < 10).mean()), 3) if n > 1 else None,
        'same_second': int((gaps == 0).sum()),
        'longest_burst_n': int(best), 'longest_burst_min': round(best_span / 60, 1),
        'longest_burst_start': str(run.iloc[0]), 'longest_burst_end': str(run.iloc[-1]),
        'longest_burst_hourly': [[str(k), int(v)] for k, v in run_hours.items()],
        'runs_over_24h': runs_over_24h,
        'heavy_days': int(len(quiet)),
        'heavy_days_quiet_under_3h': int((quiet < 3).sum()) if len(quiet) else 0,
        'heavy_days_median_quiet_h': round(float(np.median(quiet)), 1) if len(quiet) else None,
        'share_1am_to_6am': round(float(hours[1:6].sum()), 3),
        'channels': ch, 'top_descriptors': desc, 'share_timestamps_on_the_minute': round(zero_sec, 3),
        'gap_seconds_most_common': [int(x) for x in pd.Series(gaps[gaps < 600]).round().value_counts().head(5).index],
    }


def window(path, lo, hi):
    # Timing inside one stretch of time at one address.
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    t = pd.to_datetime(d.created_date).sort_values()
    w = t[(t >= lo) & (t < hi)]
    g = np.diff(w.astype('int64').to_numpy() / 1e9)
    h = w.dt.floor('h').value_counts()
    med = float(np.median(g))
    return {'from': lo, 'to': hi, 'n': int(len(w)), 'median_gap_s': med,
            'share_within_1s_of_median': round(float((abs(g - med) <= 1).mean()), 3),
            'hourly_mean': round(float(h.mean()), 1), 'hourly_sd': round(float(h.std()), 2),
            'random_sd_at_that_rate': round(float(np.sqrt(h.mean())), 1)}


def interleave(paths, year):
    # How often consecutive complaints switch between addresses, and how fast.
    frames = []
    for p in paths:
        d = pd.read_csv(p, dtype=str, keep_default_na=False)
        frames.append(pd.DataFrame({'t': pd.to_datetime(d.created_date), 'a': os.path.basename(p)}))
    x = pd.concat(frames).sort_values('t')
    x = x[x.t.dt.year == year]
    sw = x.a.values[1:] != x.a.values[:-1]
    g = np.diff(x.t.astype('int64').to_numpy() / 1e9)
    return {'year': year, 'n': int(len(x)), 'switches': int(sw.sum()), 'switches_under_60s': int((sw & (g < 60)).sum()),
            'switches_under_10s': int((sw & (g < 10)).sum())}


def hours_share(paths):
    # Share of a group's complaints filed in each clock hour, 0 to 23.
    t = pd.concat([pd.to_datetime(pd.read_csv(p, dtype=str, keep_default_na=False).created_date) for p in paths])
    return [round(float(x), 4) for x in t.dt.hour.value_counts(normalize=True).reindex(range(24), fill_value=0)]


def main():
    rec = os.path.join(ROOT, 'build', 'cache', 'records')
    out = [analyze(p) for p in sorted(glob.glob(os.path.join(rec, '*.csv')))]
    out.sort(key=lambda r: -r['n'])
    bronx = os.path.join(rec, '655_EAST_230_STREET_10466.csv')
    wake = [os.path.join(rec, f) for f in ('655_EAST_230_STREET_10466.csv', '661_EAST_230_STREET_10466.csv',
                                           '672_EAST_231_STREET_10466.csv', '674_EAST_231_STREET_10466.csv')]
    queens = [os.path.join(rec, f) for f in ('78-15_PARSONS_BOULEVARD_11366.csv', '82-68_164_STREET_11432.csv',
                                             '159-06_UNION_TURNPIKE_11366.csv', '158-33_78_AVENUE_11366.csv',
                                             '71-01_PARSONS_BOULEVARD_11365.csv')]
    parking = [os.path.join(rec, f) for f in ('5-47_50_AVENUE_11101.csv', '191_UNION_STREET_11231.csv',
                                              '100_MESEROLE_AVENUE_11222.csv', '34-16_ASTORIA_BOULEVARD_SOUTH_11103.csv')]
    extra = {
        'bronx_plateau': window(bronx, '2025-01-05 12:00', '2025-01-06 02:00'),
        'bronx_overnight': window(bronx, '2025-01-07 00:00', '2025-01-07 07:00'),
        'bronx_interleave_2025': interleave(wake, 2025),
        'queens_interleave': [interleave(queens, y) for y in range(2020, 2027)],
        'parking_interleave': [interleave(parking, y) for y in range(2022, 2027)],
        'queens_hours': hours_share(queens), 'parking_hours': hours_share(parking),
    }
    json.dump({'addresses': out, 'windows': extra}, open(os.path.join(ROOT, 'data', 'cadence.json'), 'w'), indent=1)
    print(json.dumps(extra, indent=1))
    cols = ['address', 'n', 'busiest_year', 'busiest_year_per_active_day', 'peak_day', 'peak_day_n',
            'peak_rolling_hour_n', 'median_gap_min', 'share_gaps_under_60s', 'share_gaps_under_10s',
            'longest_burst_n', 'longest_burst_min', 'heavy_days', 'heavy_days_quiet_under_3h',
            'heavy_days_median_quiet_h', 'share_1am_to_6am']
    pd.set_option('display.width', 320)
    print(pd.DataFrame(out)[cols].to_string())
    for r in out:
        print(r['address'], r['channels'], r['top_descriptors'], 'on-minute', r['share_timestamps_on_the_minute'],
              'common gaps', r['gap_seconds_most_common'], 'same-second', r['same_second'])


if __name__ == '__main__':
    main()
