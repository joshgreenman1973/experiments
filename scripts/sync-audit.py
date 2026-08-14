#!/usr/bin/env python3
"""Sync audit: is every project safe to lose this machine?

Walks the Experiments monorepo, every nested git repo inside it, and a
short list of project directories that live outside Experiments. For each
one it answers the only question that matters for migration: if this
laptop died right now, what would be lost?

Flags, in order of severity:
  NOT-IN-GIT     directory has no .git at all
  NO-REMOTE      repo exists but has no GitHub remote
  MID-REBASE     repo is stuck in a rebase/merge/cherry-pick
  UNPUSHED       commits on the current branch that origin doesn't have
  DETACHED       HEAD is not on any branch
  NO-UPSTREAM    branch has no upstream tracking ref
  DIRTY          uncommitted changes (modified or untracked files)
  BEHIND         origin has commits this clone doesn't (info only)
  STASHES        stash entries that would be lost (info only)

Usage:
  python3 scripts/sync-audit.py            # fast: uses local refs only
  python3 scripts/sync-audit.py --fetch    # accurate: fetches every remote first
  python3 scripts/sync-audit.py --json     # also print the JSON report

Writes sync-report.json next to this script's parent (Experiments root).
Exits 1 if anything would be lost (so cron/CI fails loud), 0 if clean.
"""
import json, os, subprocess, sys, datetime, concurrent.futures as cf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")

# Project directories that live outside ~/Experiments but matter just as much.
# Add to this list when a new outside-the-monorepo project starts.
EXTERNAL = [
    os.path.join(HOME, "personal-dashboard"),
    os.path.join(HOME, "streetlightmeter-api"),
    os.path.join(HOME, "Debrief"),
    os.path.join(HOME, ".claude"),  # memory, settings, scheduled tasks
]

DO_FETCH = "--fetch" in sys.argv
PRINT_JSON = "--json" in sys.argv


