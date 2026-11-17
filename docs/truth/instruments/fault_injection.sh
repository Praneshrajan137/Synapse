#!/usr/bin/env bash
# Session-2 instrument: introduce one fault at a time into the decision core and record which
# tests notice. Nothing in the repository is touched: each case is a fresh `git archive` of the
# commit under study in a scratch folder, patched there with one sed expression, tested there,
# and left for inspection. A case whose patch did not apply is reported as PATCH-FAILED and not
# tested, so a silent no-op cannot pass for a surviving fault.
#
# Usage: bash fault_injection.sh <repo> <commit> <python> <scratch-dir> <results-file>
#
# The selection is the CI fast run's for the two packages that hold the decision core
# (`-m "not slow"`), plus every test file under tests/uplift and tests/verify that names the
# faulted symbols. The same selection is used for every case, so the cases compare.
# `orchestrator/tests/test_internal_only_routes.py` is ignored: it imports `jose`, which the
# project's .venv on this laptop lacks, and it does not touch the faulted code.
set -u
REPO=$1
COMMIT=$2
PY=$3
WORK=$4
OUT=$5
mkdir -p "$WORK"
: > "$OUT"

NAMES=()
FILES=()
EXPRS=()
CHECKS=()
add() { NAMES+=("$1"); FILES+=("$2"); EXPRS+=("$3"); CHECKS+=("$4"); }

# name | file | sed expression (line-anchored) | regex proving the patch applied
add baseline - - -
add F1-confidence-floor-never-fails orchestrator/guardrails/rules.py \
  '460s/if decision.confidence < threshold:/if False:/' '^        if False:$'
add F2-fast-path-binds-the-lowest-score orchestrator/consensus/protocol.py \
  '654s/fast_best = max(proposals/fast_best = min(proposals/' 'fast_best = min\(proposals'
add F3-sentinel-review-period-tripled agents/inventory_sentinel/inference/request_state.py \
  '53s/REVIEW_PERIOD_MIN: Final\[float\] = 60.0/REVIEW_PERIOD_MIN: Final[float] = 180.0/' \
  'REVIEW_PERIOD_MIN: Final\[float\] = 180\.0'
add F4-nothing-is-executed orchestrator/consensus/protocol.py \
  '1568s/for proposal in decision.proposals:/for proposal in decision.proposals[:0]:/' \
  'for proposal in decision\.proposals\[:0\]:'
add F5-guardrail-failure-dispatches-anyway orchestrator/consensus/protocol.py \
  '889s/if not passed or twin_veto:/if False:/' '^        if False:$'

PATTERN='request_state|REVIEW_PERIOD_MIN|forecast_from_request|_fast_path|fast_best|_phase_execute|_ratify_and_dispatch|confidence_floor'

for i in "${!NAMES[@]}"; do
  name=${NAMES[$i]}
  file=${FILES[$i]}
  case_dir="$WORK/case"
  rm -rf "$case_dir"
  mkdir -p "$case_dir"
  git -C "$REPO" archive "$COMMIT" | tar -x -C "$case_dir"
  cd "$case_dir" || exit 2
  if [ "$file" != "-" ]; then
    sed -i "${EXPRS[$i]}" "$file"
    if ! grep -qE "${CHECKS[$i]}" "$file"; then
      echo "$name PATCH-FAILED (no line matched ${CHECKS[$i]} in $file)" >> "$OUT"
      continue
    fi
  fi
  extra=$(grep -rlE "$PATTERN" tests/uplift tests/verify --include='test_*.py' | sort | tr '\n' ' ')
  start=$(date +%s)
  PYTHONPATH="$case_dir;$case_dir/packages" PYTHONDONTWRITEBYTECODE=1 HYPOTHESIS_PROFILE=dev \
    timeout 1500 "$PY" -m pytest orchestrator/tests agents/inventory_sentinel/tests $extra \
    -m "not slow" -q -rfE --tb=no -p no:cacheprovider -o addopts="" \
    --ignore=orchestrator/tests/test_internal_only_routes.py > "$WORK/$name.log" 2>&1
  code=$?
  summary=$(grep -E "(passed|failed|error)" "$WORK/$name.log" | tail -1)
  echo "$name exit=$code seconds=$(( $(date +%s) - start )) extra_files=$(echo "$extra" | wc -w) :: $summary" >> "$OUT"
  grep -E '^(FAILED|ERROR)' "$WORK/$name.log" | cut -c1-220 | head -12 | sed 's/^/    /' >> "$OUT"
done
echo "done" >> "$OUT"
