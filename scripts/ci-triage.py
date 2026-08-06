#!/usr/bin/env python3
"""Find GitHub Actions workflows that are broken right now, and say why.

This is the eyes of the auto-repair loop. It answers one question per
workflow: is the LATEST run failing? A workflow that failed on Tuesday and
succeeded on Wednesday is healthy and is not reported.

Getting the error right matters more than finding the failure. `gh run view
--log-failed` tails post-job cleanup, so the real message is buried. This
walks the jobs API to the exact step that failed, then reads the log around
its ##[error] marker, with runner boilerplate stripped out.

Findings are classified so the repair agent knows what it is looking at:

  transient  GitHub's own infrastructure wobbled -- Pages deploy queue, a
             cancelled runner, an action download 503. Re-run it; changing
             code would be wrong.
  guard      A deliberate fail-loud check tripped (a scraper refusing to ship
             empty or unsummarized data). The pipeline is working as designed
             and is asking for content, not a code fix.
  upstream   A data source moved, changed shape or started refusing us.
  auth       A secret expired or a token lost a scope. Josh has to fix this
             himself -- Claude is not permitted to enter credentials.
  real       The job's own code or config broke.

Writes JSON to stdout, a human-readable summary to stderr.

Usage:
  python3 scripts/ci-triage.py                      # both accounts
  python3 scripts/ci-triage.py --account vitalcity-nyc
  python3 scripts/ci-triage.py --quiet              # JSON only
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
import datetime

ACCOUNTS = ["joshgreenman1973", "vitalcity-nyc"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = datetime.datetime.now(datetime.timezone.utc)

# Runner noise that crowds out the actual error. Dropped before classifying.
NOISE = re.compile(
    r"^\s*(pythonLocation|PKG_CONFIG_PATH|Python[0-9_]*_ROOT_DIR|LD_LIBRARY_PATH|"
    r"AGENT_TOOLSDIRECTORY|shell:|env:|##\[endgroup\]|\[command\]/usr/bin/git|"
    r"Temporarily overriding HOME|Adding repository directory|git version)")

# Ordered: infrastructure first, then intent, then blame.
TRANSIENT = [
    (r"Timeout reached, aborting", "Pages deploy queue timed out"),
    (r"deployment_queued", "Pages deploy queue backed up"),
    (r"Deployment failed, try again later", "Pages deploy failed, retryable"),
    (r"Failed to resolve action download info", "GitHub could not serve an action"),
    (r"Service Unavailable|502 Bad Gateway|503 |504 Gateway", "GitHub or an upstream returned 5xx"),
    (r"The (job|operation) was canceled", "run cancelled, probably superseded"),
    (r"__JOB_CANCELLED__", "the job was cancelled before it ran"),
    (r"canceling since a higher priority waiting request", "superseded by a newer run"),
    (r"The runner has received a shutdown signal", "runner shut down mid-job"),
    (r"unable to access 'https://github\.com", "transient git network error"),
    (r"Connection reset by peer|Temporary failure in name resolution", "network blip"),
    (r"fatal: the remote end hung up|RPC failed", "git transport failed"),
]

# Tight patterns only. A bare "401" matches line numbers and byte counts.
AUTH = [
    (r"Bad credentials|401 Unauthorized|HTTP 401|Error 401", "credentials rejected"),
    (r"Authentication failed|authentication required", "authentication failed"),
    (r"[Ii]ncorrect API key|[Ii]nvalid API key|invalid_api_key", "an API key is wrong"),
    (r"API rate limit exceeded|rate limit exceeded", "rate limited"),
    (r"Resource not accessible by integration", "workflow token lacks a permission"),
    (r"without `workflow` scope", "token lacks the workflow scope"),
    (r"Input required and not supplied", "a required secret or input is missing"),
    (r"KeyError: '[A-Z][A-Z0-9_]*(KEY|TOKEN|SECRET|PASSWORD)'", "a required secret is missing"),
    (r"403 Forbidden|HTTP 403", "access forbidden"),
    (r"out of .{0,20}credits|insufficient[_ ]quota|billing|payment required",
     "a paid API ran out of credit -- needs Josh"),
]

# Fail-loud guards: the job deliberately refused to ship bad or thin data.
GUARD = [
    (r"^FAIL:", "a fail-loud data guard tripped"),
    (r"(refus|abort)\w*[^\n]{0,40}(empty|zero rows|no rows|no records)", "refused to ship empty data"),
    (r"sys\.exit\(1\)[^\n]*guard", "a guard exited non-zero"),
    (r"not yet summarized|awaiting summary|missing summar", "content is waiting to be written"),
]

UPSTREAM = [
    (r"JSONDecodeError|Expecting value: line 1", "a data source returned non-JSON"),
    (r"requests\.exceptions\.\w*(Timeout|Connection)", "a data source timed out or refused"),
    (r"HTTPError|urllib\.error|requests\.exceptions\.", "an HTTP call to a data source failed"),
    (r"404 Client Error|HTTP 404|404 Not Found", "a data source URL 404'd"),
    (r"KeyError: '[a-z][a-z0-9_]*'", "a data source changed its field names"),
    (r"No such file or directory[^\n]*\.(csv|json|geojson|xlsx|zip)",
     "an expected data file was missing"),
    (r"EmptyDataError|No columns to parse", "a data source returned an empty file"),
]


def sh(args, timeout=120):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def gh_json(args, timeout=120):
    out = sh(["gh"] + args, timeout=timeout)
    try:
        return json.loads(out) if out.strip() else None
    except json.JSONDecodeError:
        return None


def local_clones():
    """Map 'owner/repo' -> local directory. Folder names do not reliably match
    repo names here, so trust the git remote, never the directory name."""
    m = {}
    for entry in os.scandir(ROOT):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        candidates = [entry.path]
        try:
            candidates += [d.path for d in os.scandir(entry.path)
                           if d.is_dir() and not d.name.startswith(".")]
        except OSError:
            pass
        for path in candidates:
            if not os.path.isdir(os.path.join(path, ".git")):
                continue
            url = sh(["git", "-C", path, "remote", "get-url", "origin"], timeout=15).strip()
            if url:
                nwo = re.sub(r"\.git$", "", re.sub(r".*github\.com[:/]", "", url))
                m.setdefault(nwo, path)
    return m


def repos_for(account):
    data = gh_json(["repo", "list", account, "--limit", "300", "--json", "nameWithOwner"])
    return [r["nameWithOwner"] for r in (data or [])]


def latest_run_per_workflow(nwo):
    """Only the newest run of each workflow matters -- an old failure that was
    later fixed is not a live problem."""
    data = gh_json(["api", f"repos/{nwo}/actions/runs?per_page=60"], timeout=90)
    seen, out = set(), []
    for run in (data or {}).get("workflow_runs", []):
        wf = run.get("workflow_id")
        if wf in seen:
            continue
        seen.add(wf)
        out.append(run)
    return out


def disabled_workflow_ids(nwo):
    """Workflow ids that are switched off, so their last failure is not live.

    A disabled workflow keeps its final failing run forever. Without this, an
    intentionally-parked job (block-pulse, waiting on API credit) resurfaces in
    every scan and burns a repair slot on something that cannot run.
    """
    data = gh_json(["api", f"repos/{nwo}/actions/workflows?per_page=100"], timeout=90)
    return {w["id"] for w in (data or {}).get("workflows", [])
            if w.get("state") != "active"}


def failed_step(nwo, run_id):
    """The job and step that actually failed, via the jobs API.

    A run can be marked failure while its only job says 'cancelled' with no
    steps -- that is a concurrency guard or a superseded run, and there is no
    log to read. Signal it so classify() calls it transient instead of
    inventing a code bug."""
    data = gh_json(["api", f"repos/{nwo}/actions/runs/{run_id}/jobs"], timeout=90)
    jobs = (data or {}).get("jobs", [])
    for job in jobs:
        if job.get("conclusion") not in ("failure", "timed_out"):
            continue
        step = next((s for s in job.get("steps", [])
                     if s.get("conclusion") in ("failure", "timed_out")), None)
        return job.get("id"), job.get("name"), (step or {}).get("name")
    if jobs and all(j.get("conclusion") == "cancelled" for j in jobs):
        return "cancelled", jobs[0].get("name"), None
    return None, None, None


def failure_text(nwo, job_id, before=40, after=4):
    """The log around the last ##[error], boilerplate stripped. This is the
    text a human would actually read to understand the failure."""
    raw = sh(["gh", "api", f"repos/{nwo}/actions/jobs/{job_id}/logs"], timeout=120)
    if not raw:
        return ""
    lines = [re.sub(r"^[0-9]{4}-[0-9-]*T[0-9:.]+Z\s?", "", ln) for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln.strip() and not NOISE.match(ln)]
    idx = max((i for i, ln in enumerate(lines) if "##[error]" in ln), default=len(lines) - 1)
    return "\n".join(lines[max(0, idx - before): idx + after])[-3000:]


def classify(text):
    for rules, kind in ((TRANSIENT, "transient"), (AUTH, "auth"),
                        (GUARD, "guard"), (UPSTREAM, "upstream")):
        for rx, why in rules:
            if re.search(rx, text, re.I | re.M):
                return kind, why
    m = re.search(r"^([A-Za-z_.]*(?:Error|Exception))\b:?(.*)$", text, re.M)
    if m:
        return "real", f"{m.group(1)}{m.group(2)[:70].rstrip()}".strip()
    return "real", "the job exited non-zero"


def inspect(nwo):
    findings = []
    runs = [r for r in latest_run_per_workflow(nwo)
            if r.get("conclusion") in ("failure", "startup_failure", "timed_out")]
    if not runs:
        return findings
    # Only worth an extra API call once we know this repo has something failing.
    off = disabled_workflow_ids(nwo)
    for run in runs:
        if run.get("workflow_id") in off:
            continue
        job_id, job_name, step_name = failed_step(nwo, run["id"])
        if job_id == "cancelled":
            text, job_id = "__JOB_CANCELLED__", None
        else:
            text = failure_text(nwo, job_id) if job_id else ""
        if not text:
            text = sh(["gh", "run", "view", str(run["id"]), "-R", nwo,
                       "--log-failed"], timeout=120)[-3000:]
        kind, why = classify(text)
        age_h = round((NOW - datetime.datetime.fromisoformat(
            run["created_at"].replace("Z", "+00:00"))).total_seconds() / 3600, 1)
        findings.append({
            "repo": nwo,
            "account": nwo.split("/")[0],
            "workflow": run.get("name"),
            "workflow_path": run.get("path"),
            "run_id": run["id"],
            "run_url": run.get("html_url"),
            "job_name": job_name,
            "failed_step": step_name,
            "head_sha": (run.get("head_sha") or "")[:8],
            "branch": run.get("head_branch"),
            "event": run.get("event"),
            "age_hours": age_h,
            "kind": kind,
            "why": why,
            "error": text,
        })
    return findings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", action="append", help="limit to one account (repeatable)")
    ap.add_argument("--quiet", action="store_true", help="JSON only, nothing on stderr")
    args = ap.parse_args()

    accounts = args.account or ACCOUNTS
    repos = []
    for a in accounts:
        repos += repos_for(a)
    if not repos:
        print("ci-triage: could not list any repositories -- is gh authenticated?",
              file=sys.stderr)
        sys.exit(2)

    clones = local_clones()
    findings = []
    with cf.ThreadPoolExecutor(12) as ex:
        for res in ex.map(inspect, repos):
            findings += res
    for f in findings:
        f["local_path"] = clones.get(f["repo"])

    rank = {"real": 0, "guard": 1, "upstream": 2, "auth": 3, "transient": 4}
    findings.sort(key=lambda f: (rank.get(f["kind"], 9), -f["age_hours"]))

    print(json.dumps({
        "generated_at": NOW.isoformat(),
        "repos_scanned": len(repos),
        "accounts": accounts,
        "findings": findings,
    }, indent=2))

    if not args.quiet:
        counts = {}
        for f in findings:
            counts[f["kind"]] = counts.get(f["kind"], 0) + 1
        print(f"\nscanned {len(repos)} repos across {', '.join(accounts)}", file=sys.stderr)
        print(f"broken workflows: {len(findings)}  " +
              "  ".join(f"{k}={v}" for k, v in sorted(counts.items())), file=sys.stderr)
        for f in findings:
            print(f"  [{f['kind']:<9}] {f['repo']} / {f['workflow']}"
                  f"  ({f['age_hours']}h) -- {f['why']}", file=sys.stderr)


if __name__ == "__main__":
    main()
