#!/usr/bin/env python3
"""Health audit for every project in projects-manifest.json.

Checks two things that fail silently:
  A. Live GitHub Pages URLs that 404 or serve an empty page.
  B. Cron-scheduled GitHub Actions that are disabled or last failed.

Section B queries the GitHub API, NOT the local git log -- a local clone
being behind says nothing about whether the cron is running.

Usage:  python3 scripts/health-audit.py
"""
import json, os, subprocess, glob, re, datetime, concurrent.futures as cf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
projs = json.load(open(os.path.join(ROOT, "projects-manifest.json")))["projects"]
now = datetime.datetime.now(datetime.timezone.utc)

def lp_of(p):
    lp = p.get("localPath") or (os.path.join(ROOT, p["relPath"]) if p.get("relPath") else None)
    return lp if lp and os.path.isdir(lp) else None

def crons(p):
    lp = lp_of(p)
    if not lp: return []
    out = []
    for f in glob.glob(os.path.join(lp, ".github/workflows/*.y*ml")):
        try: t = open(f, errors="ignore").read()
        except Exception: continue
        if re.search(r"^\s*schedule:", t, re.M):
            out += re.findall(r"cron:\s*['\"]([^'\"]+)", t)
    return out

def nwo(p):
    lp = lp_of(p)
    if not lp: return None
    try:
        u = subprocess.run(["git","-C",lp,"remote","get-url","origin"],
                           capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception: return None
    return re.sub(r"\.git$", "", re.sub(r".*github\.com[:/]", "", u)) or None

def http(url):
    try:
        r = subprocess.run(["curl","-sS","-o","/dev/null","-w","%{http_code} %{size_download}",
                            "-L","--max-time","20",url], capture_output=True, text=True, timeout=30)
        return r.stdout.strip()
    except Exception:
        return "ERR 0"

def gh_json(args):
    try:
        r = subprocess.run(["gh"]+args, capture_output=True, text=True, timeout=60)
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
    except Exception:
        return None

live = [p for p in projs if p.get("livePagesUrl")]
cronp = [p for p in projs if crons(p)]

print(f"projects={len(projs)}  live_urls={len(live)}  cron_projects={len(cronp)}\n")

print("=== A. LIVE URL BROKEN ===")
bad = 0
with cf.ThreadPoolExecutor(20) as ex:
    for p, res in zip(live, ex.map(lambda p: http(p["livePagesUrl"]), live)):
        code, _, size = res.partition(" ")
        size = int(size or 0)
        # A Vite/SPA shell is legitimately tiny; only flag non-200 or truly empty.
        if code != "200" or size < 200:
            bad += 1
            print(f"  {code:>4} {size:>7}b  {p['name']}  {p['livePagesUrl']}")
print("  (none)" if not bad else "")

print("\n=== B. CRON DISABLED OR LAST RUN FAILED ===")
prob = 0
for p in cronp:
    repo = nwo(p)
    if not repo:
        print(f"  ?      no git remote          {p['name']}"); prob += 1; continue
    wfs = gh_json(["api", f"repos/{repo}/actions/workflows"])
    if not wfs:
        print(f"  ?      could not query        {p['name']} ({repo})"); prob += 1; continue
    for w in wfs.get("workflows", []):
        if w["name"] == "pages-build-deployment":
            continue
        if w["state"] != "active":
            print(f"  DISABLED  {w['state']:<20} {p['name']} / {w['name']}"); prob += 1
            continue
        runs = gh_json(["api", f"repos/{repo}/actions/workflows/{w['id']}/runs?per_page=1"])
        r = (runs or {}).get("workflow_runs") or []
        if not r:
            continue
        r = r[0]
        age = (now - datetime.datetime.fromisoformat(r["created_at"].replace("Z","+00:00"))).days
        if r["conclusion"] not in ("success", None) or age > 7:
            print(f"  {r['conclusion'] or r['status']:<9} {age:>3}d ago  {p['name']} / {w['name']}")
            prob += 1
print("  (none)" if not prob else "")
