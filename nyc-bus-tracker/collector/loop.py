#!/usr/bin/env python3
"""
Collector loop for .github/workflows/bus-tracker-collect.yml.

Why a loop: GitHub's scheduler drops and delays cron runs, and from Oct. 1,
2026 it fired only 3 to 5 of the 34 runs a day the old design needed, so most
hours went uncollected while every run that did start reported success. This
script keeps ONE long-lived job running instead. It collects a burst at :09
and :39 past every hour from 6 a.m. to 10:59 p.m. Eastern, pushes each burst
to the bus-data branch, and shortly before the job's time limit it starts its
own successor through workflow_dispatch. Cron runs are only a backstop that
restarts the chain if it ever breaks.

Single writer: the workflow's first step exits early when an older collector
run is already live (the run that dispatched this one is exempt, by run id),
before anything is checked out.

Usage (inside the workflow, from the repo root):
  python3 nyc-bus-tracker/collector/loop.py            # loop mode
  python3 nyc-bus-tracker/collector/loop.py --once     # one burst now, no successor
Env: GH_TOKEN, REPO, GITHUB_RUN_ID, MTA_API_KEY; optional RUN_BUDGET_MIN (default 330), FORCE (collect outside the window, --once only).
"""
import base64, datetime as dt, glob, json, os, subprocess, sys, time
import urllib.error, urllib.request
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
SLOT_MINUTES = (9, 39)
FIRST_HOUR, LAST_HOUR = 6, 22          # bursts start 6:09 through 22:39 ET
BURST_ITERATIONS, BURST_SLEEP_S = 12, 30
BURST_COST_S = 10 * 60                 # a burst plus its push, with margin
WORKFLOW = 'bus-tracker-collect.yml'
SNAP_ROOT = 'nyc-bus-tracker/data/snapshots'

REPO = os.environ['REPO']
TOKEN = os.environ['GH_TOKEN']
RUN_ID = int(os.environ.get('GITHUB_RUN_ID', '0'))
BUDGET_S = int(os.environ.get('RUN_BUDGET_MIN', '330')) * 60
API = f'https://api.github.com/repos/{REPO}'
START = time.time()

known_oid = {}   # path -> blob id we last saw on bus-data (pulled or pushed)


def log(msg):
    print(f'[{dt.datetime.now(ET):%H:%M:%S} ET] {msg}', flush=True)


def api(method, path, body=None, tries=4):
    data = json.dumps(body).encode() if body is not None else None
    for i in range(tries):
        req = urllib.request.Request(API + path, data=data, method=method)
        req.add_header('Authorization', f'Bearer {TOKEN}')
        req.add_header('Accept', 'application/vnd.github+json')
        if data:
            req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code in (409, 422) or e.code < 500 or i == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
        time.sleep(5 * (i + 1))


