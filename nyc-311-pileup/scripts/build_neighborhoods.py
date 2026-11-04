"""Neighborhood measures for "Where 311 complaints pile up".

Places every ranked street address (the same set build_data.py ranks) in a
2020 Neighborhood Tabulation Area by its geocoded point, then measures how
311 volume is spread across neighborhoods and how much of each
neighborhood's volume comes from a handful of addresses.

Inputs:
  build/cache/types/*.csv, build/cache/coords/*.csv   (fetch_311.py)
  ../nyc-nta-rankings/data/raw/nta2020.geojson        (NYC Planning, 2020 NTAs)
  ../nyc-nta-rankings/data/acs.json                   (ACS 2020-2024 population by NTA)
Writes:
  data/neighborhoods.json
  data/neighborhoods.csv
  build/neighborhood-checks.json

Usage: python3 scripts/build_neighborhoods.py
"""
import datetime, json, os, sys
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import shape
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_data import ADDR_RE, CATS, TYPE_MIN, category, load_coords, load_types  # noqa: E402

ROOT = os.path.join(HERE, '..')
NTA_DIR = os.path.join(ROOT, '..', 'nyc-nta-rankings', 'data')
DATA = os.path.join(ROOT, 'data')
MIN_POP = 5000        # neighborhoods smaller than this get no per-resident rate
HEAVY_SHARE = 0.001   # "busiest addresses" = the citywide top 0.1%
TIERS = (130, 1301, 13011)  # top 0.01%, 0.1% and 1% of the 1,301,096 ranked addresses


def gini(x, w=None):
    """Gini coefficient of values x, optionally weighted (e.g. by population)."""
    x = np.asarray(x, float)
    w = np.ones_like(x) if w is None else np.asarray(w, float)
    o = np.argsort(x)
    x, w = x[o], w[o]
    cw = np.cumsum(w) / w.sum()
    cx = np.cumsum(x * w) / (x * w).sum()
    # Area under the Lorenz curve by trapezoids.
    cw0 = np.concatenate([[0], cw])
    cx0 = np.concatenate([[0], cx])
    return float(1 - np.sum((cw0[1:] - cw0[:-1]) * (cx0[1:] + cx0[:-1])))


