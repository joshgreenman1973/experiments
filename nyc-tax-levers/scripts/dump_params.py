import json, sys, math
from policyengine_us import CountryTaxBenefitSystem
from policyengine_core.parameters import ParameterNode, Parameter, ParameterScale
tbs = CountryTaxBenefitSystem()
I = "2026-01-01"
def ser(n, I=I):
    if isinstance(n, ParameterScale):
        b = n.brackets
        out = {"_scale": True, "thresholds": [float(x.threshold(I)) if x.threshold(I) is not None else None for x in b]}
        a = b[0]
        if "rate" in a.children: out["rates"] = [x.rate(I) for x in b]
        if "amount" in a.children: out["amounts"] = [x.amount(I) for x in b]
        out["thresholds"] = [("inf" if (t is not None and math.isinf(t)) else t) for t in out["thresholds"]]
        return out
    if isinstance(n, Parameter):
        v = n(I)
        if isinstance(v, float) and math.isinf(v): return "inf"
        return v if not hasattr(v, "tolist") else v.tolist()
    if isinstance(n, ParameterNode):
        return {k: ser(c, I) for k, c in n.children.items()}
    return str(n)
p = tbs.parameters
roots = {"ny": p.gov.states.ny.tax.income, "nyc": p.gov.local.ny.nyc.tax.income, "mamdani": p.gov.local.ny.mamdani_income_tax,
         "eitc": p.gov.irs.credits.eitc}
out = {k: ser(v) for k, v in roots.items()}
# Federal income tax before credits (2026), used only for the old Empire State
# Child Credit formula, which matches 33% of the federal child credit computed
# with the federal credit's 2017 (pre-TCJA) parameters.
out["fed"] = {"bracket": ser(p.gov.irs.income.bracket), "standard": ser(p.gov.irs.deductions.standard.amount)}
out["ctc2017"] = ser(p.gov.irs.credits.ctc, "2017-01-01")
json.dump(out, open(sys.argv[1], "w"), indent=1, default=str)