def git(*args, check=False):
    r = subprocess.run(['git', *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f'git {" ".join(args)}: {r.stderr.strip()}')
    return r


# ── timing ──────────────────────────────────────────────────────────────────
def next_slot(now):
    """Next burst start (ET) at or after now, inside the collection window."""
    day = now.replace(second=0, microsecond=0)
    for add_days in range(3):
        d = (day + dt.timedelta(days=add_days)).date()
        for h in range(FIRST_HOUR, LAST_HOUR + 1):
            for m in SLOT_MINUTES:
                t = dt.datetime(d.year, d.month, d.day, h, m, tzinfo=ET)
                if t >= now - dt.timedelta(seconds=60):
                    return t
    raise RuntimeError('no slot found')


def sleep_until(t):
    while True:
        left = (t - dt.datetime.now(ET)).total_seconds()
        if left <= 0:
            return
        time.sleep(min(left, 300))


def budget_left():
    return BUDGET_S - (time.time() - START)


# ── bus-data sync ───────────────────────────────────────────────────────────
def fetch_bus_data():
    git('fetch', '--filter=blob:none', '--no-tags', 'origin', 'bus-data', '--depth=1', check=True)


def remote_oid(path):
    r = git('rev-parse', f'origin/bus-data:{path}')
    return r.stdout.strip() if r.returncode == 0 else None


def pull_day(date):
    """Materialize one ET day's folder from bus-data (once per run per day)."""
    folder = f'{SNAP_ROOT}/{date}'
    if os.path.isdir(folder):
        return
    fetch_bus_data()
    os.makedirs(folder, exist_ok=True)
    if git('checkout', 'origin/bus-data', '--', f'{folder}/').returncode == 0:
        log(f'pulled {folder} from bus-data')
    git('reset', '-q', '--', SNAP_ROOT)
    for f in glob.glob(f'{folder}/*.jsonl'):
        known_oid[f] = remote_oid(f)


def merge_remote(path, oid):
    """Another writer changed this hour file: union its lines with ours."""
    remote = git('cat-file', '-p', oid, check=True).stdout.splitlines()
    with open(path) as fh:
        local = fh.read().splitlines()
    seen, merged = set(), []
    for line in remote + local:
        if not line.strip():
            continue
        try:
            ts = json.loads(line)['ts']
        except (ValueError, KeyError):
            continue
        if ts in seen:
            continue
        seen.add(ts)
        merged.append((ts, line))
    merged.sort()
    with open(path, 'w') as fh:
        fh.write('\n'.join(line for _, line in merged) + '\n')
    log(f'merged {len(remote)} remote line(s) into {path}')


def push_day(date):
    """Commit changed hour files to bus-data server-side (Git Data API).
    Nothing is downloaded, so cost stays flat however large the archive gets."""
    files = sorted(glob.glob(f'{SNAP_ROOT}/{date}/*.jsonl'))
    if not files:
        log('nothing to push')
        return
    for attempt in range(5):
        fetch_bus_data()
        for f in files:
            r_oid = remote_oid(f)
            if r_oid and r_oid != known_oid.get(f) and r_oid != git('hash-object', f).stdout.strip():
                merge_remote(f, r_oid)
                known_oid[f] = r_oid
        tip = api('GET', '/git/ref/heads/bus-data')['object']['sha']
        base_tree = api('GET', f'/git/commits/{tip}')['tree']['sha']
        entries, new_oids = [], {}
        for f in files:
            local = git('hash-object', f).stdout.strip()
            if local == remote_oid(f):
                continue
            with open(f, 'rb') as fh:
                content = base64.b64encode(fh.read()).decode()
            sha = api('POST', '/git/blobs', {'content': content, 'encoding': 'base64'})['sha']
            entries.append({'path': f, 'mode': '100644', 'type': 'blob', 'sha': sha})
            new_oids[f] = sha
        if not entries:
            log('bus-data already up to date')
            return
        tree = api('POST', '/git/trees', {'base_tree': base_tree, 'tree': entries})['sha']
        stamp = dt.datetime.now(ET).strftime('%Y-%m-%d %H:%M')
        commit = api('POST', '/git/commits', {'message': f'Bus data: {stamp} ET', 'tree': tree, 'parents': [tip]})['sha']
        try:
            api('PATCH', '/git/refs/heads/bus-data', {'sha': commit, 'force': False})
        except urllib.error.HTTPError as e:
            if e.code in (409, 422):
                log('bus-data moved under us; retrying')
                time.sleep(3)
                continue
            raise
        known_oid.update(new_oids)
        log(f'bus-data -> {commit[:10]} ({len(entries)} file(s))')
        return
    raise RuntimeError('could not update bus-data after retries')


# ── collection ──────────────────────────────────────────────────────────────
def burst():
    ok = 0
    for i in range(BURST_ITERATIONS):
        r = subprocess.run(['node', 'nyc-bus-tracker/collector/collect.js'], capture_output=True, text=True)
        if r.returncode == 0:
            ok += 1
        else:
            print(f'::warning::collect.js failed: {(r.stderr or r.stdout).strip()[:300]}', flush=True)
        if i < BURST_ITERATIONS - 1:
            time.sleep(BURST_SLEEP_S)
    return ok


def collect_and_push():
    date = dt.datetime.now(ET).strftime('%Y-%m-%d')
    pull_day(date)
    ok = burst()
    log(f'burst done: {ok}/{BURST_ITERATIONS} snapshots')
    if ok:
        push_day(date)
    return ok


def dispatch_successor():
    api('POST', f'/actions/workflows/{WORKFLOW}/dispatches',
        {'ref': 'main', 'inputs': {'predecessor': str(RUN_ID)}})
    log('successor dispatched')


def main():
    if '--once' in sys.argv:
        now = dt.datetime.now(ET)
        if not (FIRST_HOUR <= now.hour <= LAST_HOUR) and not os.environ.get('FORCE'):
            log('outside the collection window; nothing to do (set FORCE=1 to override)')
            return 0
        return 0 if collect_and_push() else 1

    failures = 0
    try:
        while True:
            slot = next_slot(dt.datetime.now(ET))
            wait = (slot - dt.datetime.now(ET)).total_seconds()
            if wait + BURST_COST_S > budget_left():
                # The next burst would not finish in time. Sleep out most of the
                # budget (overnight this is the idle stretch), then hand off.
                idle = max(0, min(wait - 600, budget_left() - 120))
                log(f'next slot {slot:%a %H:%M} is beyond this run; handing off in {idle / 60:.0f} min')
                time.sleep(idle)
                break
            log(f'next burst at {slot:%a %H:%M} ET')
            sleep_until(slot)
            ok = collect_and_push()
            if slot.hour == FIRST_HOUR and slot.minute == SLOT_MINUTES[0]:
                # Yesterday is complete: start the daily processor now rather
                # than waiting on GitHub's cron.
                try:
                    api('POST', '/actions/workflows/bus-tracker-process-daily.yml/dispatches', {'ref': 'main'})
                    log('daily processor dispatched')
                except Exception as e:
                    print(f'::warning::could not dispatch the daily processor: {e}', flush=True)
            failures = 0 if ok else failures + 1
            if failures >= 3:
                print('::error::three bursts in a row collected nothing', flush=True)
                break
    finally:
        dispatch_successor()
    return 1 if failures >= 3 else 0


if __name__ == '__main__':
    sys.exit(main())
