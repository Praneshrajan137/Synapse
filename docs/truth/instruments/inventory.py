"""Whole-repository inventory for docs/truth (session 2). Read-only.

Usage: python inventory.py <repo_root>
Counts tracked files (git ls-files) by top-level area and by kind, with line counts.
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(sys.argv[1]).resolve()
files = subprocess.run(
    ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True
).stdout.decode("utf-8", "replace").split("\0")
files = [f for f in files if f]

TEXT_EXT = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".md", ".yaml", ".yml", ".json", ".toml",
    ".sql", ".cypher", ".sh", ".ps1", ".tf", ".css", ".html", ".txt", ".cfg", ".ini", ".conf",
    ".tpl", ".rego", ".proto", ".ipynb", ".svg", ".lock", ".mdx", ".hcl", ".env", ".example", "",
}


def kind(path: str) -> str:
    p = path.lower()
    name = p.rsplit("/", 1)[-1]
    ext = pathlib.PurePosixPath(p).suffix
    is_test = (
        "/tests/" in "/" + p or "/test/" in "/" + p or name.startswith("test_") or ".test." in name
        or ".spec." in name or "/e2e/" in p or "/__tests__/" in p
    )
    if name in {"pnpm-lock.yaml", "package-lock.json", "uv.lock", "constraints.txt"} or ext == ".lock":
        return "lockfile"
    if "/dist/" in "/" + p or p.startswith("design-system/color/dist"):
        return "generated"
    if ext == ".py":
        return "py-test" if is_test else "py-src"
    if ext in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
        return "ts-test" if is_test else "ts-src"
    if ext in {".md", ".mdx"}:
        return "markdown"
    if ext in {".yaml", ".yml"}:
        return "yaml"
    if ext == ".json":
        return "json"
    if ext in {".sql", ".cypher"}:
        return "sql"
    if ext in {".sh", ".ps1"}:
        return "shell"
    if ext in {".tf", ".hcl"}:
        return "terraform"
    if ext in {".css", ".html", ".svg"}:
        return "web-static"
    if ext == ".ipynb":
        return "notebook"
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".woff", ".woff2", ".ttf", ".ico", ".pdf", ".pt", ".pkl",
               ".parquet", ".onnx", ".bin", ".gz", ".zip", ".webp", ".db"}:
        return "binary"
    return "other"


def count_lines(path: pathlib.Path) -> tuple[int, int]:
    try:
        data = path.read_bytes()
    except OSError:
        return 0, 0
    if b"\0" in data[:4096]:
        return 0, len(data)
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0), len(data)


area_kind_lines: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
area_kind_files: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
area_bytes: collections.Counter[str] = collections.Counter()
big: list[tuple[int, str]] = []
for f in files:
    area = f.split("/", 1)[0] if "/" in f else "(root)"
    k = kind(f)
    n, b = count_lines(root / f)
    area_kind_lines[area][k] += n
    area_kind_files[area][k] += 1
    area_bytes[area] += b
    big.append((n, f))

kinds = ["py-src", "py-test", "ts-src", "ts-test", "markdown", "yaml", "json", "sql", "shell",
         "terraform", "web-static", "notebook", "generated", "lockfile", "binary", "other"]
tot_lines = collections.Counter()
tot_files = collections.Counter()
print(f"TRACKED FILES: {len(files)}")
hdr = "area".ljust(16) + "files".rjust(7) + "lines".rjust(9) + "  " + " ".join(k.rjust(10) for k in kinds[:11])
print(hdr)
for area in sorted(area_kind_lines, key=lambda a: -sum(area_kind_lines[a].values())):
    c = area_kind_lines[area]
    fc = area_kind_files[area]
    print(area.ljust(16)[:16] + str(sum(fc.values())).rjust(7) + str(sum(c.values())).rjust(9) + "  "
          + " ".join(str(c[k]).rjust(10) for k in kinds[:11]))
    tot_lines.update(c)
    tot_files.update(fc)
print("TOTAL LINES BY KIND:")
for k in kinds:
    print(f"  {k:12} files={tot_files[k]:6} lines={tot_lines[k]:9}")
print(f"  ALL          files={sum(tot_files.values()):6} lines={sum(tot_lines.values()):9}")

print("\nLARGEST 25 TEXT FILES (lines):")
for n, f in sorted(big, reverse=True)[:25]:
    print(f"  {n:7} {f}")

# Second-level breakdown for the big areas
print("\nSECOND-LEVEL (py-src / py-test / ts-src / ts-test / markdown lines):")
second: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
for f in files:
    parts = f.split("/")
    if len(parts) < 3:
        continue
    if parts[0] in {"agents", "orchestrator", "packages", "digital_twin", "data_fabric", "api", "frontend",
                    "infrastructure", "scripts", "tests", "uplift", "ml_pipelines", "docs", ".kiro",
                    ".github", ".claude", "design-system", "proto", "docker"}:
        key = parts[0] + "/" + parts[1]
        n, _ = count_lines(root / f)
        second[key][kind(f)] += n
        second[key]["_files"] += 1
for key in sorted(second):
    c = second[key]
    print(f"  {key:46} files={c['_files']:5} py={c['py-src']:7} pytest={c['py-test']:7} ts={c['ts-src']:7} "
          f"tstest={c['ts-test']:7} md={c['markdown']:7} yaml={c['yaml']:6} json={c['json']:7}")