def git(path, *args, timeout=60):
    r = subprocess.run(["git", "-C", path] + list(args),
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip() if r.returncode == 0 else None


def audit_repo(path):
    rec = {"path": path, "name": os.path.basename(path.rstrip("/")), "flags": []}
    if not os.path.isdir(os.path.join(path, ".git")):
        rec["flags"].append("NOT-IN-GIT")
        return rec

    if DO_FETCH:
        git(path, "fetch", "--quiet", timeout=120)

    gitdir = git(path, "rev-parse", "--git-dir") or os.path.join(path, ".git")
    if not os.path.isabs(gitdir):
        gitdir = os.path.join(path, gitdir)
    for marker, flag in [("rebase-merge", "MID-REBASE"), ("rebase-apply", "MID-REBASE"),
                         ("MERGE_HEAD", "MID-REBASE"), ("CHERRY_PICK_HEAD", "MID-REBASE")]:
        if os.path.exists(os.path.join(gitdir, marker)):
            rec["flags"].append(flag)
            break

    rec["remote"] = git(path, "remote", "get-url", "origin")
    if not rec["remote"]:
        rec["flags"].append("NO-REMOTE")

    branch = git(path, "branch", "--show-current")
    rec["branch"] = branch
    if branch == "" and "MID-REBASE" not in rec["flags"]:
        rec["flags"].append("DETACHED")

    status = git(path, "status", "--porcelain")
    dirty = [l for l in (status or "").splitlines() if l.strip()]
    rec["dirty"] = len(dirty)
    if dirty:
        rec["flags"].append("DIRTY")

    if rec["remote"] and branch:
        upstream = git(path, "rev-parse", "--abbrev-ref", "@{u}")
        if upstream:
            ahead = git(path, "rev-list", "--count", "@{u}..HEAD")
            behind = git(path, "rev-list", "--count", "HEAD..@{u}")
            rec["ahead"] = int(ahead or 0)
            rec["behind"] = int(behind or 0)
            if rec["ahead"]:
                rec["flags"].append("UNPUSHED")
            if rec["behind"]:
                rec["flags"].append("BEHIND")
        else:
            rec["flags"].append("NO-UPSTREAM")

    stashes = git(path, "stash", "list")
    rec["stashes"] = len((stashes or "").splitlines())
    if rec["stashes"]:
        rec["flags"].append("STASHES")

    return rec


def find_repos():
    repos = [ROOT]
    for entry in sorted(os.listdir(ROOT)):
        p = os.path.join(ROOT, entry)
        if os.path.isdir(os.path.join(p, ".git")):
            repos.append(p)
    repos += [p for p in EXTERNAL if os.path.isdir(p)]
    return repos


# Losing these means losing work. BEHIND/STASHES are informational.
CRITICAL = {"NOT-IN-GIT", "NO-REMOTE", "MID-REBASE", "UNPUSHED",
            "DETACHED", "NO-UPSTREAM", "DIRTY"}


def main():
    repos = find_repos()
    with cf.ThreadPoolExecutor(12) as ex:
        results = list(ex.map(audit_repo, repos))

    problems = [r for r in results if set(r["flags"]) & CRITICAL]
    info_only = [r for r in results if r["flags"] and not (set(r["flags"]) & CRITICAL)]

    mode = "fetched remotes" if DO_FETCH else "local refs only (run with --fetch for ahead/behind accuracy)"
    print(f"sync-audit: {len(results)} repos checked, {mode}")
    print(f"clean: {len(results) - len(problems) - len(info_only)}   "
          f"info-only: {len(info_only)}   at-risk: {len(problems)}\n")

    if problems:
        print("=== WOULD LOSE WORK IF THIS MACHINE DIED ===")
        for r in sorted(problems, key=lambda r: r["name"]):
            parts = [",".join(f for f in r["flags"] if f in CRITICAL)]
            if r.get("dirty"):
                parts.append(f"{r['dirty']} dirty files")
            if r.get("ahead"):
                parts.append(f"{r['ahead']} unpushed commits")
            if not r.get("remote"):
                parts.append("no GitHub remote")
            print(f"  {r['name']:<32} {'; '.join(parts)}")
        print()

    if info_only:
        print("=== INFO (nothing at risk) ===")
        for r in sorted(info_only, key=lambda r: r["name"]):
            print(f"  {r['name']:<32} {','.join(r['flags'])}")
        print()

    report = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "fetched": DO_FETCH,
        "checked": len(results),
        "at_risk": len(problems),
        "repos": results,
    }
    out = os.path.join(ROOT, "sync-report.json")
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"report written to {out}")

    # machine/repos.json is the committed inventory restore-clones.py reads:
    # every nested repo on disk and its remote. The manifest can't provide
    # this — it is rebuilt by CI, which can't see this machine's folders.
    inventory = {
        "note": "Generated by scripts/sync-audit.py. Commit when it changes.",
        "nested": sorted(
            [{"relPath": os.path.relpath(r["path"], ROOT), "remote": r["remote"]}
             for r in results
             if r["path"] != ROOT and r["path"].startswith(ROOT) and r.get("remote")],
            key=lambda x: x["relPath"]),
        "no_remote": sorted(
            os.path.relpath(r["path"], ROOT) for r in results
            if r["path"] != ROOT and r["path"].startswith(ROOT)
            and "NO-REMOTE" in r["flags"]),
        "external": sorted(
            [{"path": r["path"], "remote": r.get("remote"),
              "in_git": "NOT-IN-GIT" not in r["flags"]}
             for r in results if not r["path"].startswith(ROOT)],
            key=lambda x: x["path"]),
    }
    inv_path = os.path.join(ROOT, "machine", "repos.json")
    os.makedirs(os.path.dirname(inv_path), exist_ok=True)
    with open(inv_path, "w") as f:
        json.dump(inventory, f, indent=2)
    print(f"inventory written to {inv_path}")

    if PRINT_JSON:
        print(json.dumps(report, indent=2))

    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