def main():
    meta = json.load(open(os.path.join(ROOT, 'build', 'cache', 'meta.json')))[0]
    d = load_types()
    TOT = int(d.n.sum())
    placed = d.addr.str.match(ADDR_RE)
    da = d[placed].copy()
    da['cat'] = da.tkey.map(category)
    at = da.groupby(['addr', 'zip']).n.sum().reset_index()
    at = at.sort_values(['n', 'addr', 'zip'], ascending=[False, True, True]).reset_index(drop=True)
    at['rank'] = np.arange(1, len(at) + 1)
    N = len(at)
    heavy_k = int(round(N * HEAVY_SHARE))
    at['heavy'] = at['rank'] <= heavy_k
    catn = da.groupby(['addr', 'zip', 'cat']).n.sum().unstack(fill_value=0)
    at = at.join(catn, on=['addr', 'zip'])

    coords = load_coords()
    at = at.join(coords[['lat', 'lon']], on=['addr', 'zip'])
    has_xy = at.lat.notna()

    # Point in polygon.
    gj = json.load(open(os.path.join(NTA_DIR, 'raw', 'nta2020.geojson')))
    geoms, props = [], []
    for f in gj['features']:
        geoms.append(shape(f['geometry']))
        props.append(f['properties'])
    tree = STRtree(geoms)
    xy = at[has_xy]
    pts = shapely.points(xy.lon.to_numpy(), xy.lat.to_numpy())
    pi, gi = tree.query(pts, predicate='within')
    code = np.full(len(xy), None, dtype=object)
    code[pi] = [props[g]['nta2020'] for g in gi]
    at.loc[has_xy, 'nta'] = code
    in_nta = at.nta.notna()

    # Complaint types big enough to show on their own, counted by neighborhood.
    lab = (d.groupby(['tkey', 'complaint_type']).n.sum().reset_index()
           .sort_values('n').drop_duplicates('tkey', keep='last').set_index('tkey').complaint_type)
    da = da.merge(at[['addr', 'zip', 'nta']], on=['addr', 'zip'])
    da = da[da.nta.notna()]
    ttot = da.groupby('tkey').n.sum().sort_values(ascending=False)
    big = [t for t, v in ttot.items() if v >= TYPE_MIN]
    # Busiest single address in each neighborhood for each category and type, so the
    # page can say when one building drives a neighborhood's number.
    def busiest(key, keys):
        g = da[da[key].isin(keys)].groupby(['nta', key, 'addr']).n.sum().reset_index()
        g = g.sort_values('n').drop_duplicates(['nta', key], keep='last')
        return {(r.nta, r[key]): (r.addr, int(r.n)) for _, r in g.iterrows()}
    busy_cat = busiest('cat', [k for k, _ in CATS])
    busy_type = None  # filled after big is known
    by_type = da[da.tkey.isin(big)].groupby(['nta', 'tkey']).n.sum().unstack(fill_value=0).reindex(columns=big, fill_value=0)
    busy_type = busiest('tkey', big)

    # Complaints at the citywide busiest addresses (ranked on all complaints, as on the
    # rest of the page), by neighborhood, for each slice: all, each category, each type.
    da = da.merge(at[['addr', 'zip', 'rank']], on=['addr', 'zip'])
    tiers = {}
    for k in TIERS:
        x = da[da['rank'] <= k]
        tiers[k] = {'all': x.groupby('nta').n.sum(),
                    'cat': x.groupby(['nta', 'cat']).n.sum(),
                    'type': x[x.tkey.isin(big)].groupby(['nta', 'tkey']).n.sum(),
                    'addr': x.groupby('nta')[['addr', 'zip']].apply(lambda g: len(g.drop_duplicates()))}

    def tier_vec(code, k):
        t = tiers[k]
        v = [int(t['all'].get(code, 0)), int(t['addr'].get(code, 0))]
        v += [int(t['cat'].get((code, c), 0)) for c, _ in CATS]
        v += [int(t['type'].get((code, ty), 0)) for ty in big]
        return v
    addr_ix = {}

    def aix(a):
        return addr_ix.setdefault(a, len(addr_ix))

    acs = json.load(open(os.path.join(NTA_DIR, 'acs.json')))
    start = datetime.date(2020, 1, 1)
    end = datetime.date.fromisoformat(meta['newest'][:10])
    years = ((end - start).days + 1) / 365.25

    rows = []
    for p in props:
        c = p['nta2020']
        g = at[at.nta == c].sort_values('n', ascending=False)
        n = int(g.n.sum())
        pop = (acs.get(c, {}).get('population') or {}).get('v')
        pop = int(pop) if pop else 0
        inc = (acs.get(c, {}).get('median_hh_income') or {}).get('v')
        top1 = g.head(1)
        rows.append({
            'code': c, 'name': p['ntaname'], 'boro': p['boroname'], 'type': int(p['ntatype']),
            'pop': pop, 'income': inc,
            'n': n, 'addresses': int(len(g)),
            'heavy_n': int(g[g.heavy].n.sum()), 'heavy_addresses': int(g.heavy.sum()),
            'top1_n': int(top1.n.sum()), 'top1_addr': top1.addr.iloc[0] if len(top1) else '',
            'top10_n': int(g.head(10).n.sum()),
            'addr_for_half': int(np.searchsorted(g.n.cumsum().to_numpy(), n / 2) + 1) if n else 0,
            'gini': gini(g.n.to_numpy()) if len(g) > 1 else None,
            **{f'cat_{k}': int(g[k].sum()) for k, _ in CATS},
        })
    nb = pd.DataFrame(rows)
    nb['rated'] = (nb.type == 0) & (nb['pop'] >= MIN_POP)
    nb['rate'] = np.where(nb.rated, nb.n / nb['pop'].clip(lower=1) / years * 1000, np.nan)
    nb['rate_light'] = np.where(nb.rated, (nb.n - nb.heavy_n) / nb['pop'].clip(lower=1) / years * 1000, np.nan)
    nb['top1_share'] = nb.top1_n / nb.n.clip(lower=1)
    nb['top10_share'] = nb.top10_n / nb.n.clip(lower=1)
    nb['heavy_share'] = nb.heavy_n / nb.n.clip(lower=1)
    r = nb[nb.rated].copy()
    r['rank'] = r.rate.rank(ascending=False, method='min').astype(int)
    r['rank_light'] = r.rate_light.rank(ascending=False, method='min').astype(int)
    nb = nb.join(r[['rank', 'rank_light']])

    # Citywide skew across neighborhoods, residents as the unit.
    def resident_shares(col):
        s = r.sort_values(col, ascending=False)
        cp = s['pop'].cumsum() / s['pop'].sum()
        cn = (s.n if col == 'rate' else s.n - s.heavy_n).cumsum()
        cn = cn / cn.iloc[-1]
        out = {}
        for q in (0.1, 0.2, 0.5):
            i = int(np.searchsorted(cp.to_numpy(), q))
            out[str(q)] = {'pop_share': float(cp.iloc[i]), 'n_share': float(cn.iloc[i]), 'ntas': i + 1}
        # Lorenz points for the chart: residents (x) vs complaints (y), busiest-rate first.
        out['curve'] = [[round(float(a), 4), round(float(b), 4)] for a, b in
                        zip(np.concatenate([[0], cp]), np.concatenate([[0], cn]))]
        return out

    rate_q = r.rate.quantile([0.1, 0.5, 0.9])
    light_q = r.rate_light.quantile([0.1, 0.5, 0.9])
    corr_inc = r.dropna(subset=['income'])
    checks = {
        'total': TOT, 'addresses': N, 'placed_n': int(at.n.sum()),
        'with_coords_n': int(at[has_xy].n.sum()), 'in_nta_n': int(at[in_nta].n.sum()),
        'in_nta_addresses': int(in_nta.sum()),
        'outside_nta_addresses': int((has_xy & ~in_nta).sum()),
        'outside_nta_n': int(at[has_xy & ~in_nta].n.sum()),
        'no_coords_n': int(at[~has_xy].n.sum()),
        'years': years, 'period_end': str(end),
        'ntas': len(nb), 'rated_ntas': int(nb.rated.sum()),
        'rated_pop': int(r['pop'].sum()), 'rated_n': int(r.n.sum()),
        'unrated_n': int(nb[~nb.rated].n.sum()),
        'heavy_k': heavy_k, 'heavy_min': int(at.loc[heavy_k - 1, 'n']),
        'city_rate': float(r.n.sum() / r['pop'].sum() / years * 1000),
        'rate_p10': float(rate_q[0.1]), 'rate_p50': float(rate_q[0.5]), 'rate_p90': float(rate_q[0.9]),
        'light_p10': float(light_q[0.1]), 'light_p50': float(light_q[0.5]), 'light_p90': float(light_q[0.9]),
        'gini_resident': gini(r.rate, r['pop']), 'gini_resident_light': gini(r.rate_light, r['pop']),
        'shares': resident_shares('rate'), 'shares_light': resident_shares('rate_light'),
        'median_top1_share': float(r.top1_share.median()),
        'median_top10_share': float(r.top10_share.median()),
        'ntas_top1_over_25': int((r.top1_share >= 0.25).sum()),
        'ntas_top10_over_50': int((r.top10_share >= 0.5).sum()),
        'median_gini_within': float(r.gini.median()),
        'spearman_rate_light': float(r.rate.rank().corr(r.rate_light.rank())),
        'rank_moves_10plus': int((abs(r['rank'] - r.rank_light) >= 10).sum()),
        'spearman_income': float(corr_inc.rate.rank().corr(corr_inc.income.rank())),
        'spearman_income_light': float(corr_inc.rate_light.rank().corr(corr_inc.income.rank())),
    }
    checks['top_rate'] = r.sort_values('rate', ascending=False).head(10)[
        ['name', 'boro', 'rate', 'rate_light', 'top1_share', 'top1_addr', 'rank_light']].to_dict('records')
    checks['top_light'] = r.sort_values('rate_light', ascending=False).head(10)[
        ['name', 'boro', 'rate', 'rate_light', 'rank']].to_dict('records')
    checks['bottom_rate'] = r.sort_values('rate').head(5)[['name', 'boro', 'rate']].to_dict('records')
    checks['top1_heaviest'] = r.sort_values('top1_share', ascending=False).head(10)[
        ['name', 'boro', 'top1_share', 'top1_addr', 'top1_n', 'n']].to_dict('records')
    checks['biggest_fallers'] = r.assign(move=r.rank_light - r['rank']).sort_values('move', ascending=False).head(8)[
        ['name', 'boro', 'rank', 'rank_light', 'heavy_share']].to_dict('records')

    with open(os.path.join(ROOT, 'build', 'neighborhood-checks.json'), 'w') as f:
        json.dump(checks, f, indent=1, default=float)

    # Page data: one row per neighborhood, arrays kept short.
    keep = nb.sort_values(['boro', 'name'])
    page = {
        'cats': [k for k, _ in CATS], 'years': years, 'end': str(end), 'min_pop': MIN_POP,
        'heavy_k': heavy_k, 'heavy_min': checks['heavy_min'],
        'city_rate': checks['city_rate'],
        'curve': checks['shares']['curve'], 'curve_light': checks['shares_light']['curve'],
        'rows': [[x.code, x.name, x.boro[0] if x.boro != 'Staten Island' else 'S', int(x.type), int(x.pop),
                  int(x.n), int(x.addresses), int(x.heavy_n), int(x.heavy_addresses),
                  int(x.top1_n), x.top1_addr, int(x.top10_n), int(x.addr_for_half),
                  round(x.gini, 3) if x.gini is not None and np.isfinite(x.gini) else None,
                  [int(getattr(x, f'cat_{k}')) for k, _ in CATS],
                  int(x.income) if x.income and np.isfinite(x.income) else None,
                  [int(v) for v in (by_type.loc[x.code] if x.code in by_type.index else [0] * len(big))],
                  [v for k, _ in CATS for v in ((aix(busy_cat[(x.code, k)][0]), busy_cat[(x.code, k)][1])
                                                 if (x.code, k) in busy_cat else (-1, 0))],
                  [v for t in big for v in ((aix(busy_type[(x.code, t)][0]), busy_type[(x.code, t)][1])
                                            if (x.code, t) in busy_type else (-1, 0))],
                  [tier_vec(x.code, k) for k in TIERS]]
                 for x in keep.itertuples()],
        'fields': ['code', 'name', 'boro', 'type', 'pop', 'n', 'addresses', 'heavy_n', 'heavy_addresses',
                   'top1_n', 'top1_addr', 'top10_n', 'addr_for_half', 'gini', 'cats', 'income', 'types', 'busy_cats', 'busy_types', 'tiers'],
        'tiers': list(TIERS),
        'types': [{'label': lab[t], 'cat': category(t)} for t in big],
    }
    page['addrs'] = list(addr_ix)
    with open(os.path.join(DATA, 'neighborhoods.json'), 'w') as f:
        json.dump(page, f, separators=(',', ':'))
    out = keep[['code', 'name', 'boro', 'pop', 'n', 'addresses', 'rate', 'rank', 'heavy_addresses', 'heavy_n',
                'rate_light', 'rank_light', 'top1_addr', 'top1_n', 'top1_share', 'top10_share', 'addr_for_half',
                'gini']].rename(columns={
        'code': 'nta2020', 'name': 'neighborhood', 'boro': 'borough', 'pop': 'residents_acs_2020_24',
        'n': 'complaints', 'addresses': 'addresses_with_complaints',
        'rate': 'complaints_per_1000_residents_per_year', 'rank': 'rank_per_resident',
        'heavy_addresses': 'citywide_top_0_1pct_addresses', 'heavy_n': 'complaints_at_those_addresses',
        'rate_light': 'rate_without_those_addresses', 'rank_light': 'rank_without_those_addresses',
        'top1_addr': 'busiest_address', 'top1_n': 'busiest_address_complaints',
        'top1_share': 'busiest_address_share', 'top10_share': 'top_10_addresses_share',
        'addr_for_half': 'addresses_for_half_of_complaints', 'gini': 'gini_across_addresses'})
    out.round(4).to_csv(os.path.join(DATA, 'neighborhoods.csv'), index=False)
    print(json.dumps({k: v for k, v in checks.items() if not isinstance(v, (list, dict))}, indent=1, default=float))
    for k in ('top_rate', 'top_light', 'bottom_rate', 'top1_heaviest', 'biggest_fallers'):
        print(k)
        for row in checks[k]:
            print('  ', row)
    for k in ('shares', 'shares_light'):
        print(k, {q: v for q, v in checks[k].items() if q != 'curve'})


if __name__ == '__main__':
    main()
