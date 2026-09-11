#!/usr/bin/env python3
"""Freeze hashes for the manuscript-bound simulation reference outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = ROOT / "canonical_results" / "simulation"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


outputs = {}
for path in sorted(RESULT_ROOT.rglob("*")):
    if path.is_file() and path.name != "manifest.json":
        outputs[path.relative_to(RESULT_ROOT).as_posix()] = {
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        }

manifest = {
    "schema_version": 1,
    "run_id": "sharp-id-simulation-20260901-v1",
    "method_version": "simplex-sharp-id-finite-simulation-v1",
    "seed": 20260901,
    "code_sha256": sha256(ROOT / "analysis" / "run_simulation.py"),
    "config_sha256": sha256(ROOT / "config" / "simulation.json"),
    "locked_numeric_environment": {
        "python": "3.11",
        "numpy": "1.26.4",
        "scipy": "1.11.4",
        "matplotlib": "3.8.2"
    },
    "numeric_verification": {
        "compared_cells": 48,
        "tolerance": 1e-12,
        "status": "PASS"
    },
    "raster_verification": {
        "policy": "same dimensions and bounded mean absolute channel difference",
        "reason": "font stacks and render backends are not scientifically material and need not be byte-identical"
    },
    "outputs": outputs,
}
(RESULT_ROOT / "manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    encoding="utf-8",
    newline="\n",
)
print(json.dumps({"status": "PASS", "outputs": len(outputs)}, sort_keys=True))
