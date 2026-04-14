#!/usr/bin/env python3
from __future__ import annotations

"""Run all chaos engineering tests and produce a summary report."""

import subprocess
import sys
from datetime import UTC, datetime

CHAOS_TESTS = [
    ("GNN Nonsensical Spike", "tests/chaos/test_gnn_spike.py"),
    ("LLM Hallucination", "tests/chaos/test_llm_hallucination.py"),
    ("Agent Deadlock", "tests/chaos/test_deadlock.py"),
    ("Digital Twin Drift", "tests/chaos/test_twin_drift.py"),
    ("Supplier Trust Bias", "tests/chaos/test_supplier_bias.py"),
    ("RL Policy Instability", "tests/chaos/test_rl_instability.py"),
    ("Kafka Partition Failure", "tests/chaos/test_kafka_failure.py"),
    ("Ollama Crash / OOM", "tests/chaos/test_ollama_crash.py"),
    ("GPU OOM Training", "tests/chaos/test_gpu_oom.py"),
]


def main() -> int:
    results: list[dict[str, object]] = []
    all_passed = True

    print("=" * 70)
    print("SYNAPSE Chaos Engineering Test Suite")
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")
    print("=" * 70)

    for name, path in CHAOS_TESTS:
        print(f"\n--- {name} ({path}) ---")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", path, "-v", "--tb=short"],
            capture_output=True,
            text=True,
        )
        passed = proc.returncode == 0
        results.append({"test": name, "path": path, "passed": passed})
        if not passed:
            all_passed = False
            print("  FAILED")
            tail_stdout = "\n".join(proc.stdout.splitlines()[-30:])
            tail_stderr = "\n".join(proc.stderr.splitlines()[-15:])
            if tail_stdout.strip():
                print(tail_stdout)
            if tail_stderr.strip():
                print(tail_stderr)
        else:
            print("  PASSED")

    print("\n" + "=" * 70)
    print("CHAOS TEST SUMMARY")
    print("=" * 70)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['test']}")

    passed_count = sum(1 for r in results if r["passed"])
    print(f"\n  {passed_count}/{len(results)} chaos tests passed")

    if not all_passed:
        print("\n  SPRINT 5 QUALITY GATE: FAILED — Fix failing chaos tests before proceeding")
        return 1

    print("\n  SPRINT 5 QUALITY GATE: CHAOS ENGINEERING PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
