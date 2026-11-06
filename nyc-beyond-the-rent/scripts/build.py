#!/usr/bin/env python3
"""Assemble data/dashboard.json for Beyond the Rent from the raw official files.

Every derived number the page prints is computed here, so the methodology can
point at one place. Conventions:
- "t12" = trailing 12 months. For prices it is total revenue / total sales over
  the 12 months (a sales-weighted average), which removes seasonality.
- Changes are year over year: a month against the same month a year earlier,
  or a 12-month window against the 12 months before it.
- Average bills are pooled: total revenue over total customer-months, so the
  12-month bill and the utility ranking use the same definition.
- Headline values are stored at full precision (4 decimals) and rounded only
  when the page displays them; percentage changes use the unrounded values.
- Gas 12-month averages are weighted by residential sales volume, like the
  electricity ones, and annual gas figures are EIA's published annual prices.
"""
import json, math, pathlib, sys
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
OUT = ROOT / "data/dashboard.json"


def r(x, n=2):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), n)


def ser(s, n=2):
    """pandas Series indexed by Period/str -> {"YYYY-MM": v}."""
    return {str(k): r(v, n) for k, v in s.items() if v is not None and not pd.isna(v)}


# ---------------------------------------------------------------- electricity
e = pd.read_csv(RAW / "eia861m_res.csv")
e["m"] = pd.PeriodIndex.from_fields(year=e.year, month=e.month, freq="M")
CONED = 4226
OTHER_NY = {13573: "National Grid (Niagara Mohawk)", 13511: "NYSEG", 16183: "RG&E",
            3249: "Central Hudson", 14154: "Orange & Rockland", 11171: "LIPA (PSEG Long Island)"}


def agg(rows):
    g = rows.groupby("m")[["rev_k", "mwh", "cust"]].sum().sort_index()
    g = g[(g.mwh > 0)]
    full = pd.period_range(g.index.min(), g.index.max(), freq="M")
    g = g.reindex(full)
    out = pd.DataFrame(index=g.index)
    out["price"] = g.rev_k / g.mwh * 100                      # cents per kWh
    out["bill"] = g.rev_k * 1000 / g.cust                     # dollars per customer per month
    out["kwh"] = g.mwh * 1000 / g.cust                        # kWh per customer per month
    rr, ss, cc = g.rev_k.rolling(12).sum(), g.mwh.rolling(12).sum(), g.cust.rolling(12).sum()
    out["t12"] = rr / ss * 100
    out["t12bill"] = rr * 1000 / cc                           # total revenue / total customer-months
    return out


coned = agg(e[e.uid == CONED])
other = agg(e[e.uid.isin(OTHER_NY)])

# State and U.S. totals: EIA "sales_revenue.xlsx", Monthly-States sheet (all residential
# customers, full-service and delivery-only combined, as EIA publishes state prices).
sr = pd.read_excel(RAW / "sales_revenue.xlsx", sheet_name="Monthly-States", header=None, skiprows=3)
sr = sr.iloc[:, :7]
sr.columns = ["year", "month", "state", "status", "rev_k", "mwh", "cust"]
sr = sr[pd.to_numeric(sr.year, errors="coerce").notna()]
for c in ["year", "month", "rev_k", "mwh", "cust"]:
    sr[c] = pd.to_numeric(sr[c], errors="coerce")
sr = sr[sr.year >= 2009]
sr["m"] = pd.PeriodIndex.from_fields(year=sr.year.astype(int), month=sr.month.astype(int), freq="M")
nys = agg(sr[sr.state == "NY"])
us = agg(sr[sr.state != "PR"])
if coned.index.max() != nys.index.max():
    print("note: Con Ed latest", coned.index.max(), "state latest", nys.index.max())

