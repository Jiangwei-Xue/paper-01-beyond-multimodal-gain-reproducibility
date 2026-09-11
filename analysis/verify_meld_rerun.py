#!/usr/bin/env python3
"""Numerically compare a fresh rerun against the canonical packaged results."""

import argparse
import csv
import json
from pathlib import Path

from result_io import SPECS, read_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", default="canonical_results")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--tolerance", type=float, default=1e-10)
    args = parser.parse_args()
    reference = Path(args.reference)
    candidate = Path(args.candidate)
    maximum = 0.0
    count = 0
    for filename, keys in SPECS.items():
        left = read_rows(reference / filename, keys)
        right = read_rows(candidate / filename, keys)
        if set(left) != set(right):
            raise RuntimeError(f"row keys differ for {filename}")
        for key in left:
            for column in (set(left[key]) & set(right[key])) - set(keys):
                try:
                    difference = abs(float(left[key][column]) - float(right[key][column]))
                except ValueError:
                    continue
                maximum = max(maximum, difference)
                count += 1
    status = "PASS" if maximum <= args.tolerance else "FAIL"
    print(json.dumps({
        "RERUN_NUMERICAL_STATUS": status,
        "compared_numeric_cells": count,
        "max_absolute_difference": maximum,
        "tolerance": args.tolerance,
    }, sort_keys=True))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
