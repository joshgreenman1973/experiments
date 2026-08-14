# Moving to a new machine

Everything you need to make a Mac-to-Mac move without losing work. Last
verified August 14, 2026. The tooling that keeps this honest lives in
`scripts/sync-audit.py` (finds work that exists only on this machine) and
`scripts/restore-clones.py` (puts every project back on a fresh machine).

## How the projects are organized

- **`~/Experiments` is a monorepo** pushed to
  `joshgreenman1973/experiments`. About 77 projects are tracked directly
  inside it.
- **~115 more projects are nested git repos** inside `~/Experiments`, each
  with its own GitHub remote under one of three owners: `joshgreenman1973`,
  `vitalcity-nyc` or the `Vital-City-NYC` org. The parent repo ignores
  them; `machine/repos.json` (committed here) is the full inventory of
  which folder maps to which remote.
- **A few project directories live outside `~/Experiments`** and are listed
  in the `external` section of `machine/repos.json`:
  `~/personal-dashboard`, `~/streetlightmeter-api`, `~/Debrief` and
  `~/.claude` (Claude Code memory, settings and scheduled tasks).

## Before leaving the old machine

1. Run the audit and fix what it finds:

   ```bash
   python3 ~/Experiments/scripts/sync-audit.py --fetch
   ```

   Anything under "WOULD LOSE WORK IF THIS MACHINE DIED" exists only on
   that machine. Commit and push it, or accept losing it.
2. Commit `machine/repos.json` if it changed (the audit regenerates it).
3. Copy the things git cannot carry (see the list below).

## Setting up the new machine

1. Install the basics: Xcode command line tools (`xcode-select --install`),
   [GitHub CLI](https://cli.github.com) (`brew install gh`), Node and the
   Claude Code desktop app.
2. Sign in to both GitHub accounts (each opens a browser login):

   ```bash
   gh auth login   # once as joshgreenman1973, once as vitalcity-nyc
   ```

3. Clone the monorepo and restore every nested repo:

   ```bash
   git clone https://github.com/joshgreenman1973/experiments.git ~/Experiments
   cd ~/Experiments
   python3 scripts/restore-clones.py --clone
   ```

4. Copy `~/.claude` from the old machine (or its backup). This carries
   Claude Code memory, settings and scheduled tasks. Without it, Claude
   starts from scratch.
5. Reinstall the recurring local jobs (versioned in `machine/launchagents/`;
   files ending `.retired` or `.superseded-by-action` are inactive history —
   skip them):

   ```bash
   cp ~/Experiments/machine/launchagents/com.josh.joshgreenman-site-refresh.plist ~/Experiments/machine/launchagents/com.joshgreenman.mamdani-captions.plist ~/Experiments/machine/launchagents/com.vitalcity.weekly-report.plist ~/Experiments/machine/launchagents/com.josh.sync-audit.plist ~/Library/LaunchAgents/ && for f in com.josh.joshgreenman-site-refresh com.joshgreenman.mamdani-captions com.vitalcity.weekly-report com.josh.sync-audit; do launchctl load -w ~/Library/LaunchAgents/$f.plist; done
   ```

6. Re-create the Keychain items scripts depend on (values come from the
   old machine's Keychain or from console.anthropic.com — never from a
   file in a repo):
   - `ANTHROPIC_API_KEY` (account `anthropic`) — used by the
     family-dinner-prices scan and anything else calling the Anthropic
     application programming interface directly.
   - `vc-network-pass` — the Vital City dashboard passphrase read by the
     weekly growth report.

7. Run the audit once to confirm the new machine sees everything:

   ```bash
   python3 ~/Experiments/scripts/sync-audit.py --fetch
   ```

## Things git cannot carry — copy these by hand

- `~/.claude` — Claude Code memory, settings, scheduled tasks. The single
  most important non-git item.
- `~/Debrief` — meeting library (642 imported meetings), not in git.
- `~/personal-dashboard` — not in git.
- `~/streetlightmeter-api` — not in git (check whether the deployed copy
  is the source of truth before assuming loss).
- Keychain items listed above.
- Any repo the audit flags `NO-REMOTE` — it exists nowhere but that disk.

## Keeping this current

- The `com.josh.sync-audit` job runs `sync-audit.py --fetch` every Monday
  at 9:00am and rewrites `sync-report.json` and `machine/repos.json`. If
  `machine/repos.json` changes, commit it — that file is what makes
  `restore-clones.py` complete.
- When a project starts life outside `~/Experiments`, add its path to the
  `EXTERNAL` list at the top of `scripts/sync-audit.py`.
- When an iOS or other local-only project matters (anything on TestFlight
  counts), give it a GitHub remote the day it starts. The audit will keep
  flagging it until it has one.