LAST = coned.index.max()
yago = LAST - 12
P = 4  # stored precision for headline values; the page rounds for display
elec_latest = {
    "month": str(LAST),
    "nys_month": str(nys.index.max()), "us_month": str(us.index.max()),
    "coned_price": r(coned.price[LAST], P), "coned_price_yago": r(coned.price[yago], P),
    "coned_t12": r(coned.t12[LAST], P), "coned_t12_yago": r(coned.t12[yago], P),
    "coned_t12bill": r(coned.t12bill[LAST], P), "coned_t12bill_yago": r(coned.t12bill[yago], P),
    "coned_bill": r(coned.bill[LAST], P), "coned_bill_yago": r(coned.bill[yago], P),
    "other_t12": r(other.t12[LAST], P), "other_t12_yago": r(other.t12[yago], P),
    "nys_t12": r(nys.t12[LAST], P), "nys_t12_yago": r(nys.t12[yago], P),
    "us_t12": r(us.t12[LAST], P), "us_t12_yago": r(us.t12[yago], P),
    "coned_cust": int(e[(e.uid == CONED) & (e.m == LAST)].cust.iloc[0]),
}
for k, s in [("coned", coned), ("other", other), ("nys", nys), ("us", us)]:
    elec_latest[f"{k}_t12_yoy"] = r((s.t12[LAST] / s.t12[yago] - 1) * 100, P)
elec_latest["coned_t12bill_yoy"] = r((coned.t12bill[LAST] / coned.t12bill[yago] - 1) * 100, P)
elec_latest["coned_us_ratio"] = r(coned.t12[LAST] / us.t12[LAST], P)
# Long-run: t12 at the latest month vs the same 12-month window ten years earlier.
base = LAST - 120
elec_latest["decade"] = {k: {"from": r(s.t12[base], P), "to": r(s.t12[LAST], P), "pct": r((s.t12[LAST] / s.t12[base] - 1) * 100, P)}
                         for k, s in [("coned", coned), ("other", other), ("nys", nys), ("us", us)]}
elec_latest["decade_from"] = str(base)

# Large utilities nationwide, trailing 12 months to LAST, full-service residential.
win = e[(e.m > LAST - 12) & (e.m <= LAST)]
cnt = win.groupby("uid").m.nunique()
ok = cnt[cnt == 12].index
u = win[win.uid.isin(ok)].groupby(["uid", "state"]).agg(rev_k=("rev_k", "sum"), mwh=("mwh", "sum"), cust=("cust", "mean")).reset_index()
names = e.sort_values("m").groupby("uid").name.last()
u = u.groupby("uid").agg(rev_k=("rev_k", "sum"), mwh=("mwh", "sum"), cust=("cust", "sum"),
                         states=("state", lambda s: "/".join(sorted(set(s))))).reset_index()
u["name"] = u.uid.map(names)
u["price"] = u.rev_k / u.mwh * 100
u["bill"] = u.rev_k * 1000 / u.cust / 12
big = u[(u.cust >= 50000) & (~u.name.str.contains("Adjustment|State Total|Sunrun|Sunnova|Tesla", na=False))].sort_values("price", ascending=False)
EAST = set("ME NH VT MA RI CT NY NJ PA DE MD DC VA WV NC SC GA FL OH MI IN IL KY TN AL MS WI".split())
peers = [{"name": x.name, "states": x.states, "east": bool(set(x.states.split("/")) & EAST),
          "price": r(x.price, P), "bill": r(x.bill, P), "cust": int(x.cust)} for x in big.itertuples()]

# BLS average price per kWh, metro areas, 2024 annual average (BLS stopped most metro
# electricity prices after December 2024).
bls = json.load(open(RAW / "bls.json"))["series"]
METROS = {"APUS12A72610": "New York", "APUS11A72610": "Boston", "APUS12B72610": "Philadelphia",
          "APUS35A72610": "Washington", "APUS35E72610": "Baltimore", "APUS35B72610": "Miami",
          "APUS35C72610": "Atlanta", "APUS23A72610": "Chicago", "APUS23B72610": "Detroit",
          "APUS37A72610": "Dallas", "APUS49A72610": "Los Angeles", "APUS49B72610": "San Francisco",
          "APUS49D72610": "Seattle", "APUS24A72610": "St. Louis", "APUS48A72610": "Phoenix",
          "APUS35D72610": "Tampa", "APU000072610": "U.S. city average"}
