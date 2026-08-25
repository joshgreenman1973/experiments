#!/usr/bin/env python3
"""Decide what the auto-repair loop should actually work on, and remember what
it already tried.

Triage finds what is broken. This decides what is worth touching, and -- more
importantly -- what to stop touching. An agent that retries the same doomed fix
every two hours is worse than no agent: it burns tokens, rewrites history and
trains Josh to ignore the alerts.

The rules:

  transient  Re-run the job. Never edit code. Capped at 3 re-runs per failure
             signature per 24h, because if a fourth re-run is needed the
             problem is not the queue.
  auth       Never attempted. Claude is not permitted to enter credentials or
             set secrets. Escalated to Josh once, then silent.
  real,
  upstream,
  guard      Diagnose and fix. Two attempts per signature. After the second
             failed attempt the item is escalated and parked.

A "signature" is the repo, the workflow and the shape of the error with
numbers, timestamps and paths normalized out. A genuinely new error gets a
fresh budget; the same error recurring does not.

Usage:
  python3 scripts/ci-triage.py | python3 scripts/ci-repair-queue.py
  python3 scripts/ci-repair-queue.py --record <sig> --outcome fixed|failed|rerun
  python3 scripts/ci-repair-queue.py --state          # dump the ledger
  python3 scripts/ci-repair-queue.py --forget <sig>   # clear one entry
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(ROOT, ".ci-autorepair")
STATE = os.path.join(STATE_DIR, "state.json")
LOG = os.path.join(STATE_DIR, "history.log")
NOW = datetime.datetime.now(datetime.timezone.utc)

MAX_FIX_ATTEMPTS = 2
MAX_RERUNS = 3
RERUN_WINDOW_H = 24
# Once escalated, stay quiet for this long even if the failure persists.
ESCALATION_COOLDOWN_H = 168  # one week


def load():
    try:
        with open(STATE) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def save(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
    os.replace(tmp, STATE)


def note(line):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(LOG, "a") as fh:
        fh.write(f"{NOW.isoformat()}  {line}\n")


def signature(f):
    """Stable id for 'this specific failure'. Numbers, hex, timestamps and
    absolute paths are stripped so the same bug hashes the same way on a
    later run, but a different bug does not."""
    text = f.get("error", "")[-1500:]
    text = re.sub(r"\d{4}-\d{2}-\d{2}[T ][\d:.]+Z?", "", text)
    text = re.sub(r"0x[0-9a-f]+|\b[0-9a-f]{7,40}\b", "", text, flags=re.I)
    text = re.sub(r"/home/runner/work/[^\s:]*|/opt/hostedtoolcache/[^\s:]*", "", text)
    text = re.sub(r"\d+", "N", text)
    text = re.sub(r"\s+", " ", text).strip()
    key = f"{f['repo']}::{f.get('workflow')}::{text}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def hours_since(iso):
    if not iso:
        return 1e9
    try:
        return (NOW - datetime.datetime.fromisoformat(iso)).total_seconds() / 3600
    except ValueError:
        return 1e9


def site_is_live(repo):
    """A failed Pages deploy usually means the queue backed up while the
    content shipped fine on a later run. The build status lies; the deployed
    page does not. Returns True when the site serves real content."""
    owner, name = repo.split("/", 1)
    url = f"https://{owner}.github.io/{name}/"
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code} %{size_download}",
             "-L", "--max-time", "20", f"{url}?cb=cirepair"],
            capture_output=True, text=True, timeout=30)
        code, _, size = r.stdout.strip().partition(" ")
        return code == "200" and int(size or 0) > 400
    except Exception:
        return False


def decide(f, entry):
    """-> (action, reason). Actions: rerun, fix, escalate, skip."""
    kind = f["kind"]
    attempts = entry.get("fix_attempts", 0)
    reruns = [t for t in entry.get("reruns", []) if hours_since(t) < RERUN_WINDOW_H]

    if entry.get("escalated_at") and hours_since(entry["escalated_at"]) < ESCALATION_COOLDOWN_H:
        return "skip", "already escalated to Josh, in cooldown"

    if kind == "auth":
        return "escalate", "needs a credential or a payment -- Claude must not touch either"

    if kind == "transient":
        if "pages" in (f.get("workflow") or "").lower() and site_is_live(f["repo"]):
            return "skip", "site is live and serving content; the failed deploy was cosmetic"
        if len(reruns) >= MAX_RERUNS:
            return "escalate", (f"re-ran {len(reruns)}x in {RERUN_WINDOW_H}h and it still "
                                "fails -- this is not just the queue")
        return "rerun", "GitHub-side wobble; re-running without changing anything"

    if attempts >= MAX_FIX_ATTEMPTS:
        return "escalate", f"{attempts} repair attempts already failed on this same error"
    return "fix", ("first repair attempt" if not attempts
                   else f"retry after {attempts} failed attempt(s)")


def build_queue(payload):
    state = load()
    out = []
    for f in payload.get("findings", []):
        sig = signature(f)
        entry = state.get(sig, {})
        action, reason = decide(f, entry)
        item = dict(f)
        item.pop("error", None)
        out.append({
            **item,
            "signature": sig,
            "action": action,
            "reason": reason,
            "prior_fix_attempts": entry.get("fix_attempts", 0),
            "first_seen": entry.get("first_seen", NOW.isoformat()),
            "error": f.get("error", ""),
        })
        state.setdefault(sig, {}).setdefault("first_seen", NOW.isoformat())
        state[sig].update({
            "repo": f["repo"], "workflow": f.get("workflow"),
            "kind": f["kind"], "why": f.get("why"),
            "last_seen": NOW.isoformat(),
        })
    save(state)
    return out


def record(sig, outcome, detail=""):
    state = load()
    e = state.setdefault(sig, {"first_seen": NOW.isoformat()})
    if outcome == "fixed":
        e["fix_attempts"] = 0
        e["reruns"] = []
        e.pop("escalated_at", None)
        e["last_fixed_at"] = NOW.isoformat()
    elif outcome == "failed":
        e["fix_attempts"] = e.get("fix_attempts", 0) + 1
        e["last_attempt_at"] = NOW.isoformat()
    elif outcome == "rerun":
        e.setdefault("reruns", []).append(NOW.isoformat())
    elif outcome == "escalated":
        e["escalated_at"] = NOW.isoformat()
    else:
        print(f"unknown outcome: {outcome}", file=sys.stderr)
        sys.exit(2)
    if detail:
        e["last_detail"] = detail[:400]
    save(state)
    note(f"{outcome:<9} {sig}  {e.get('repo','?')} / {e.get('workflow','?')}  {detail[:160]}")
    print(f"recorded {outcome} for {sig}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", metavar="SIG")
    ap.add_argument("--outcome", choices=["fixed", "failed", "rerun", "escalated"])
    ap.add_argument("--detail", default="")
    ap.add_argument("--state", action="store_true")
    ap.add_argument("--forget", metavar="SIG")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.state:
        print(json.dumps(load(), indent=2, sort_keys=True))
        return
    if args.forget:
        st = load()
        st.pop(args.forget, None)
        save(st)
        print(f"forgot {args.forget}")
        return
    if args.record:
        if not args.outcome:
            ap.error("--record requires --outcome")
        record(args.record, args.outcome, args.detail)
        return

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("ci-repair-queue: expected ci-triage.py JSON on stdin", file=sys.stderr)
        sys.exit(2)

    queue = build_queue(payload)
    print(json.dumps({"generated_at": NOW.isoformat(),
                      "repos_scanned": payload.get("repos_scanned"),
                      "queue": queue}, indent=2))

    if not args.quiet:
        order = ["fix", "rerun", "escalate", "skip"]
        print(f"\n{len(queue)} broken workflows", file=sys.stderr)
        for act in order:
            items = [q for q in queue if q["action"] == act]
            if not items:
                continue
            print(f"\n{act.upper()} ({len(items)})", file=sys.stderr)
            for q in items:
                print(f"  {q['signature']}  {q['repo']} / {q['workflow']}"
                      f"\n      {q['why']}  --  {q['reason']}", file=sys.stderr)


if __name__ == "__main__":
    main()
