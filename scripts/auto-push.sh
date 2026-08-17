#!/usr/bin/env bash
# auto-push.sh -- push the current HEAD commit to origin/main unattended.
#
# Scheduled jobs in this repo kept failing on two recurring, unrelated snags:
#
#   1. `gh` serves credentials for the ACTIVE account only. When the active
#      account is vitalcity-nyc, every push to joshgreenman1973/experiments
#      dies with "Permission ... denied to vitalcity-nyc" (403). Setting
#      credential.<url>.username does NOT help -- gh's helper returns nothing
#      for a non-active user, so the push falls through to a password prompt.
#      The only fix is `gh auth switch`, which is global state, so we put it
#      back the way we found it before exiting.
#
#   2. The working tree here carries ~1,100 uncommitted files, and main is
#      routinely dozens of commits behind origin (other jobs push all day).
#      A plain rebase would have to check out files this tree has modified,
#      so it refuses. Cherry-picking HEAD onto origin/main inside a throwaway
#      worktree sidesteps the working tree completely.
#
# Usage:  scripts/auto-push.sh [commit-ish]     (defaults to HEAD)
# Exit:   0 on success or "already pushed"; non-zero on any real failure.

set -euo pipefail

COMMIT="${1:-HEAD}"
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

REMOTE_URL="$(git remote get-url origin)"
# github.com/<owner>/<repo> -> <owner>, for both https and ssh remotes.
OWNER="$(printf '%s\n' "$REMOTE_URL" | sed -E 's#^.*github\.com[:/]([^/]+)/.*$#\1#')"
[ -n "$OWNER" ] || { echo "auto-push: cannot parse owner from $REMOTE_URL" >&2; exit 1; }

SHA="$(git rev-parse "$COMMIT")"
PREV_ACCOUNT="$(gh auth status 2>/dev/null | awk '/Logged in to github.com account/{a=$NF=="(keyring)"?$(NF-1):$NF} /Active account: true/{print a; exit}')"

restore_account() {
  if [ -n "${PREV_ACCOUNT:-}" ] && [ "${PREV_ACCOUNT}" != "${OWNER}" ]; then
    gh auth switch --hostname github.com --user "$PREV_ACCOUNT" >/dev/null 2>&1 || true
  fi
}

WT=""
cleanup() {
  [ -n "$WT" ] && [ -d "$WT" ] && git worktree remove --force "$WT" >/dev/null 2>&1 || true
  git worktree prune >/dev/null 2>&1 || true
  restore_account
}
trap cleanup EXIT

# 1. Make sure the owning account is the one git will authenticate as.
if [ "${PREV_ACCOUNT:-}" != "$OWNER" ]; then
  echo "auto-push: active gh account is '${PREV_ACCOUNT:-none}', repo is owned by '$OWNER' -- switching"
  gh auth switch --hostname github.com --user "$OWNER" >/dev/null
fi

# 2. Replay the commit on top of whatever origin/main is right now.
git fetch -q origin main

if git merge-base --is-ancestor "$SHA" origin/main 2>/dev/null; then
  echo "auto-push: $(git rev-parse --short "$SHA") already on origin/main -- nothing to do"
  exit 0
fi

WT="$(mktemp -d "${TMPDIR:-/tmp}/auto-push-wt.XXXXXX")"
rm -rf "$WT"
git worktree add -q --detach "$WT" origin/main

if ! CP_OUT="$(git -C "$WT" cherry-pick "$SHA" 2>&1)"; then
  git -C "$WT" cherry-pick --abort >/dev/null 2>&1 || true
  # The commit gets a NEW sha every time it is replayed, so a re-run cannot
  # recognise its own earlier push by sha -- it shows up as an empty pick
  # instead. That means the content is already on origin/main: not an error.
  if printf '%s' "$CP_OUT" | grep -qiE 'empty|nothing to commit'; then
    echo "auto-push: content of $(git rev-parse --short "$SHA") already on origin/main -- nothing to do"
    exit 0
  fi
  echo "auto-push: cherry-pick of $(git rev-parse --short "$SHA") onto origin/main conflicted." >&2
  echo "auto-push: another job probably touched the same files -- re-run the job to rebuild from current data." >&2
  exit 1
fi

# 3. Push. A racing job may land first; refetch and retry once.
if ! git -C "$WT" push -q origin HEAD:main 2>/dev/null; then
  echo "auto-push: push rejected (origin moved) -- retrying once"
  git fetch -q origin main
  git -C "$WT" rebase -q origin/main || {
    echo "auto-push: rebase after race failed" >&2; exit 1; }
  git -C "$WT" push -q origin HEAD:main
fi

echo "auto-push: pushed $(git -C "$WT" rev-parse --short HEAD) to $OWNER/main"
