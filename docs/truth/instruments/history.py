"""Where the effort went: added lines per month per class of path. Read-only (git log).

Usage: python history.py <repo_root> <rev>
"""
from __future__ import annotations

import collections
import subprocess
import sys

root, rev = sys.argv[1], sys.argv[2]


def classify(path: str) -> str:
    p = path
    if p.startswith(("uplift/", "tests/uplift/", "tests/verify/")):
        return "proof-harness"
    if p.startswith(("scripts/audit/", "infrastructure/quality/", "docs/state/", ".github/", ".pre-commit")):
        return "gates-ci"
    if p.startswith((".kiro/", "docs/", ".claude/")) or p in {"CLAUDE.md", "README.md", "HANDOFF.md", "AGENTS.md"} \
            or p.startswith(".agents/"):
        return "docs-specs"
    if p.startswith("frontend/"):
        if "pnpm-lock" in p or "package-lock" in p:
            return "lockfiles"
        if "/tests/" in p or ".test." in p or ".spec." in p or p.startswith("frontend/spec/"):
            return "frontend-tests"
        return "frontend-src"
    if p.startswith("design-system/"):
        return "frontend-src" if "/dist/" not in p and "lock" not in p else "lockfiles"
    if p.startswith(("agents/", "orchestrator/", "digital_twin/", "api/", "packages/", "data_fabric/", "ml_pipelines/")):
        if "/tests/" in p or p.rsplit("/", 1)[-1].startswith("test_"):
            return "product-tests"
        return "product-src"
    if p.startswith("tests/"):
        return "product-tests"
    if p.startswith(("infrastructure/", "docker/", "docker-compose")) or p in {"Makefile"}:
        return "infra-deploy"
    if p.startswith("scripts/"):
        return "scripts-other"
    if "lock" in p or p == "constraints.txt":
        return "lockfiles"
    return "other"


out = subprocess.run(
    ["git", "-C", root, "log", rev, "--no-merges", "--numstat", "--date=format:%Y-%m",
     "--format=@@%H|%ad|%s"],
    capture_output=True, check=True,
).stdout.decode("utf-8", "replace")

month_class_add: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
month_commits: collections.Counter[str] = collections.Counter()
prefix: collections.Counter[str] = collections.Counter()
commit_classes: dict[str, set[str]] = {}
cur_month = ""
cur = ""
touch_product = 0
touch_only_meta = 0
n_commits = 0
for line in out.splitlines():
    if line.startswith("@@"):
        if cur:
            cls = commit_classes[cur]
            if cls & {"product-src", "frontend-src"}:
                touch_product += 1
            elif cls and cls <= {"proof-harness", "gates-ci", "docs-specs", "lockfiles", "other", "scripts-other",
                                 "product-tests", "frontend-tests", "infra-deploy"}:
                touch_only_meta += 1
        h, m, s = line[2:].split("|", 2)
        cur, cur_month = h, m
        commit_classes[cur] = set()
        month_commits[m] += 1
        n_commits += 1
        prefix[s.split("(")[0].split(":")[0].strip().lower()[:12]] += 1
        continue
    parts = line.split("\t")
    if len(parts) != 3:
        continue
    a, _d, path = parts
    if a == "-":
        continue
    c = classify(path)
    month_class_add[cur_month][c] += int(a)
    commit_classes[cur].add(c)
if cur:
    cls = commit_classes[cur]
    if cls & {"product-src", "frontend-src"}:
        touch_product += 1
    else:
        touch_only_meta += 1

classes = ["product-src", "product-tests", "frontend-src", "frontend-tests", "proof-harness", "gates-ci",
           "docs-specs", "infra-deploy", "scripts-other", "lockfiles", "other"]
print(f"rev={rev} non-merge commits={n_commits}")
print("month    commits " + " ".join(c[:13].rjust(14) for c in classes))
tot = collections.Counter()
for m in sorted(month_class_add):
    c = month_class_add[m]
    tot.update(c)
    print(f"{m}  {month_commits[m]:6}  " + " ".join(str(c[k]).rjust(14) for k in classes))
print("TOTAL    " + f"{n_commits:6}  " + " ".join(str(tot[k]).rjust(14) for k in classes))
s = sum(tot[k] for k in classes if k != "lockfiles")
print("SHARE (excl lockfiles): " + ", ".join(f"{k}={100 * tot[k] / s:.1f}%" for k in classes if k != "lockfiles"))
print(f"commits touching product-src or frontend-src: {touch_product} of {n_commits}")
print(f"commits touching neither: {n_commits - touch_product}")
print("subject prefixes:", prefix.most_common(12))
