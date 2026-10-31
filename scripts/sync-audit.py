#!/usr/bin/env python3
"""Sync audit: is every project safe to lose this machine?

Walks the Experiments monorepo, every nested git repo inside it (up to three
folders down), and a short list of project directories that live outside
Experiments. It also lists folders inside Experiments that no repo holds at
all. For each
one it answers the only question that matters for migration: if this
laptop died right now, what would be lost?

Flags, in order of severity:
  NOT-IN-GIT     directory has no .git at all
  NO-REMOTE      repo exists but has no GitHub remote
  UNREACHABLE    --fetch failed as every signed-in account; it would not clone
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
import json, os, re, shutil, subprocess, sys, datetime, threading, concurrent.futures as cf

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


def git(path, *args, timeout=60, env=None):
    r = subprocess.run(["git", "-C", path] + list(args),
                       capture_output=True, text=True, timeout=timeout, env=env)
    return r.stdout.strip() if r.returncode == 0 else None


GH = shutil.which("gh") or os.path.join(HOME, ".local", "bin", "gh")
_tokens = {}
_tokens_lock = threading.Lock()  # audit_repo runs on 12 threads


def fetch_as_owner(path, remote):
    """gh's sign-in helper only serves the ACTIVE GitHub account, so fetching
    the other account's private repos failed quietly and their ahead/behind
    counts went stale. Try the owning account first, each with a token for
    that one command; the active account never changes."""
    if not os.path.exists(GH):
        return git(path, "fetch", "--quiet", timeout=120) is not None
    with _tokens_lock:
        if not _tokens:
            st = subprocess.run([GH, "auth", "status"], capture_output=True, text=True)
            for acct in sorted(set(re.findall(r"account (\S+)", st.stdout + st.stderr))):
                _tokens[acct] = subprocess.run([GH, "auth", "token", "--user", acct],
                                               capture_output=True, text=True).stdout.strip()
    owner = (remote or "").split("github.com/", 1)[-1].split("/")[0].lower()
    for acct in sorted(_tokens, key=lambda a: a.lower() != owner):
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GH_TOKEN=_tokens[acct])
        if git(path, "fetch", "--quiet", timeout=120, env=env) is not None:
            return True
    return False


def audit_repo(path):
    rec = {"path": path, "name": os.path.basename(path.rstrip("/")), "flags": []}
    if not os.path.isdir(os.path.join(path, ".git")):
        rec["flags"].append("NOT-IN-GIT")
        return rec

    # A fetch that fails as every signed-in account means a new Mac could not
    # clone this repo either: renamed, deleted, or no account has access.
    origin = git(path, "remote", "get-url", "origin")
    if DO_FETCH and origin and not fetch_as_owner(path, origin):
        rec["flags"].append("UNREACHABLE")

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


# Folders that are never projects: Claude's scratch worktrees, dependency
# installs and build output. Everything else that git can't see gets listed.
SKIP_DIRS = {".git", ".claude", "node_modules", ".venv", "venv", "__pycache__",
             ".pytest_cache", ".next", ".cache", ".wrangler", ".netlify"}
MAX_DEPTH = 3  # nyc-data/<project>, vital-city-tools/<project>, personal/<project>


def find_repos():
    """Every nested repo up to MAX_DEPTH folders down, not just the top level.

    Container folders like nyc-data/ and vital-city-tools/ are not repos
    themselves but hold dozens; an audit that stopped one level down left
    36 projects off machine/repos.json, so a new Mac would not have cloned
    them. A repo's own subfolders are not searched.
    """
    repos = [ROOT]

    def walk(d, depth):
        try:
            entries = sorted(os.listdir(d))
        except OSError:
            return
        for entry in entries:
            p = os.path.join(d, entry)
            if entry in SKIP_DIRS or not os.path.isdir(p) or os.path.islink(p):
                continue
            if os.path.isdir(os.path.join(p, ".git")):
                repos.append(p)
            elif depth < MAX_DEPTH:
                walk(p, depth + 1)

    walk(ROOT, 1)
    repos += [p for p in EXTERNAL if os.path.isdir(p)]
    return repos


def du_mb(path):
    r = subprocess.run(["du", "-sk", path], capture_output=True, text=True)
    try:
        return round(int(r.stdout.split()[0]) / 1024)
    except (IndexError, ValueError):
        return None


def find_local_only(repo_paths):
    """Folders inside ~/Experiments that no git repo holds: not committed to
    the monorepo (untracked or gitignored) and not a nested repo either.
    GitHub has no copy of these; Time Machine is their only backup.

    git reports the top-most such folder. When that folder is a container
    holding nested repos (personal/, vital-city-tools/), look inside it and
    report the children that aren't repos.
    """
    out = git(ROOT, "status", "--porcelain", "--ignored", "--untracked-files=normal") or ""
    candidates = [l[3:].rstrip("/") for l in out.splitlines()
                  if l[:3] in ("?? ", "!! ") and l.endswith("/")]
    repo_set = set(repo_paths)
    found = []

    # kind "project": a whole project folder (top level, or directly inside a
    # container like nyc-data/). kind "inside-project": a gitignored folder
    # within a project that is on GitHub, usually downloaded data or build
    # output the project's own scripts can recreate.
    def holds_repos(p):
        return any(r.startswith(p + os.sep) for r in repo_set)

    def consider(rel):
        p = os.path.join(ROOT, rel)
        if (set(rel.split("/")) & SKIP_DIRS or p in repo_set
                or not os.path.isdir(p) or os.path.islink(p)):
            return
        if holds_repos(p):
            for child in sorted(os.listdir(p)):
                consider(f"{rel}/{child}")
            return
        parent = os.path.dirname(p)
        kind = "project" if parent == ROOT or holds_repos(parent) else "inside-project"
        found.append({"path": p, "mb": du_mb(p), "kind": kind})

    for rel in candidates:
        consider(rel)
    # git lists ignored folders inside untracked ones separately; keep the outer one
    found.sort(key=lambda f: f["path"])
    kept = []
    for f in found:
        if not any(f["path"].startswith(k["path"] + os.sep) for k in kept):
            kept.append(f)
    return kept


# Losing these means losing work. BEHIND/STASHES are informational.
CRITICAL = {"NOT-IN-GIT", "NO-REMOTE", "UNREACHABLE", "MID-REBASE", "UNPUSHED",
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

    local_only = find_local_only(repos)
    if local_only:
        print("=== ONLY ON THIS MACHINE (in no git repo; Time Machine is the backup) ===")
        for kind, label in [("project", "project folders"),
                            ("inside-project", "data or build folders inside projects")]:
            print(f"  -- {label}")
            for f in local_only:
                if f["kind"] == kind:
                    print(f"  {os.path.relpath(f['path'], ROOT):<44} {f['mb']} MB")
        print()

    # sync-report.json is gitignored, so the local-only folder names stay out
    # of the public repo; the snapshot carries them to the private one.
    report = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "fetched": DO_FETCH,
        "checked": len(results),
        "at_risk": len(problems),
        "repos": results,
        "local_only": local_only,
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
