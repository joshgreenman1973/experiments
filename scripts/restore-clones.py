#!/usr/bin/env python3
"""Restore every nested project repo onto a fresh machine.

The Experiments monorepo tracks ~77 projects directly; the other ~120 live
as independent git repos nested inside ~/Experiments. This script reads
machine/repos.json — a committed inventory of every nested repo and its
remote, kept current by scripts/sync-audit.py — and clones anything
missing from disk into the exact path it had before.

Run it after cloning the monorepo itself:

  git clone https://github.com/joshgreenman1973/experiments.git ~/Experiments
  cd ~/Experiments
  python3 scripts/restore-clones.py           # dry run: shows what it would do
  python3 scripts/restore-clones.py --clone   # actually clone

It never touches a directory that already exists, so it is safe to re-run.
Repos with no GitHub remote cannot be restored by this script — it lists
them at the end so nothing disappears silently.
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DO_CLONE = "--clone" in sys.argv

inv_path = os.path.join(ROOT, "machine", "repos.json")
if not os.path.exists(inv_path):
    sys.exit("machine/repos.json not found — run scripts/sync-audit.py on the "
             "old machine and commit the result before migrating.")
inv = json.load(open(inv_path))

missing = [r for r in inv["nested"]
           if not os.path.isdir(os.path.join(ROOT, r["relPath"]))]
print(f"nested repos in inventory: {len(inv['nested'])}   "
      f"already on disk: {len(inv['nested']) - len(missing)}   "
      f"missing: {len(missing)}\n")

failures = []
for r in missing:
    dest = os.path.join(ROOT, r["relPath"])
    if DO_CLONE:
        print(f"cloning {r['remote']} -> {r['relPath']}")
        res = subprocess.run(["git", "clone", r["remote"], dest])
        if res.returncode != 0:
            failures.append(r["relPath"])
    else:
        print(f"would clone {r['remote']} -> {r['relPath']}")

if not DO_CLONE and missing:
    print("\n(dry run — pass --clone to do it)")

if inv.get("no_remote"):
    print("\nNOT RESTORABLE (no GitHub remote — copy these from the old "
          "machine or a backup):")
    for p in inv["no_remote"]:
        print(f"  {p}")

if inv.get("external"):
    print("\nOUTSIDE ~/Experiments (this script does not restore these — "
          "see MIGRATION.md):")
    for e in inv["external"]:
        state = e["remote"] or ("in git, no remote" if e["in_git"] else "NOT in git")
        print(f"  {e['path']}  ({state})")

if failures:
    print("\nFAILED CLONES:")
    for f in failures:
        print(f"  {f}")
    sys.exit(1)