EAST_METRO = {"New York", "Boston", "Philadelphia", "Washington", "Baltimore", "Miami", "Atlanta", "Tampa", "Detroit"}
metro = []
for sid, nm in METROS.items():
    v = [bls[sid].get(f"2024-{m:02d}") for m in range(1, 13)] if sid in bls else []
    v = [x for x in v if x is not None]
    if len(v) == 12:
        v10 = [bls[sid].get(f"2014-{m:02d}") for m in range(1, 13)]
        v10 = [x for x in v10 if x is not None]
        metro.append({"metro": nm, "sid": sid, "east": nm in EAST_METRO, "p2024": r(sum(v) / 12 * 100),
                      "p2014": r(sum(v10) / 12 * 100) if len(v10) == 12 else None})
metro.sort(key=lambda x: -x["p2024"])

# Wholesale: NYISO day-ahead zonal LBMP, monthly simple average.
ny = json.load(open(RAW / "nyiso_monthly.json"))
lbmp = pd.DataFrame(ny).T
lbmp.index = pd.PeriodIndex(lbmp.index, freq="M")
lbmp = lbmp.astype(float)


def eia_xls(f):
    x = pd.read_excel(RAW / f, sheet_name="Data 1", header=None, skiprows=3)
    x.columns = ["d", "v"]
    x = x.dropna()
    x["d"] = pd.to_datetime(x.d)
    return x


hh = eia_xls("RNGWHHDm.xls")
hh = pd.Series(hh.v.values, index=hh.d.dt.to_period("M"))

# Pass-through: correlate the year-over-year change in Con Ed's monthly price (cents)
# with the year-over-year change in the Zone J price (cents/kWh) k months earlier.
cp = coned.price
zj = lbmp.J / 10  # $/MWh -> cents/kWh
d_c = (cp - cp.shift(12)).dropna()
d_z = (zj - zj.shift(12)).dropna()
lag = []
for k in range(0, 7):
    j = pd.concat([d_c, d_z.shift(k)], axis=1, keys=["c", "z"]).dropna()
    j = j[j.index >= pd.Period("2011-01", "M")]
    slope = np.polyfit(j.z, j.c, 1)[0]
    rho = j.c.corr(j.z)
    lag.append({"lag": k, "r": r(rho, 3), "r2": r(rho ** 2, 3), "slope": r(slope, 3), "n": int(len(j))})
# Power follows gas: Zone J vs Henry Hub, same month.
jj = pd.concat([lbmp.J, hh], axis=1, keys=["j", "hh"]).dropna()
gas_power_r = r(jj.j.corr(jj.hh), 3)

# Seasonality: Con Ed price and use by calendar month, last three full calendar years.
yrs = [LAST.year - 3, LAST.year - 2, LAST.year - 1]
sea = coned[[p.year in yrs for p in coned.index]]
season = [{"m": m, "price": r(sea[[p.month == m for p in sea.index]].price.mean()),
           "kwh": r(sea[[p.month == m for p in sea.index]].kwh.mean(), 0),
           "bill": r(sea[[p.month == m for p in sea.index]].bill.mean(), 0)} for m in range(1, 13)]

elec = {
    "latest": elec_latest,
    "coned": {k: ser(coned[k], 2 if k != "kwh" else 0) for k in ["price", "bill", "kwh", "t12", "t12bill"]},
    "other": {k: ser(other[k]) for k in ["price", "t12", "t12bill"]},
    "nys": {k: ser(nys[k]) for k in ["price", "t12", "t12bill"]},
    "us": {k: ser(us[k]) for k in ["price", "t12", "t12bill"]},
    "peers": peers, "peers_window": f"{LAST - 11} to {LAST}",
    "metro": metro,
    "lbmp": {k: ser(lbmp[k]) for k in ["J", "K", "upstate"]},
    "lbmp_t12": {k: ser(lbmp[k].rolling(12).mean()) for k in ["J", "upstate"]},
    "henry_hub": ser(hh),
    "passthrough": lag, "gas_power_r": gas_power_r,
    "season": season, "season_years": yrs,
    # Two lines, not a bill breakdown: Con Ed's 12-month retail price and the 12-month simple
    # average of NYC-zone day-ahead energy prices, a wholesale benchmark. Their difference is
    # "retail price minus wholesale benchmark", not a measured delivery charge.
    "split": {"retail": ser(coned.t12), "energy": ser((lbmp.J / 10).rolling(12).mean())},
}
sp = pd.concat([coned.t12, (lbmp.J / 10).rolling(12).mean()], axis=1, keys=["c", "j"]).dropna()
elec["split_latest"] = {"month": str(sp.index[-1]), "retail": r(sp.c.iloc[-1], P), "energy": r(sp.j.iloc[-1], P),
                        "gap": r(sp.c.iloc[-1] - sp.j.iloc[-1], P),
                        "base_month": str(sp.index[-1] - 120), "retail_base": r(sp.c.iloc[-121], P), "energy_base": r(sp.j.iloc[-121], P),
                        "gap_base": r(sp.c.iloc[-121] - sp.j.iloc[-121], P)}

