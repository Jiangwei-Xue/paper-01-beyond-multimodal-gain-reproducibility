"""Shared table definitions for canonical-versus-rerun checks."""

import csv


SPECS = {
    "primary_predictive_gain.csv": ["modality"],
    "representation_ladder.csv": ["text_dims", "modality"],
    "same_speaker_subgroup.csv": ["modality"],
    "split_stability.csv": ["seed"],
    "general_T_model_based_sharp.csv": ["modality"],
}


def read_rows(path, keys):
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {tuple(row[key] for key in keys): row for row in rows}
