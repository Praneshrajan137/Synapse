#!/usr/bin/env bash
# Retire all .claude/worktrees/ directories and their tracking branches.
#
# SAFETY: every branch listed here is first verified to have a corresponding
# archive/<name>-<sha> tag in the local repo. If a tag is missing, the script
# refuses to delete that branch.
#
# Usage:
#   bash scripts/retire_worktrees.sh             # dry-run (default)
#   bash scripts/retire_worktrees.sh --apply     # actually delete
#
# This script MUST be run from a working copy that is NOT inside .claude/worktrees/.
# Recommended: run from the main checkout at the repo root.

set -euo pipefail

APPLY=0
if [ "${1:-}" = "--apply" ]; then
    APPLY=1
fi

repo_root="$(git rev-parse --show-toplevel)"
case "$repo_root" in
    *".claude/worktrees/"*)
        echo "ERROR: refusing to run from inside .claude/worktrees/." >&2
        echo "       cd to the main checkout (repo root) first." >&2
        exit 2
        ;;
esac

cd "$repo_root"

echo "== Active worktrees =="
git worktree list

echo
echo "== Branches with archive tag (safe to retire) =="
mapfile -t worktree_paths < <(git worktree list --porcelain | awk '/^worktree / && $2 ~ /\.claude\/worktrees\// {print $2}')

for wt in "${worktree_paths[@]}"; do
    branch=$(git -C "$wt" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    if [ -z "$branch" ] || [ "$branch" = "HEAD" ]; then
        echo "  SKIP  $wt — detached or unreadable"
        continue
    fi
    short=$(echo "$branch" | sed 's|^claude/||')
    # Match archive/<short-without-trailing-hash>-<any-sha>
    archive_root=$(echo "$short" | sed 's/-[a-f0-9]\{6,8\}$//')
    if git tag --list "archive/${archive_root}-*" | head -1 | grep -q .; then
        if [ "$APPLY" = "1" ]; then
            echo "  RETIRE $wt (branch $branch)"
            git worktree remove --force "$wt"
            git branch -D "$branch" 2>/dev/null || true
        else
            echo "  DRY    $wt (branch $branch) — would remove worktree + delete branch"
        fi
    else
        echo "  SKIP  $wt — no archive/${archive_root}-* tag; refusing to delete"
    fi
done

if [ "$APPLY" = "1" ]; then
    git worktree prune
    echo
    echo "Done. Pushing archive tags to origin:"
    git push origin --tags
else
    echo
    echo "Dry run only. Re-run with --apply to execute the deletion."
fi