# ------------------------------------------------------------------ piped gas
def bls_s(sid):
    s = pd.Series(bls[sid])
    s.index = pd.PeriodIndex(s.index, freq="M")
    return s.sort_index()


def eia_m(f):
    x = eia_xls(f)
    return pd.Series(x.v.values, index=x.d.dt.to_period("M"))


g_ny, g_nj, g_us, g_cg = eia_m("N3010NY3m.xls"), eia_m("N3010NJ3m.xls"), eia_m("N3010US3m.xls"), eia_m("N3050NY3m.xls")
# Residential sales volumes (million cubic feet), used to weight 12-month averages. EIA reports
# 100% of New York residential deliveries as included in its price, so price and volume cover
# the same customers; for New Jersey and the U.S. the weights are total residential deliveries.
v_ny, v_nj, v_us = eia_m("N3010NY2m.xls"), eia_m("N3010NJ2m.xls"), eia_m("N3010US2m.xls")


def eia_a(f):
    x = eia_xls(f)
    return pd.Series(x.v.values, index=x.d.dt.year)


a_ny, a_nj, a_us = eia_a("N3010NY3a.xls"), eia_a("N3010NJ3a.xls"), eia_a("N3010US3a.xls")
GLAST = min(g_ny.index.max(), v_ny.index.max())


def t12w(price, vol, need=12):
    """Sales-weighted 12-month average: sum(price x volume) / sum(volume) over the 12 months
    ending each month, using months where both exist and requiring `need` of the 12. EIA
    withholds some monthly city-gate prices (March 2026, for one), so that line takes 11."""
    j = pd.concat([price, vol], axis=1, keys=["p", "v"]).dropna()
    j = j.reindex(pd.period_range(j.index.min(), j.index.max(), freq="M"))
    return (j.p * j.v).rolling(12, min_periods=need).sum() / j.v.rolling(12, min_periods=need).sum()


def t12(s):
    return s.rolling(12).mean()


w_ny, w_nj, w_us = t12w(g_ny, v_ny), t12w(g_nj, v_nj), t12w(g_us, v_us)
# Check against EIA's published annual prices (calendar years): the weighted December value
# should sit within a few percent of the annual figure (monthly prices are rounded to cents).
wcheck = {}
for y in range(2006, GLAST.year):
    dk = pd.Period(f"{y}-12", "M")
    if dk in w_ny.index and y in a_ny.index and not pd.isna(w_ny[dk]):
        wcheck[str(y)] = {"weighted": r(w_ny[dk], 3), "eia_annual": r(a_ny[y], 3), "diff_pct": r((w_ny[dk] / a_ny[y] - 1) * 100, 2)}
worst = max(abs(v["diff_pct"]) for v in wcheck.values())
if worst > 3:
    sys.exit(f"gas weighting check failed: weighted calendar-year NY price is {worst}% off EIA's annual figure")

