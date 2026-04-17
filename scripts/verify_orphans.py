"""Grep-verify suspected orphans against the actual codebase using git grep."""
import json
import subprocess
from pathlib import Path
from collections import defaultdict

REPO = Path("/Users/jay/Developer/claude-code-agent")
GRAPH = REPO / "graphify" / "graph.json"

g = json.loads(GRAPH.read_text())
AUG = REPO / "graphify" / "graph.augmented.json"
if AUG.exists():
    aug = json.loads(AUG.read_text())
    g["nodes"].extend(aug["nodes"])
    g["links"].extend(aug["links"])
nodes = {n["id"]: n for n in g["nodes"]}
links = g["links"]

USE_RELATIONS = {
    "imports_from", "calls", "implements", "extends", "instantiates",
    "uses", "references", "decorated_by", "raises", "returns",
}
inbound = defaultdict(set)
for e in links:
    if e.get("confidence") != "EXTRACTED":
        continue
    if e.get("relation") not in USE_RELATIONS:
        continue
    inbound[e["target"]].add(e["source"])

ENTRY_PREFIXES = (
    "main_", "app_main", "conftest", "cli_", "settings",
    "__init__", "vite_config", "tailwind_config", "pyproject", "package_json",
)
def is_entry_or_skip(node):
    src = node.get("source_file", "") or ""
    nid = node["id"]
    if "/tests/" in src or src.endswith("_test.py") or ".test." in src:
        return True
    if "__tests__" in src or "/e2e/" in src:
        return True
    if any(nid.startswith(p) for p in ENTRY_PREFIXES):
        return True
    if src.endswith("/main.py") or src.endswith("/__init__.py"):
        return True
    if "/migrations/" in src or src.endswith(".md") or src.endswith(".json"):
        return True
    if src.endswith(".yaml") or src.endswith(".yml") or src.endswith(".html"):
        return True
    if src.endswith(".css") or src.endswith(".svg"):
        return True
    return False

orphan_symbols = []
for nid, n in nodes.items():
    if n.get("file_type") != "code":
        continue
    if is_entry_or_skip(n):
        continue
    if inbound[nid]:
        continue
    if "_" not in nid:
        continue
    label = n.get("label", "")
    if len(label) < 5 or label.lower() in {"main", "init", "test", "name"}:
        continue
    orphan_symbols.append(n)

import random
random.seed(42)
backend_orphans = [n for n in orphan_symbols if (n.get("source_file") or "").startswith("backend/")]
frontend_orphans = [n for n in orphan_symbols if (n.get("source_file") or "").startswith("frontend/")]

sample = random.sample(backend_orphans, min(60, len(backend_orphans))) + random.sample(frontend_orphans, min(40, len(frontend_orphans)))

print(f"Total orphan symbols: {len(orphan_symbols)} ({len(backend_orphans)} backend, {len(frontend_orphans)} frontend)")
print(f"Checking {len(sample)} sampled orphans against git grep...")
print()

import re
def clean_label(lab):
    """Strip method-marker dot and call parens; return bare identifier."""
    s = lab.strip()
    if s.startswith("."):
        s = s[1:]
    if s.endswith("()"):
        s = s[:-2]
    # Drop anything past first dot/paren/space (defensive)
    m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", s)
    return m.group(0) if m else s

truly_dead = []
live = []
for n in sample:
    raw_label = n["label"]
    label = clean_label(raw_label)
    if not label or len(label) < 4:
        continue
    src = n["source_file"]
    src_basename = src.split("/")[-1]
    # git grep -l: list files matching the symbol; -w: word boundary
    res = subprocess.run(
        ["git", "grep", "-lw", label],
        capture_output=True, text=True, cwd=str(REPO),
    )
    files = [f for f in res.stdout.splitlines() if f != src and not f.endswith(f"/{src_basename}")]
    # Filter test files (definition might appear in tests but real "use" needs prod ref)
    prod_refs = [f for f in files if "/tests/" not in f and "__tests__" not in f
                 and not f.endswith(".md") and not f.endswith(".json")
                 and not f.endswith(".yaml") and not f.endswith(".yml")]
    if prod_refs:
        live.append((n, prod_refs[:2]))
    else:
        truly_dead.append((n, files[:2]))  # may have test-only refs

print(f"=== Truly dead (no prod-code reference): {len(truly_dead)} / {len(sample)} ===")
for n, refs in truly_dead[:30]:
    extra = f" (test-only refs: {len(refs)})" if refs else ""
    print(f"  {n['label']:40s}  {n['source_file']}:{n.get('source_location') or ''}{extra}")

print(f"\n=== False-positive orphans (graph missed prod-code reference): {len(live)} / {len(sample)} ===")
for n, files in live[:10]:
    print(f"  {n['label']:40s}  defined: {n['source_file']}")
    for f in files:
        print(f"    used in: {f}")

# Compute false-positive rate
total = len(sample)
fp_rate = len(live) / total * 100
print(f"\n=== Summary ===")
print(f"  Sample size: {total}")
print(f"  Truly dead: {len(truly_dead)} ({100 - fp_rate:.1f}%)")
print(f"  False positives (graph extraction misses): {len(live)} ({fp_rate:.1f}%)")
