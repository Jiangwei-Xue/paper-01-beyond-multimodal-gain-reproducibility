#!/usr/bin/env python3
"""Compare a simulation rerun with the manuscript-bound reference outputs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image


CSV_FILES = ("simulation_population.csv", "simulation_coverage.csv")
PNG_FILES = (
    "simulation_identification.png",
    "simulation_stability.png",
    "simulation_coverage.png",
)


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    return rows[0], rows[1:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", default="canonical_results/simulation")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--numeric-tolerance", type=float, default=1e-12)
    parser.add_argument("--pixel-mean-tolerance", type=float, default=8.0)
    args = parser.parse_args()
    reference = Path(args.reference)
    candidate = Path(args.candidate)

    compared = 0
    maximum = 0.0
    failures: list[str] = []
    for filename in CSV_FILES:
        ref_header, ref_rows = read_csv(reference / "data" / filename)
        cand_header, cand_rows = read_csv(candidate / "data" / filename)
        if ref_header != cand_header or len(ref_rows) != len(cand_rows):
            failures.append(f"table shape/header mismatch: {filename}")
            continue
        for row_index, (ref_row, cand_row) in enumerate(zip(ref_rows, cand_rows)):
            if len(ref_row) != len(cand_row):
                failures.append(f"row width mismatch: {filename}:{row_index}")
                continue
            for column, ref_value, cand_value in zip(ref_header, ref_row, cand_row):
                try:
                    difference = abs(float(ref_value) - float(cand_value))
                except ValueError:
                    if ref_value != cand_value:
                        failures.append(f"text mismatch: {filename}:{row_index}:{column}")
                    continue
                compared += 1
                maximum = max(maximum, difference)
                if difference > args.numeric_tolerance:
                    failures.append(
                        f"numeric mismatch: {filename}:{row_index}:{column}:{difference}"
                    )

    image_checks = {}
    for filename in PNG_FILES:
        ref = np.asarray(Image.open(reference / "figures" / filename).convert("RGBA"), dtype=np.int16)
        cand = np.asarray(Image.open(candidate / "figures" / filename).convert("RGBA"), dtype=np.int16)
        if ref.shape != cand.shape:
            failures.append(f"image shape mismatch: {filename}")
            continue
        difference = np.abs(ref - cand)
        mean_difference = float(difference.mean())
        image_checks[filename] = {
            "shape": list(ref.shape),
            "max_channel_difference": int(difference.max()),
            "mean_channel_difference": mean_difference,
            "changed_channel_fraction": float(np.mean(difference > 0)),
        }
        if mean_difference > args.pixel_mean_tolerance:
            failures.append(f"image content drift: {filename}:{mean_difference}")

    result = {
        "SIMULATION_RERUN_STATUS": "PASS" if not failures else "FAIL",
        "compared_numeric_cells": compared,
        "max_absolute_numeric_difference": maximum,
        "numeric_tolerance": args.numeric_tolerance,
        "image_checks": image_checks,
        "pixel_mean_tolerance": args.pixel_mean_tolerance,
        "failures": failures,
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