# Three benchmark lines ($ per thousand cubic feet), each a 12-month average weighted by New York
# residential volumes so all three describe the same months. Henry Hub is quoted per million Btu;
# 1 Mcf of pipeline gas carries about 1.036 MMBtu (EIA heat content). These are benchmarks, not
# components of a bill: the differences between them are not tariff charges.
stack = pd.concat([t12w(hh * 1.036, v_ny), t12w(g_cg, v_ny, need=11), w_ny], axis=1, keys=["hh", "cg", "res"]).dropna()
stack = stack[stack.index >= pd.Period("2005-01", "M")]
gas = {
    "eia": {"ny": ser(g_ny), "nj": ser(g_nj), "us": ser(g_us), "citygate": ser(g_cg)},
    "eia_vol": {"ny": ser(v_ny, 0), "nj": ser(v_nj, 0), "us": ser(v_us, 0)},
    # From 2000: EIA withheld New York's August-December 1996 prices, which leaves holes in
    # the 12-month windows that follow; the page charts from 2005.
    "eia_t12": {k: ser(w_[w_.index >= pd.Period("2000-01", "M")], 3) for k, w_ in [("ny", w_ny), ("us", w_us), ("nj", w_nj)]},
    "eia_annual": {k: {str(y): r(v, 2) for y, v in s_.items()} for k, s_ in [("ny", a_ny), ("nj", a_nj), ("us", a_us)]},
    "weight_check": wcheck,
    "stack": {k: ser(stack[k], 3) for k in stack.columns},
    "bls_cpi": {k: ser(bls_s(s)) for k, s in [("nyc", "CUURS12ASEHF02"), ("ne", "CUUR0100SEHF02"), ("us", "CUUR0000SEHF02")]},
    "bls_therm": {k: ser(bls_s(s), 3) for k, s in [("nyc", "APUS12A72620"), ("ne", "APU010072620"), ("us", "APU000072620")]},
    "latest": {"month": str(GLAST), "ny": r(g_ny[GLAST], P), "ny_yago": r(g_ny[GLAST - 12], P),
               "ny_t12": r(w_ny[GLAST], P), "ny_t12_yago": r(w_ny[GLAST - 12], P),
               "us_t12": r(w_us[GLAST], P), "us_t12_yago": r(w_us[GLAST - 12], P),
               "hh_t12": r(stack.hh.iloc[-1], P), "cg_t12": r(stack.cg.iloc[-1], P), "res_t12": r(stack.res.iloc[-1], P),
               "stack_month": str(stack.index[-1]),
               "annual_year": int(a_ny.index.max()), "ny_annual": r(a_ny.iloc[-1], 2), "us_annual": r(a_us.iloc[-1], 2)},
    "season": [{"m": m, "ny": r(g_ny[[p.year in yrs and p.month == m for p in g_ny.index]].mean()),
                "us": r(g_us[[p.year in yrs and p.month == m for p in g_us.index]].mean())} for m in range(1, 13)],
}
gl = gas["latest"]
gl["ny_t12_yoy"] = r((w_ny[GLAST] / w_ny[GLAST - 12] - 1) * 100, P)
gl["us_t12_yoy"] = r((w_us[GLAST] / w_us[GLAST - 12] - 1) * 100, P)

# ---------------------------------------------------------------- heating oil
ho = pd.read_csv(RAW / "nyserda_heating_oil.csv", parse_dates=["date"]).sort_values("date")
REG = {"new_york_city_average_gal": "New York City", "long_island_average_gal": "Long Island",
       "lower_hudson_average_gal": "Lower Hudson", "upper_hudson_average_gal": "Upper Hudson",
       "capital_district_average": "Capital District", "central_new_york_average": "Central New York",
       "western_new_york_average": "Western New York", "north_country_average_gal": "North Country",
       "new_york_statewide_average": "Statewide"}
