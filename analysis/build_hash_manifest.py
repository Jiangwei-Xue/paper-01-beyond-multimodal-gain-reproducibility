#!/usr/bin/env python3
"""Build the public scientific artifact manifest from the release allowlist."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SELF_PATHS = {
    "provenance/PUBLIC_RELEASE_MANIFEST.jsonl",
    "provenance/SHA256SUMS.txt",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def lineage(path: str) -> tuple[list[str], str | None]:
    if path.startswith("canonical_results/meld/"):
        return [
            "analysis/run_meld_reproduction.py",
            "config/meld_reproduction.json",
            "input_data/meld_reanalysis_continuous_features.csv",
            "input_data/meld_reanalysis_pairs.csv",
        ], "meld-realdata-reproduction-20260901-v1"
    if path.startswith("canonical_results/simulation/"):
        return ["analysis/run_simulation.py", "config/simulation.json"], "sharp-id-simulation-20260901-v1"
    if path.startswith("canonical_results/empirical/nhanes/"):
        return [
            "analysis/empirical_common.R",
            "analysis/run_empirical_reproduction.R",
            "config/nhanes_crosscheck_reproduction.R",
            "input_data/nhanes_analysis_public.csv",
        ], "nhanes-crosscheck-formal-v1"
    if path.startswith("canonical_results/empirical/crosscheck/"):
        return [
            "analysis/empirical_common.R",
            "analysis/run_empirical_reproduction.R",
            "config/nhanes_crosscheck_reproduction.R",
            "input_data/crosscheck_pairs_public.csv",
        ], "nhanes-crosscheck-formal-v1"
    if path.startswith("canonical_results/floor_diagnostics/"):
        return [
            "analysis/empirical_common.R",
            "analysis/run_nhanes_floor_diagnostics.R",
            "config/nhanes_crosscheck_reproduction.R",
            "input_data/nhanes_analysis_public.csv",
        ], "nhanes-positive-floor-diagnostics-v1"
    if path == "manuscript_binding/PAPER_RESULTS_MAP.json":
        return [
            "canonical_results/meld/manifest.json",
            "canonical_results/simulation/data/simulation_coverage.csv",
            "canonical_results/empirical/nhanes/witness_results.csv",
            "canonical_results/empirical/crosscheck/witness_results.csv",
            "canonical_results/floor_diagnostics/positive_floor_sensitivity/paper_selected_floor_rows.csv",
        ], None
    if path == "manuscript_binding/LOCAL_PAPER_BINDING.json":
        return ["manuscript_binding/PAPER_RESULTS_MAP.json", "paper/Beyond_Multimodal_Gain.pdf"], None
    if path in {"input_data/nhanes_analysis_public.csv", "input_data/crosscheck_pairs_public.csv"}:
        return ["docs/DATA_LICENSE_AND_PROVENANCE.md"], None
    if path == "input_data/meld_reanalysis_pairs.csv":
        return ["input_data/meld_reanalysis_pairs_metadata.json"], None
    if path == "input_data/meld_reanalysis_continuous_features.csv":
        return ["input_data/meld_reanalysis_continuous_metadata.json"], None
    return [], None


def license_for(path: str, role: str) -> str:
    if (
        path.startswith(("upstream/", "analysis/", "config/", "requirements"))
        or path in {
            "Makefile", "PUBLIC_RELEASE_CONFIG.json", ".gitignore", ".gitattributes",
        }
    ):
        return "MIT"
    if path.startswith("paper/"):
        return "CC-BY-4.0"
    if path.startswith("input_data/") or path.startswith("third_party/"):
        return "upstream-terms"
    if path.startswith("LICENSES/"):
        return "license-text"
    return "CC-BY-4.0"


def purpose_for(path: str, role: str) -> str:
    if path.startswith("canonical_results/"):
        return "reference output for scientific equivalence validation"
    if path.startswith("input_data/"):
        return "compact scientific input"
    if path.startswith("analysis/"):
        return "analysis or validation implementation"
    if path.startswith("config/"):
        return "frozen experimental specification"
    if path.startswith("manuscript_binding/"):
        return "paper-to-result provenance"
    if path.startswith("paper/"):
        return "reference manuscript bound to the results"
    return role.replace("-", " ")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--config", default="PUBLIC_RELEASE_CONFIG.json")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    config = json.loads((root / args.config).read_text(encoding="utf-8"))
    rows = []
    sums = []
    seen = set()
    for item in config["allowlist"]:
        source = item["source"]
        if source in SELF_PATHS or source in seen:
            continue
        seen.add(source)
        path = root / source
        if not path.is_file():
            raise FileNotFoundError(source)
        digest = sha256(path)
        parents, produced_by = lineage(source)
        rows.append({
            "path": source,
            "role": item["role"],
            "sha256": digest,
            "size_bytes": path.stat().st_size,
            "scientific_purpose": purpose_for(source, item["role"]),
            "reproducibility_relevance": "required" if produced_by or parents or source.startswith(("analysis/", "config/", "input_data/", "canonical_results/", "manuscript_binding/")) else "supporting",
            "license": license_for(source, item["role"]),
            "produced_by_run": produced_by,
            "parent_artifacts": parents,
        })
        sums.append(f"{digest}  {source}")
    serialized = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        for row in sorted(rows, key=lambda value: value["path"])
    )
    (root / "provenance/PUBLIC_RELEASE_MANIFEST.jsonl").write_text(serialized, encoding="utf-8", newline="\n")
    (root / "provenance/SHA256SUMS.txt").write_text("\n".join(sorted(sums)) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "artifacts": len(rows)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
