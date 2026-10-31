#!/usr/bin/env python3
"""Restore every nested project repo onto a fresh machine.

The Experiments monorepo tracks ~77 projects directly; the other ~120 live
as independent git repos nested inside ~/Experiments. This script reads
machine/repos.json — a committed inventory of every nested repo and its
remote, kept current by scripts/sync-audit.py — and clones anything
missing from disk into the exact path it had before.

Run it after cloning the monorepo itself:

  git clone https://github.com/joshgreenman1973/experiments.git ~/Experiments
  python3 ~/.claude/machine-kit/restore-clones.py           # dry run
  python3 ~/.claude/machine-kit/restore-clones.py --clone   # actually clone

(The machine-kit copy is refreshed daily by the snapshot, so it is current
even when this repo has unpushed commits. Sign in to both GitHub accounts
with `gh auth login` first; each repo is cloned as the account that owns it.)

It never touches a directory that already exists, so it is safe to re-run.
Repos with no GitHub remote cannot be restored by this script — it lists
them at the end so nothing disappears silently.
"""
import json, os, re, shutil, subprocess, sys

# Fixed path rather than "wherever this script sits": the daily snapshot keeps
# a current copy in ~/.claude/machine-kit/, which is the one to run on a new
# Mac when this repo's copy hasn't been pushed lately.
ROOT = os.path.expanduser("~/Experiments")
DO_CLONE = "--clone" in sys.argv
GH = shutil.which("gh") or os.path.expanduser("~/.local/bin/gh")


def signed_in_accounts():
    r = subprocess.run([GH, "auth", "status"], capture_output=True, text=True)
    return sorted(set(re.findall(r"account (\S+)", r.stdout + r.stderr)))


ACCOUNTS = signed_in_accounts() if os.path.exists(GH) else []
_tokens = {}


def clone(remote, dest):
    """gh's sign-in helper only serves the ACTIVE account, so with both
    joshgreenman1973 and vitalcity-nyc signed in, the other account's private
    repos fail to clone. Try the account that owns the repo first, then the
    rest, each with a token for that one command; the active account never
    changes."""
    owner = remote.split("github.com/", 1)[-1].split("/")[0].lower()
    for acct in sorted(ACCOUNTS, key=lambda a: a.lower() != owner) or [None]:
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        if acct:
            if acct not in _tokens:
                _tokens[acct] = subprocess.run([GH, "auth", "token", "--user", acct],
                                               capture_output=True, text=True).stdout.strip()
            env["GH_TOKEN"] = _tokens[acct]
        if subprocess.run(["git", "clone", "--quiet", remote, dest], env=env).returncode == 0:
            return True
        shutil.rmtree(dest, ignore_errors=True)
    return False

# Two copies of the inventory: the one committed here, and the one the weekly
# snapshot pushes to the private claude-config repo (~/.claude/machine-kit).
# Either can lag the other, so merge them and restore everything either knows.
inv_paths = [os.path.join(ROOT, "machine", "repos.json"),
             os.path.expanduser("~/.claude/machine-kit/repos.json")]
invs = [json.load(open(p)) for p in inv_paths if os.path.exists(p)]
if not invs:
    sys.exit("No repos.json found in machine/ or ~/.claude/machine-kit/ — run "
             "scripts/sync-audit.py on the old machine before migrating.")
inv = max(invs, key=lambda i: len(i.get("nested", [])))
seen = {r["relPath"] for r in inv["nested"]}
for other in invs:
    for r in other.get("nested", []):
        if r["relPath"] not in seen:
            inv["nested"].append(r)
            seen.add(r["relPath"])

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
        if not clone(r["remote"], dest):
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
          "see ~/.claude/NEW-MAC.md):")
    for e in inv["external"]:
        state = e["remote"] or ("in git, no remote" if e["in_git"] else "NOT in git")
        print(f"  {e['path']}  ({state})")

if failures:
    print("\nFAILED CLONES:")
    for f in failures:
        print(f"  {f}")
    sys.exit(1)