us_ho = eia_xls("W_EPD2F_PRS_NUS_DPGw.xls")
spot = eia_m("EER_EPD2F_PF4_Y35NY_DPGm.xls")
ho_m = ho.set_index("date")[list(REG)].resample("MS").mean()
ho_m.index = ho_m.index.to_period("M")
lastw = ho.iloc[-1]
target = lastw.date - pd.Timedelta(days=364)
prior = ho.iloc[(ho.date - target).abs().argsort().iloc[0]]
margin = (ho_m["new_york_city_average_gal"] - spot).dropna()
oil = {
    "weekly": {"dates": [d.strftime("%Y-%m-%d") for d in ho.date],
               **{k: [r(v) for v in ho[k]] for k in REG}},
    "regions": REG,
    "us_weekly": {"dates": [d.strftime("%Y-%m-%d") for d in us_ho.d], "v": [r(v, 3) for v in us_ho.v]},
    "spot": ser(spot, 3), "nyc_monthly": ser(ho_m["new_york_city_average_gal"], 3),
    "margin": ser(margin, 3),
    "latest": {"date": lastw.date.strftime("%Y-%m-%d"), "nyc": r(lastw.new_york_city_average_gal),
               "state": r(lastw.new_york_statewide_average),
               "yago_date": prior.date.strftime("%Y-%m-%d"), "nyc_yago": r(prior.new_york_city_average_gal),
               "state_yago": r(prior.new_york_statewide_average),
               "regions": {REG[k]: r(lastw[k]) for k in REG},
               "spot_month": str(spot.index.max()), "spot": r(spot.iloc[-1], 3),
               "margin_month": str(margin.index.max()), "margin": r(margin.iloc[-1], 2),
               "margin_t12": r(margin.iloc[-12:].mean(), 2), "margin_t12_yago": r(margin.iloc[-24:-12].mean(), 2), "margin_n": int(len(margin))},
}
ol = oil["latest"]
ol["nyc_yoy"] = r((ol["nyc"] / ol["nyc_yago"] - 1) * 100, 1)
ol["state_yoy"] = r((ol["state"] / ol["state_yago"] - 1) * 100, 1)
usl = us_ho.iloc[-1]
ol["us"] = r(usl.v, 2)
ol["us_date"] = usl.d.strftime("%Y-%m-%d")

# ------------------------------------------------------------------ overview CPI
cpi = {k: ser(bls_s(s), 3) for k, s in {
    "nyc_all": "CUURS12ASA0", "nyc_rent": "CUURS12ASEHA", "nyc_elec": "CUURS12ASEHF01", "nyc_gas": "CUURS12ASEHF02",
    "nyc_hhenergy": "CUURS12ASAH21", "nyc_energy": "CUURS12ASA0E",
    "ne_elec": "CUUR0100SEHF01", "ne_gas": "CUUR0100SEHF02", "ne_all": "CUUR0100SA0",
    "us_all": "CUUR0000SA0", "us_elec": "CUUR0000SEHF01", "us_gas": "CUUR0000SEHF02", "us_rent": "CUUR0000SEHA",
    "us_water": "CUUR0000SEHG01", "us_wst": "CUUR0000SEHG", "us_fueloil": "CUUR0000SEHE01"}.items()}

# ------------------------------------------------------------------ water (hand-collected)
water = {}
wf = ROOT / "research/water.json"
if wf.exists():
    water = json.load(open(wf))
coned_research = {}
cf = ROOT / "research/coned.json"
if cf.exists():
    coned_research = json.load(open(cf))

# Source versions: a fingerprint of every raw file this build read, so a later build can tell a
# revision at the source (file changed, same months) from a mistake here. Written beside the
# dashboard and kept in git; scripts/check.py also logs revised historical values.
import hashlib
srcs = {}
for f in sorted(list(RAW.glob("*.xls")) + list(RAW.glob("*.xlsx")) + list(RAW.glob("*.csv")) + list(RAW.glob("*.json"))
                + list((RAW / "eia861m").glob("*"))):
    if f.is_file():
        srcs[str(f.relative_to(RAW))] = {"bytes": f.stat().st_size, "sha256": hashlib.sha256(f.read_bytes()).hexdigest()[:16]}
(ROOT / "data/sources.json").write_text(json.dumps({"built": pd.Timestamp.now().strftime("%Y-%m-%d"), "files": srcs}, indent=1))

out = {"built": pd.Timestamp.now().strftime("%Y-%m-%d"), "elec": elec, "gas": gas, "oil": oil, "cpi": cpi,
       "water": water, "coned_research": coned_research,
       "bls_fetched": json.load(open(RAW / "bls.json"))["fetched"]}
OUT.write_text(json.dumps(out, separators=(",", ":")))
print("wrote", OUT, round(OUT.stat().st_size / 1024), "KB")
print(json.dumps(elec_latest, indent=1))
print("passthrough", lag, "gas-power r", gas_power_r)
print(json.dumps(gas["latest"], indent=1)); print(json.dumps(oil["latest"], indent=1)); print("gas weight check", wcheck)
print("split", elec["split_latest"]); print("peers", len(peers))
print("metro:"); [print(m) for m in metro]
print("season:", season)
