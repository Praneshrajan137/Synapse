#!/usr/bin/env python3
"""SYNAPSE Ollama Verification — ensure required models are pulled and responsive."""
from __future__ import annotations

import json
import sys
import urllib.request

OLLAMA_BASE = "http://localhost:11434"

REQUIRED_MODELS = [
    {"name": "phi3:mini", "tier": "Tier 2", "priority": 1},
    {"name": "qwen2.5:7b", "tier": "Tier 2", "priority": 2},
]

OPTIONAL_MODELS = [
    {"name": "deepseek-r1:14b", "tier": "Tier 3", "priority": 3},
    {"name": "llama3.3:70b-instruct-q4_K_M", "tier": "Tier 3-4", "priority": 4},
]


def check_ollama_health() -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Ollama not reachable: {e}")
        return False


def get_installed_models() -> list[str]:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def test_model_inference(model_name: str) -> bool:
    try:
        payload = json.dumps({
            "model": model_name,
            "prompt": "Respond with exactly: SYNAPSE_OK",
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            f"{OLLAMA_BASE}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return "response" in data
    except Exception as e:
        print(f"  Inference failed for {model_name}: {e}")
        return False


def main() -> None:
    print("SYNAPSE Ollama Model Verification")
    print()

    if not check_ollama_health():
        print("Ollama is not running. Start with: ollama serve")
        sys.exit(1)

    installed = get_installed_models()
    print(f"Installed models: {len(installed)}")

    all_pass = True
    for model_info in REQUIRED_MODELS:
        name = model_info["name"]
        tier = model_info["tier"]
        found = any(name in m for m in installed)
        if found:
            print(f"  OK {name} ({tier}) — installed")
            if test_model_inference(name):
                print("    OK Inference OK")
            else:
                print("    FAIL Inference FAILED")
                all_pass = False
        else:
            print(f"  MISSING {name} ({tier}) — NOT INSTALLED")
            print(f"    Run: ollama pull {name}")
            all_pass = False

    print()
    for model_info in OPTIONAL_MODELS:
        name = model_info["name"]
        tier = model_info["tier"]
        found = any(name in m for m in installed)
        status = "installed" if found else "not installed (optional)"
        print(f"  {'OK' if found else 'OPTIONAL'} {name} ({tier}) — {status}")

    print()
    if all_pass:
        print("All required models verified.")
    else:
        print("Some required models missing or failing.")
        sys.exit(1)


if __name__ == "__main__":
    main()
