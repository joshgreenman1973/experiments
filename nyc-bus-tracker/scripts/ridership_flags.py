#!/usr/bin/env python3
"""Flag route-months whose MTA ridership estimate moved out of line with fare taps.

The MTA's stop ridership estimates (fvdm-uavx) are scaled up from passenger
counters that only some buses carry. When counter coverage or the scaling on a
route changes, the estimate can jump while paid fare taps barely move. In
September 2026 BX15 went from 7,870 to 24,984 estimated weekday boardings while
its taps held near 3,600; earlier in 2026 several Bronx routes showed fewer
estimated boardings than paid taps. Neither is a change in riders.

Rule: for each route and month with both an estimate and taps, compare the
estimate-to-taps ratio with the median of the same route's ratios over the
twelve months before (at least six of them present). A month is flagged when
the ratio is more than FLAG_JUMP above or below that median. Flagged months are
listed per route in "flags"; pages keep flagged routes out of rankings and
change figures. The same test on the whole system, at SYSTEM_JUMP, fills
"systemFlags" so pages can say when the system total moved for the same reason.

Run by fetch_route_ridership.py before it writes the file, or standalone:
    python3 scripts/ridership_flags.py [path/to/routes-monthly.json]
"""
import json
import os
import statistics
import sys

FLAG_JUMP = 0.40
SYSTEM_JUMP = 0.08
MIN_BASE = 6

DEFINITION = (
    'Months in which the estimate-to-taps ratio moved more than '
    f'{round(FLAG_JUMP * 100)}% above or below the median of the route\'s own ratio over the '
    f'twelve months before (at least {MIN_BASE} of them present). These are months where the '
    'estimate changed far out of line with paid entries, most likely because counter '
    'coverage or the MTA\'s scaling changed on that route. Pages leave a route out of '
    'rankings and change figures while its latest month, or any month in the comparison '
    'window, is flagged. systemFlags applies the same test to the whole system at '
    f'{round(SYSTEM_JUMP * 100)}%.'
)


def flagged_months(months, est, taps, jump):
    ratios = [e / t if e and t else None for e, t in zip(est, taps)]
    out = []
    for i, r in enumerate(ratios):
        if r is None:
            continue
        base = [x for x in ratios[max(0, i - 12):i] if x is not None]
        if len(base) < MIN_BASE:
            continue
        med = statistics.median(base)
        if med and abs(r / med - 1) > jump:
            out.append(months[i])
    return out


def add_flags(data):
    months = data['months']
    n = 0
    for rec in data['routes'].values():
        f = flagged_months(months, rec.get('wdAvg') or [], rec.get('tapsWdAvg') or [], FLAG_JUMP)
        if f:
            rec['flags'] = f
            n += 1
        else:
            rec.pop('flags', None)
    s = data['system']
    data['systemFlags'] = flagged_months(months, s.get('wdAvg') or [], s.get('tapsWdAvg') or [], SYSTEM_JUMP)
    data.setdefault('definitions', {})['flags'] = DEFINITION
    latest = months[-1]
    in_latest = sorted(k for k, r in data['routes'].items() if latest in r.get('flags', []))
    print(f'  ridership flags: {n} routes have a flagged month; {len(in_latest)} in {latest}'
          + (f' ({", ".join(in_latest[:12])}{"…" if len(in_latest) > 12 else ""})' if in_latest else '')
          + (f'; system flagged in {", ".join(data["systemFlags"])}' if data['systemFlags'] else ''),
          flush=True)
    return data


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, '..', 'data', 'ridership', 'routes-monthly.json')
    with open(path) as fh:
        d = json.load(fh)
    add_flags(d)
    with open(path, 'w') as fh:
        json.dump(d, fh, separators=(',', ':'))
