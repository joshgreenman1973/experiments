# Moving to a new machine, or adding a second one

The full guide lives in the private repo `joshgreenman1973/claude-config`,
at `~/.claude/NEW-MAC.md` once cloned. It covers replacing this Mac and
adding a second Mac alongside it, and it sits next to a weekly snapshot of
what each Mac has (`~/.claude/machines/<mac>/SNAPSHOT.md`).

It's kept there rather than here because this repo is public and the guide
lists apps, recurring jobs and the names of stored credentials.

To get to it on a fresh Mac, after `gh auth login` as `joshgreenman1973`:

```bash
git clone https://joshgreenman1973@github.com/joshgreenman1973/claude-config.git ~/.claude
```

The two tools in this repo that the guide uses:

- `scripts/sync-audit.py --fetch` finds work that exists only on this
  machine (runs every Monday at 9am via `com.josh.sync-audit`).
- `scripts/restore-clones.py --clone` clones every nested project repo
  back into place, reading `machine/repos.json` and the copy in
  `~/.claude/machine-kit/repos.json`.

Copies of the recurring jobs are in `machine/launchagents/` here and in
`~/.claude/machine-kit/launchagents/`. Files ending `.retired`,
`.superseded` or `.superseded-by-action` are history; skip them.
