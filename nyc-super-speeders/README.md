# NYC Super Speeders

A live, plate-level accountability dashboard for NYC's school-zone speed-camera data — and a companion to the [NYC Traffic Collisions deep dive](https://joshgreenman1973.github.io/experiments/nyc-collisions/).

**Live**: https://joshgreenman1973.github.io/experiments/nyc-super-speeders/

Sections: a why-speed-kills primer, a live Wall of Shame (top 50 plates by FY2026 camera-ticket count), escalation curves vs. the DVAP 15-ticket threshold, a plate lookup with shareable permalinks (`?plate=X&state=Y`), a school-zone density map, a borough-level cross-reference against pedestrian + cyclist casualties, an interactive DVAP-eligibility simulator, and temporal patterns.

All reads are live from NYC Open Data (`pvqr-7yc4`, `h9gi-nx95`) via the Socrata API — scoped to NYC Fiscal Year 2026 (Jul 1, 2025 – Jun 30, 2026). No backend. See [METHODOLOGY.md](./METHODOLOGY.md).
