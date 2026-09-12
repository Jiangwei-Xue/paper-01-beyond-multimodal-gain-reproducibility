#!/usr/bin/env python3
"""Dependency-free scientific and integrity validation for the public tree."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


IGNORED_TOP_LEVEL = {
    ".git", ".venv", ".venv-meld", ".venv-sim", "rerun_results", "dist",
    "__pycache__",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    failures: list[str] = []

    required = [
        "README.md", "LICENSE", "CITATION.cff", "PUBLIC_ATTRIBUTION.json",
        "PUBLIC_ENVIRONMENT.json", "PUBLIC_RELEASE_CONFIG.json",
        "paper/Beyond_Multimodal_Gain.pdf",
        "paper/LICENSE.md",
        "docs/EXPERIMENT_DESIGN.md", "docs/REPRODUCTION_PROTOCOL.md",
        "docs/VALIDATION_APPLICABILITY.md", "docs/RELEASE_AUDIT.md",
        "docs/DATA_LICENSE_AND_PROVENANCE.md",
        "manuscript_binding/LOCAL_PAPER_BINDING.json",
        "manuscript_binding/PAPER_RESULTS_MAP.json",
        "config/EXPERIMENT_MANIFEST.json", "config/meld_reproduction.json",
        "config/simulation.json", "config/nhanes_crosscheck_reproduction.R",
        "input_data/meld_reanalysis_continuous_features.csv",
        "input_data/meld_reanalysis_pairs.csv", "input_data/nhanes_analysis_public.csv",
        "input_data/crosscheck_pairs_public.csv",
        "canonical_results/meld/manifest.json",
        "canonical_results/simulation/manifest.json",
        "canonical_results/empirical/environment.txt",
        "canonical_results/floor_diagnostics/environment.txt",
        "provenance/PUBLIC_RELEASE_MANIFEST.jsonl",
        "provenance/SHA256SUMS.txt",
    ]
    for relative in required:
        if not (root / relative).is_file():
            failures.append(f"missing required file: {relative}")

    license_scope = (root / "LICENSE").read_text(encoding="utf-8")
    paper_license = (root / "paper/LICENSE.md").read_text(encoding="utf-8")
    cc_legal = (root / "LICENSES/CC-BY-4.0.txt").read_text(encoding="utf-8")
    citation = (root / "CITATION.cff").read_text(encoding="utf-8")
    if not all(token in license_scope for token in [
        "paper/Beyond_Multimodal_Gain.pdf", "CC BY 4.0", "MIT License",
        "alternative licenses",
    ]):
        failures.append("layered license scope is incomplete")
    if not all(token in paper_license for token in [
        "Jiangwei Xue, Zhida Qin, and Yuda Bi", "CC BY 4.0",
        "third-party", "paper/Beyond_Multimodal_Gain.pdf",
    ]):
        failures.append("paper license notice is incomplete")
    if not all(token in cc_legal for token in [
        "Creative Commons Attribution 4.0 International Public License",
        "Section 1 -- Definitions.", "Section 8 -- Interpretation.",
        "https://creativecommons.org/licenses/by/4.0/legalcode.txt",
    ]):
        failures.append("CC BY 4.0 legal text is incomplete")
    if "  - MIT" not in citation or "  - CC-BY-4.0" not in citation:
        failures.append("citation metadata omits layered license identifiers")

    release_config = load_json(root / "PUBLIC_RELEASE_CONFIG.json")
    if release_config.get("public_release_id") != "bmg-minimal-reproduction-v1.9.0":
        failures.append("public release identity mismatch")
    allowlisted = {item["source"] for item in release_config.get("allowlist", [])}
    if "paper/LICENSE.md" not in allowlisted:
        failures.append("paper license notice is not release-allowlisted")

    binding = load_json(root / "manuscript_binding/LOCAL_PAPER_BINDING.json")
    paper = root / binding["paper_path"]
    if not paper.is_file() or sha256(paper) != binding.get("paper_pdf_sha256"):
        failures.append("paper hash binding mismatch")
    attribution = load_json(root / "PUBLIC_ATTRIBUTION.json")
    expected_authors = attribution.get("paper_authors", [])
    if binding.get("paper_author_metadata") != "PUBLIC_ATTRIBUTION.json":
        failures.append("paper author metadata binding mismatch")
    if len(expected_authors) != 3 or len(set(expected_authors)) != 3 or not all(
        isinstance(author, str) and author.strip() for author in expected_authors
    ):
        failures.append("public author metadata is incomplete")
    if binding.get("source_build_status") != "pass" or binding.get("visible_content_equivalence") != "pass":
        failures.append("paper source-build validation mismatch")
    paper_map = load_json(root / "manuscript_binding/PAPER_RESULTS_MAP.json")
    if paper_map.get("included_paper_pdf_sha256") != binding.get("paper_pdf_sha256"):
        failures.append("paper result-map hash mismatch")

    meld_cfg = load_json(root / "config/meld_reproduction.json")
    for filename, expected in meld_cfg["expected_input_sha256"].items():
        if sha256(root / "input_data" / filename) != expected:
            failures.append(f"MELD input hash mismatch: {filename}")

    with (root / "input_data/meld_reanalysis_continuous_features.csv").open(newline="", encoding="utf-8") as handle:
        continuous = list(csv.DictReader(handle))
    with (root / "input_data/meld_reanalysis_pairs.csv").open(newline="", encoding="utf-8") as handle:
        discrete = list(csv.DictReader(handle))
    if len(continuous) != 2330 or len(discrete) != 2330:
        failures.append("MELD pair count mismatch")
    keys = ("dialogue_id", "source_key", "target_key", "y_sentiment")
    if any(any(a[k] != b[k] for k in keys) for a, b in zip(continuous, discrete)):
        failures.append("MELD continuous/discrete alignment mismatch")
    dimensions = {
        "text": sum(k.startswith("text_svd_") for k in continuous[0]),
        "audio": sum(k.startswith("audio_pca_") for k in continuous[0]),
        "visual": sum(k.startswith("visual_pca_") for k in continuous[0]),
    }
    if dimensions != {"text": 32, "audio": 16, "visual": 32}:
        failures.append(f"compact feature dimension mismatch: {dimensions}")

    with (root / "input_data/nhanes_analysis_public.csv").open(newline="", encoding="utf-8") as handle:
        nhanes = list(csv.DictReader(handle))
    if len(nhanes) != 6565 or sum(row["Y_primary"] == "1" for row in nhanes) != 903:
        failures.append("NHANES denominator or event mismatch")

    with (root / "input_data/crosscheck_pairs_public.csv").open(newline="", encoding="utf-8") as handle:
        crosscheck = list(csv.DictReader(handle))
    unique_ids = list(dict.fromkeys(row["participant_id"] for row in crosscheck))
    if len(crosscheck) != 5607 or len(unique_ids) != 60:
        failures.append("CrossCheck denominator or cluster mismatch")

    with (root / "canonical_results/meld/oof_predictions.csv").open(newline="", encoding="utf-8") as handle:
        oof = list(csv.DictReader(handle))
    folds: dict[str, set[str]] = {}
    for row in oof:
        folds.setdefault(row["dialogue_id"], set()).add(row["outer_fold"])
    if len(oof) != 2330 or len(folds) != 268 or any(len(value) != 1 for value in folds.values()):
        failures.append("MELD grouped OOF isolation mismatch")

    for base in ["canonical_results/meld", "canonical_results/simulation"]:
        manifest = load_json(root / base / "manifest.json")
        for relative, record in manifest["outputs"].items():
            target = root / base / relative
            if not target.is_file() or sha256(target) != record["sha256"]:
                failures.append(f"run manifest mismatch: {base}/{relative}")
    meld_manifest = load_json(root / "canonical_results/meld/manifest.json")
    if sha256(root / "analysis/run_meld_reproduction.py") != meld_manifest["code_sha256"]:
        failures.append("MELD code hash mismatch")

    public_manifest = root / "provenance/PUBLIC_RELEASE_MANIFEST.jsonl"
    if public_manifest.is_file():
        rows = [json.loads(line) for line in public_manifest.read_text(encoding="utf-8").splitlines() if line]
        path_set = {row["path"] for row in rows}
        license_by_path = {row["path"]: row.get("license") for row in rows}
        if len(rows) != len(path_set):
            failures.append("duplicate package manifest path")
        if license_by_path.get("paper/Beyond_Multimodal_Gain.pdf") != "CC-BY-4.0":
            failures.append("paper PDF license mapping mismatch")
        if license_by_path.get("paper/LICENSE.md") != "CC-BY-4.0":
            failures.append("paper notice license mapping mismatch")
        if license_by_path.get("PUBLIC_RELEASE_CONFIG.json") != "MIT":
            failures.append("executable release configuration license mismatch")
        for row in rows:
            target = root / row["path"]
            if not target.is_file() or sha256(target) != row["sha256"]:
                failures.append(f"package hash mismatch: {row['path']}")
            for parent in row.get("parent_artifacts", []):
                if parent not in path_set:
                    failures.append(f"broken lineage parent: {row['path']} -> {parent}")

    status = "PASS" if not failures else "FAIL"
    result = {
        "PACKAGE_VALIDATION": status,
        "package_integrity": status,
        "experiment_definition": status,
        "data_provenance": status,
        "result_provenance": status,
        "paper_result_mapping": status,
        "meld_pairs": len(continuous),
        "meld_dialogues": len(folds),
        "nhanes_rows": len(nhanes),
        "crosscheck_pairs": len(crosscheck),
        "crosscheck_participants": len(unique_ids),
        "feature_dimensions": dimensions,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
