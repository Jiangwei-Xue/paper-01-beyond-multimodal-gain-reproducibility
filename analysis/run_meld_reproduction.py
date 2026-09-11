#!/usr/bin/env python3
"""Deterministic MELD next-turn sentiment reproduction.

The released inputs contain only low-dimensional transformed features, coarse
proxy clusters, labels, dialogue identifiers, and context indicators. They do
not contain transcripts, raw audio, raw video, or pre-reduction embeddings.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sys
from pathlib import Path

import numpy as np
import sklearn
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


LN2 = math.log(2.0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_continuous(path: Path) -> dict:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        text_cols = [x for x in fields if x.startswith("text_svd_")]
        audio_cols = [x for x in fields if x.startswith("audio_pca_")]
        visual_cols = [x for x in fields if x.startswith("visual_pca_")]
        rows = list(reader)
    def matrix(columns: list[str]) -> np.ndarray:
        return np.asarray([[float(row[x]) for x in columns] for row in rows], dtype=np.float64)
    return {
        "dialogue_id": np.asarray([int(row["dialogue_id"]) for row in rows], dtype=np.int64),
        "source_key": np.asarray([row["source_key"] for row in rows], dtype=object),
        "target_key": np.asarray([row["target_key"] for row in rows], dtype=object),
        "y": np.asarray([int(row["y_sentiment"]) for row in rows], dtype=np.int64),
        "source_major": np.asarray([int(row["source_major"]) for row in rows], dtype=np.float64),
        "next_same_speaker": np.asarray([int(row["next_same_speaker"]) for row in rows], dtype=np.float64),
        "text": matrix(text_cols),
        "audio": matrix(audio_cols),
        "visual": matrix(visual_cols),
    }


def load_discrete(path: Path) -> dict:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        "dialogue_id": np.asarray([int(row["dialogue_id"]) for row in rows], dtype=np.int64),
        "source_key": np.asarray([row["source_key"] for row in rows], dtype=object),
        "target_key": np.asarray([row["target_key"] for row in rows], dtype=object),
        "y": np.asarray([int(row["y_sentiment"]) for row in rows], dtype=np.int64),
        "audio": np.asarray([int(row["audio_cluster"]) for row in rows], dtype=np.int64),
        "visual": np.asarray([int(row["visual_cluster"]) for row in rows], dtype=np.int64),
        "fused": np.asarray([int(row["fused_cluster"]) for row in rows], dtype=np.int64),
    }


def validate_alignment(continuous: dict, discrete: dict) -> None:
    for key in ("dialogue_id", "source_key", "target_key", "y"):
        if not np.array_equal(continuous[key], discrete[key]):
            raise RuntimeError(f"continuous/discrete row mismatch: {key}")


def outcome_entropy_bits(y: np.ndarray) -> float:
    counts = np.bincount(y, minlength=3).astype(float)
    p = counts / counts.sum()
    return float(-np.sum(p[p > 0] * np.log2(p[p > 0])))


def make_model(c_value: float, config: dict):
    model = LogisticRegression(
        C=float(c_value),
        penalty="l2",
        solver="lbfgs",
        max_iter=int(config["logistic_max_iter"]),
        tol=float(config["logistic_tol"]),
    )
    if config["standardize_within_fold"]:
        return make_pipeline(StandardScaler(), model)
    return model


def true_class_probabilities(probabilities: np.ndarray, classes: np.ndarray, y: np.ndarray) -> np.ndarray:
    class_to_col = {int(label): i for i, label in enumerate(classes)}
    return probabilities[np.arange(len(y)), np.asarray([class_to_col[int(label)] for label in y])]


def classes_from_model(model) -> np.ndarray:
    final = model[-1] if hasattr(model, "__getitem__") else model
    return np.asarray(final.classes_)


def mean_log_loss_bits(y: np.ndarray, probability: np.ndarray, clip: float) -> float:
    return float(-np.mean(np.log2(np.clip(probability, clip, 1.0))))


def tune_c(X: np.ndarray, y: np.ndarray, groups: np.ndarray, seed: int, config: dict) -> tuple[float, list[dict]]:
    splitter = StratifiedGroupKFold(
        n_splits=int(config["inner_folds"]), shuffle=True, random_state=int(seed)
    )
    grid_records = []
    best = None
    for c_value in config["c_grid"]:
        losses = []
        counts = []
        for train, valid in splitter.split(X, y, groups):
            model = make_model(c_value, config)
            model.fit(X[train], y[train])
            proba = model.predict_proba(X[valid])
            true_p = true_class_probabilities(proba, classes_from_model(model), y[valid])
            losses.append(-np.sum(np.log2(np.clip(true_p, config["probability_clip"], 1.0))))
            counts.append(len(valid))
        score = float(np.sum(losses) / np.sum(counts))
        grid_records.append({"C": float(c_value), "log_loss_bits": score})
        candidate = (score, float(c_value))
        if best is None or candidate < best:
            best = candidate
    assert best is not None
    return best[1], grid_records


def nested_oof(X: np.ndarray, y: np.ndarray, groups: np.ndarray, seed: int, config: dict):
    splitter = StratifiedGroupKFold(
        n_splits=int(config["outer_folds"]), shuffle=True, random_state=int(seed)
    )
    oof = np.full(len(y), np.nan, dtype=float)
    fold = np.full(len(y), -1, dtype=int)
    tuning = []
    for fold_id, (train, test) in enumerate(splitter.split(X, y, groups)):
        inner_seed = int(seed)
        selected_c, grid = tune_c(X[train], y[train], groups[train], inner_seed, config)
        model = make_model(selected_c, config)
        model.fit(X[train], y[train])
        proba = model.predict_proba(X[test])
        oof[test] = true_class_probabilities(proba, classes_from_model(model), y[test])
        fold[test] = fold_id
        tuning.append({
            "fold": fold_id,
            "inner_seed": inner_seed,
            "selected_C": selected_c,
            "n_train": int(len(train)),
            "n_test": int(len(test)),
            "train_dialogues": int(len(np.unique(groups[train]))),
            "test_dialogues": int(len(np.unique(groups[test]))),
            "grid": grid,
        })
    if np.isnan(oof).any() or np.any(fold < 0):
        raise RuntimeError("OOF predictions are incomplete")
    return oof, fold, tuning


def cluster_inference(values: np.ndarray, groups: np.ndarray, seed: int, config: dict) -> dict:
    estimate = float(np.mean(values))
    unique_groups, inverse = np.unique(groups, return_inverse=True)
    centered_sums = np.bincount(inverse, weights=values - estimate, minlength=len(unique_groups))
    rng = np.random.default_rng(int(seed))
    reps = int(config["multiplier_replicates"])
    draws = np.empty(reps, dtype=float)
    chunk = 1000
    for start in range(0, reps, chunk):
        stop = min(reps, start + chunk)
        signs = rng.choice(np.asarray([-1.0, 1.0]), size=(stop - start, len(unique_groups)))
        draws[start:stop] = signs @ centered_sums / len(values)
    alpha = 1.0 - float(config["confidence_level"])
    critical = float(np.quantile(np.abs(draws), 1.0 - alpha))
    p = float((1 + np.sum(np.abs(draws) >= abs(estimate))) / (reps + 1))
    finite = math.sqrt(len(unique_groups) / (len(unique_groups) - 1))
    se = float(finite * np.sqrt(np.sum(centered_sums ** 2)) / len(values))
    return {
        "estimate": estimate,
        "ci_low": estimate - critical,
        "ci_high": estimate + critical,
        "p": p,
        "critical": critical,
        "cluster_se": se,
        "n_clusters": int(len(unique_groups)),
        "multiplier_seed": int(seed),
    }


def design(continuous: dict, text_dims: int, modality: str) -> tuple[np.ndarray, np.ndarray]:
    context = np.column_stack([continuous["source_major"], continuous["next_same_speaker"]])
    base = np.column_stack([continuous["text"][:, :text_dims], context])
    if modality == "audio":
        extra = continuous["audio"]
    elif modality == "visual":
        extra = continuous["visual"]
    elif modality == "fused":
        extra = np.column_stack([continuous["audio"], continuous["visual"]])
    else:
        raise ValueError(modality)
    return base, np.column_stack([base, extra])


def predictive_run(continuous: dict, text_dims: int, seed: int, config: dict, subset=None):
    if subset is None:
        subset = np.ones(len(continuous["y"]), dtype=bool)
    y = continuous["y"][subset]
    groups = continuous["dialogue_id"][subset]
    results = {}
    row_scores = {}
    fold_records = {}
    base_prob_cache = None
    for modality_index, modality in enumerate(config["modalities"]):
        base, augmented = design(continuous, text_dims, modality)
        base = base[subset]
        augmented = augmented[subset]
        if base_prob_cache is None:
            base_prob, base_fold, base_tuning = nested_oof(base, y, groups, seed, config)
            base_prob_cache = (base_prob, base_fold, base_tuning)
        else:
            base_prob, base_fold, base_tuning = base_prob_cache
        aug_prob, aug_fold, aug_tuning = nested_oof(augmented, y, groups, seed, config)
        if not np.array_equal(base_fold, aug_fold):
            raise RuntimeError("base and augmented outer folds differ")
        score = np.log2(np.clip(aug_prob, config["probability_clip"], 1.0)) - np.log2(
            np.clip(base_prob, config["probability_clip"], 1.0)
        )
        inference = cluster_inference(score, groups, seed + 1000 + modality_index, config)
        inference["base_log_loss_bits"] = mean_log_loss_bits(y, base_prob, config["probability_clip"])
        inference["augmented_log_loss_bits"] = mean_log_loss_bits(y, aug_prob, config["probability_clip"])
        results[modality] = inference
        row_scores[modality] = score
        fold_records[modality] = {"base": base_tuning, "augmented": aug_tuning}
    return results, row_scores, base_fold, fold_records


def entropy_rows(prob: np.ndarray) -> np.ndarray:
    clipped = np.clip(prob, 1e-300, 1.0)
    return -np.sum(prob * np.log2(clipped), axis=-1)


def inverse_floor_simplex(n: int, floor: float) -> np.ndarray:
    if not (0.0 <= floor < 1.0 / n):
        raise ValueError("floor outside simplex interior")
    a = np.full(n, floor, dtype=float)
    return (np.eye(n) - np.outer(a, np.ones(n))) / (1.0 - a.sum())


def joint_oof(text: np.ndarray, context: np.ndarray, y: np.ndarray, m: np.ndarray,
              groups: np.ndarray, seed: int, config: dict) -> tuple[np.ndarray, list[dict]]:
    X = np.column_stack([text, context])
    joint_y = y * 4 + m
    splitter = StratifiedGroupKFold(
        n_splits=int(config["outer_folds"]), shuffle=True, random_state=int(seed)
    )
    output = np.zeros((len(y), 12), dtype=float)
    records = []
    for fold_id, (train, test) in enumerate(splitter.split(X, joint_y, groups)):
        selected_c, grid = tune_c(X[train], joint_y[train], groups[train], seed + fold_id + 1, config)
        model = make_model(selected_c, config)
        model.fit(X[train], joint_y[train])
        predicted = model.predict_proba(X[test])
        full = np.zeros((len(test), 12), dtype=float)
        for column, label in enumerate(classes_from_model(model)):
            full[:, int(label)] = predicted[:, column]
        output[test] = full
        records.append({"fold": fold_id, "selected_C": selected_c, "grid": grid})
    return output.reshape(len(y), 3, 4), records


def model_functionals(joint: np.ndarray, eta: float = 0.0, alpha: float = 0.0) -> dict:
    py = joint.sum(axis=2)
    pm = joint.sum(axis=1)
    h_y = float(np.mean(entropy_rows(py)))
    h_joint = entropy_rows(joint.reshape(len(joint), -1))
    h_m = entropy_rows(pm)
    witness = float(np.mean(entropy_rows(py) + h_m - h_joint))
    inv_m = inverse_floor_simplex(4, eta)
    z = np.einsum("nym,jm->nyj", joint, inv_m)
    weights = z.sum(axis=1)
    lower_conditional = 0.0
    for row in range(len(joint)):
        for component in range(4):
            weight = weights[row, component]
            if weight > 1e-15:
                q = np.maximum(z[row, :, component], 0.0) / weight
                lower_conditional += weight * float(entropy_rows(q[None, :])[0])
    lower_conditional /= len(joint)
    lower = h_y - lower_conditional
    extreme = np.full(3, alpha, dtype=float)
    extreme[0] = 1.0 - 2.0 * alpha
    upper = h_y - float(entropy_rows(extreme[None, :])[0])
    inv_y = inverse_floor_simplex(3, alpha)
    canonical = np.einsum("iy,nym,jm->nij", inv_y, joint, inv_m)
    return {
        "H_Y_given_R_C_bits": h_y,
        "witness_bits": witness,
        "lower_bits": lower,
        "upper_bits": upper,
        "compatible": bool(np.min(canonical) >= -1e-10),
        "minimum_canonical_cell": float(np.min(canonical)),
    }


def max_floor(joint: np.ndarray, fixed_floor: float, vary: str) -> float:
    if vary not in {"eta", "alpha"}:
        raise ValueError(vary)
    lo = 0.0
    hi = (0.25 if vary == "eta" else 1.0 / 3.0) - 1e-12
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if vary == "eta":
            ok = model_functionals(joint, eta=mid, alpha=fixed_floor)["compatible"]
        else:
            ok = model_functionals(joint, eta=fixed_floor, alpha=mid)["compatible"]
        if ok:
            lo = mid
        else:
            hi = mid
    return lo


def make_plots(output_dir: Path, primary_rows: list[dict], ladder_rows: list[dict], model_rows: list[dict]) -> None:
    labels = [row["modality"] for row in primary_rows]
    gain = np.asarray([float(row["nested_cv_gain_bits"]) for row in primary_rows])
    low = np.asarray([float(row["cluster_multiplier_ci_low"]) for row in primary_rows])
    high = np.asarray([float(row["cluster_multiplier_ci_high"]) for row in primary_rows])
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    x = np.arange(len(labels))
    ax.errorbar(x, gain, yerr=np.vstack([gain - low, high - gain]), fmt="o", capsize=5)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Incremental log-score gain (bits)")
    fig.tight_layout()
    fig.savefig(output_dir / "primary_predictive_gain.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for modality in labels:
        rows = [row for row in ladder_rows if row["modality"] == modality]
        dims = np.asarray([int(row["text_dims"]) for row in rows])
        values = np.asarray([float(row["gain_bits"]) for row in rows])
        lo = np.asarray([float(row["ci_low"]) for row in rows])
        hi = np.asarray([float(row["ci_high"]) for row in rows])
        ax.errorbar(dims, values, yerr=np.vstack([values - lo, hi - values]), marker="o", capsize=3, label=modality)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xlabel("Text SVD dimensions")
    ax.set_ylabel("Incremental log-score gain (bits)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_dir / "representation_ladder.png", dpi=180)
    plt.close(fig)

    lower = np.asarray([float(row["lower_eta_0_02"]) for row in model_rows])
    upper = np.asarray([float(row["upper_alpha_0_05"]) for row in model_rows])
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    for i, label in enumerate(labels):
        ax.plot([lower[i], upper[i]], [i, i], color="tab:blue", linewidth=2)
        ax.plot([lower[i], upper[i]], [i, i], "o", color="tab:blue")
    ax.set_yticks(np.arange(len(labels)), labels)
    ax.set_xlabel("Model-based sharp functional (bits)")
    fig.tight_layout()
    fig.savefig(output_dir / "general_T_model_based_intervals.png", dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/reproduction.json")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="canonical_results")
    args = parser.parse_args()
    config_path = Path(args.config)
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fold_dir = output_dir / "folds"
    fold_dir.mkdir(parents=True, exist_ok=True)
    config = read_json(config_path)

    continuous_path = data_dir / "meld_reanalysis_continuous_features.csv"
    discrete_path = data_dir / "meld_reanalysis_pairs.csv"
    actual_hashes = {path.name: sha256_file(path) for path in (continuous_path, discrete_path)}
    if actual_hashes != config["expected_input_sha256"]:
        raise RuntimeError(f"input hash mismatch: {actual_hashes}")
    continuous = load_continuous(continuous_path)
    discrete = load_discrete(discrete_path)
    validate_alignment(continuous, discrete)

    primary, primary_scores, primary_fold, primary_tuning = predictive_run(
        continuous, 32, int(config["seed"]), config
    )
    primary_rows = []
    for modality in config["modalities"]:
        item = primary[modality]
        primary_rows.append({
            "modality": modality,
            "nested_cv_gain_bits": item["estimate"],
            "cluster_multiplier_ci_low": item["ci_low"],
            "cluster_multiplier_ci_high": item["ci_high"],
            "cluster_multiplier_p": item["p"],
        })
    write_csv(output_dir / "primary_predictive_gain.csv", primary_rows, list(primary_rows[0]))

    score_rows = []
    indices = np.arange(len(continuous["y"]))
    for i in indices:
        score_rows.append({
            "row_index": int(i),
            "dialogue_id": int(continuous["dialogue_id"][i]),
            "source_key": continuous["source_key"][i],
            "target_key": continuous["target_key"][i],
            "outer_fold": int(primary_fold[i]),
            "audio_score_diff_bits": float(primary_scores["audio"][i]),
            "visual_score_diff_bits": float(primary_scores["visual"][i]),
            "fused_score_diff_bits": float(primary_scores["fused"][i]),
        })
    write_csv(output_dir / "oof_predictions.csv", score_rows, list(score_rows[0]))
    write_json(fold_dir / "primary_fold_and_tuning_manifest.json", primary_tuning)

    ladder_rows = []
    for text_dims in config["text_dimensions"]:
        if int(text_dims) == 32:
            ladder = primary
        else:
            ladder, _, _, _ = predictive_run(continuous, int(text_dims), int(config["seed"]), config)
        for modality in config["modalities"]:
            item = ladder[modality]
            width = 1.96 * item["cluster_se"]
            ladder_rows.append({
                "text_dims": int(text_dims),
                "modality": modality,
                "gain_bits": item["estimate"],
                "ci_low": item["estimate"] - width,
                "ci_high": item["estimate"] + width,
            })
    write_csv(output_dir / "representation_ladder.csv", ladder_rows, list(ladder_rows[0]))

    stability_rows = []
    for seed in config["stability_seeds"]:
        result, _, _, _ = predictive_run(continuous, 32, int(seed), config)
        stability_rows.append({"seed": int(seed), **{m: result[m]["estimate"] for m in config["modalities"]}})
    write_csv(output_dir / "split_stability.csv", stability_rows, list(stability_rows[0]))

    subset = continuous["next_same_speaker"].astype(bool)
    subgroup, _, _, _ = predictive_run(continuous, 32, int(config["seed"]), config, subset=subset)
    subgroup_rows = []
    for modality in config["modalities"]:
        item = subgroup[modality]
        subgroup_rows.append({
            "modality": modality,
            "gain_bits": item["estimate"],
            "ci_low": item["ci_low"],
            "ci_high": item["ci_high"],
            "p": item["p"],
        })
    write_csv(output_dir / "same_speaker_subgroup.csv", subgroup_rows, list(subgroup_rows[0]))

    context = np.column_stack([continuous["source_major"], continuous["next_same_speaker"]])
    model_rows = []
    model_tuning = {}
    for modality_index, modality in enumerate(config["modalities"]):
        joint, tuning = joint_oof(
            continuous["text"], context, continuous["y"], discrete[modality],
            continuous["dialogue_id"], int(config["seed"]) + 2000 + modality_index, config
        )
        model_tuning[modality] = tuning
        base = model_functionals(joint)
        lower_005 = model_functionals(joint, eta=0.005)["lower_bits"]
        lower_01 = model_functionals(joint, eta=0.01)["lower_bits"]
        lower_02 = model_functionals(joint, eta=0.02)["lower_bits"]
        upper_003 = model_functionals(joint, alpha=0.03)["upper_bits"]
        upper_005 = model_functionals(joint, alpha=0.05)["upper_bits"]
        model_rows.append({
            "modality": modality,
            "model_H_Y_given_R_C_bits": base["H_Y_given_R_C_bits"],
            "model_implied_witness_bits": base["witness_bits"],
            "lower_eta_0_005": lower_005,
            "lower_eta_0_01": lower_01,
            "lower_eta_0_02": lower_02,
            "upper_alpha_0_03": upper_003,
            "upper_alpha_0_05": upper_005,
            "eta_max_at_alpha_0_05": max_floor(joint, 0.05, "eta"),
            "alpha_max_at_eta_0_02": max_floor(joint, 0.02, "alpha"),
        })
    write_csv(output_dir / "general_T_model_based_sharp.csv", model_rows, list(model_rows[0]))
    write_json(fold_dir / "model_based_tuning_manifest.json", model_tuning)

    make_plots(output_dir, primary_rows, ladder_rows, model_rows)

    log_lines = [
        f"run_id={config['run_id']}",
        f"seed={config['seed']}",
        f"outer_folds={config['outer_folds']}",
        f"inner_folds={config['inner_folds']}",
        f"n_pairs={len(continuous['y'])}",
        f"n_dialogues={len(np.unique(continuous['dialogue_id']))}",
        f"python={platform.python_version()}",
        f"numpy={np.__version__}",
        f"scikit_learn={sklearn.__version__}",
        "reproduction_timezone=UTC",
    ]
    for modality in config["modalities"]:
        log_lines.append(f"primary_{modality}_gain_bits={primary[modality]['estimate']:.17g}")
    (output_dir / "environment.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8", newline="\n")

    run_record = {
        "schema_version": 1,
        "run_id": config["run_id"],
        "method_version": "meld-continuous-nested-cv-v1",
        "config_sha256": sha256_file(config_path),
        "input_sha256": actual_hashes,
        "code_sha256": sha256_file(Path(__file__)),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "reproduction_timezone": "UTC",
        },
        "n_pairs": int(len(continuous["y"])),
        "n_dialogues": int(len(np.unique(continuous["dialogue_id"]))),
        "outcome_counts": {str(i): int(x) for i, x in enumerate(np.bincount(continuous["y"], minlength=3))},
        "same_speaker_pairs": int(np.sum(subset)),
        "unconditional_outcome_entropy_bits": outcome_entropy_bits(continuous["y"]),
        "text_only_oof_log_loss_bits": primary["audio"]["base_log_loss_bits"],
        "outputs": {},
    }
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            relative = path.relative_to(output_dir).as_posix()
            run_record["outputs"][relative] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    write_json(output_dir / "manifest.json", run_record)
    print(json.dumps({
        "status": "PASS",
        "run_id": config["run_id"],
        "n_pairs": run_record["n_pairs"],
        "results_dir": str(output_dir),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
