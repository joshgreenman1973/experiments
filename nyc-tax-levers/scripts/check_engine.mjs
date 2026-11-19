// Compare engine.js with PolicyEngine results written by check_engine.py.
// Usage: node check_engine.mjs CASES.json   (exits 1 on any mismatch over $1)
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { compute } = require("../engine.js");

const base = JSON.parse(readFileSync(new URL("../params-2026.json", import.meta.url)));
const cases = JSON.parse(readFileSync(process.argv[2]));

// Apply a PolicyEngine-style reform dict to a copy of the parameters.
function applyReform(P, reform) {
  const Q = structuredClone(P);
  for (const [path, value] of Object.entries(reform || {})) {
    let parts = path.split(".");
    const rootMap = { "gov.states.ny.tax.income": (Q) => Q.ny, "gov.local.ny.nyc.tax.income": (Q) => Q.nyc,
      "gov.local.ny.mamdani_income_tax": (Q) => Q.mamdani, "gov.contrib.states.ny": (Q) => Q.contrib.ny,
      "gov.contrib.local.nyc": (Q) => Q.contrib.nyc };
    let node = null, rest = null;
    for (const [pre, get] of Object.entries(rootMap)) {
      if (path.startsWith(pre + ".")) { node = get(Q); rest = path.slice(pre.length + 1); }
    }
    if (!node) throw new Error("unmapped " + path);
    parts = rest.split(".");
    for (let i = 0; i < parts.length; i++) {
      const p = parts[i], last = i === parts.length - 1;
      const m = p.match(/^(\w+)\[(\d+)\]$/);
      if (m) {
        const scale = node[m[1]], idx = +m[2], field = parts[i + 1];
        const arr = field === "threshold" ? scale.thresholds : field === "rate" ? scale.rates : scale.amounts;
        arr[idx] = value;
        break;
      }
      if (last) node[p] = value; else node = node[p];
    }
  }
  return Q;
}

const MAP = {
  eitc: (r) => r.fedEitc, ny_taxable_income: (r) => r.ny.taxable, ny_main_income_tax: (r) => r.ny.main,
  ny_supplemental_tax: (r) => r.ny.supplemental, ny_household_credit: (r) => r.ny.householdCredit,
  ny_eitc: (r) => r.ny.eitc, ny_ctc: (r) => r.ny.escc, ny_income_tax: (r) => r.ny.tax,
  nyc_income_tax_before_credits: (r) => r.nyc.beforeCredits, nyc_household_credit: (r) => r.nyc.householdCredit,
  nyc_eitc: (r) => r.nyc.eitc, nyc_school_tax_credit: (r) => r.nyc.school,
  nyc_income_tax_elimination_credit: (r) => r.nyc.elimination, nyc_income_tax: (r) => r.nyc.tax,
};

let bad = 0, checked = 0, worst = 0;
for (const [name, reform] of Object.entries(cases.reforms)) {
  const P = applyReform(base, reform);
  const res = cases.results[name];
  cases.households.forEach((h, i) => {
    const r = compute(h, P);
    for (const [v, f] of Object.entries(MAP)) {
      const want = res[v][i], got = f(r), d = Math.abs(want - got);
      // PolicyEngine computes in 32-bit floats (about 7 significant digits), so
      // allow $1 or one part in a million of the household's wages, whichever is larger.
      const tol = Math.max(1, 1e-6 * h.wages);
      checked++; worst = Math.max(worst, d);
      if (d > tol) {
        if (bad < 25) console.log(`${name} #${i} ${JSON.stringify(h)} ${v}: PolicyEngine ${want} vs engine ${got.toFixed(2)}`);
        bad++;
      }
    }
  });
}
console.log(`${checked} values checked across ${Object.keys(cases.reforms).length} scenarios and ${cases.households.length} households; ${bad} outside tolerance; largest gap $${worst.toFixed(2)}`);
process.exit(bad ? 1 : 0);
