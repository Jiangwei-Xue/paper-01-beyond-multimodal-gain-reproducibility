#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PARSER = argparse.ArgumentParser(description="Reproduce the manuscript simulation outputs.")
PARSER.add_argument("--config", default=str(PACKAGE_ROOT / "config" / "simulation.json"))
PARSER.add_argument("--output-dir", default=str(PACKAGE_ROOT / "rerun_results" / "simulation"))
ARGS = PARSER.parse_args()
CONFIG_PATH = Path(ARGS.config)
with CONFIG_PATH.open("r", encoding="utf-8") as handle:
    CONFIG = json.load(handle)

ROOT = Path(ARGS.output_dir)
FIG = ROOT / "figures"
DATA = ROOT / "data"
FIG.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)

RNG = np.random.default_rng(int(CONFIG["seed"]))
LOG2E = 1.0 / math.log(2.0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def entropy(p: np.ndarray) -> float:
    p = np.asarray(p, float)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def floor_matrix(n: int, floor: float) -> np.ndarray:
    a = np.full(n, floor)
    return (1 - a.sum()) * np.eye(n) + np.outer(a, np.ones(n))


def inv_floor_matrix(n: int, floor: float) -> np.ndarray:
    a = np.full(n, floor)
    return (np.eye(n) - np.outer(a, np.ones(n))) / (1 - a.sum())


def mode_mult(P: np.ndarray, M: np.ndarray, mode: int) -> np.ndarray:
    return np.moveaxis(
        np.tensordot(M, np.moveaxis(P, mode, 0), axes=(1, 0)), 0, mode
    )


def h_y_given_t(P: np.ndarray) -> float:
    py_t = P.sum(axis=1)
    pt = py_t.sum(axis=0)
    return sum(pt[t] * entropy(py_t[:, t] / pt[t]) for t in range(P.shape[2]) if pt[t] > 0)


def cmi_y_m_given_t(P: np.ndarray) -> float:
    out = 0.0
    L, J, G = P.shape
    for t in range(G):
        tab = P[:, :, t]
        pt = tab.sum()
        if pt <= 0:
            continue
        q = tab / pt
        py, pm = q.sum(axis=1), q.sum(axis=0)
        for y in range(L):
            for m in range(J):
                if q[y, m] > 0:
                    out += pt * q[y, m] * math.log2(q[y, m] / (py[y] * pm[m]))
    return float(out)


def endpoints(P: np.ndarray, alpha: float, eta: float, delta: float):
    L, J, G = P.shape
    Ui = inv_floor_matrix(L, alpha)
    Vi = inv_floor_matrix(J, eta)
    Si = inv_floor_matrix(G, delta / G)
    W = mode_mult(mode_mult(mode_mult(P, Ui, 0), Vi, 1), Si, 2)

    Z = mode_mult(mode_mult(P, Vi, 1), Si, 2)
    if W.min() < -1e-9 or Z.min() < -1e-9:
        return None

    Ht = h_y_given_t(P)
    Hz = 0.0
    hz = np.zeros_like(Z)
    for y in range(L):
        for j in range(J):
            for k in range(G):
                lam = Z[:, j, k].sum()
                if Z[y, j, k] > 0 and lam > 0:
                    hz[y, j, k] = -math.log2(Z[y, j, k] / lam)
                    Hz += Z[y, j, k] * hz[y, j, k]
    lower = Ht - Hz

    vertex = np.full(L, alpha)
    vertex[0] = 1 - (L - 1) * alpha
    upper = Ht - entropy(vertex)

    # Influence functions on the observable cells.
    py_t = P.sum(axis=1)
    pt = py_t.sum(axis=0)
    hp = np.zeros((L, G))
    for y in range(L):
        for t in range(G):
            if py_t[y, t] > 0:
                hp[y, t] = -math.log2(py_t[y, t] / pt[t])

    Dh = np.zeros_like(P)
    for y in range(L):
        for m in range(J):
            for t in range(G):
                Dh[y, m, t] = sum(
                    Vi[j, m] * Si[k, t] * hz[y, j, k]
                    for j in range(J) for k in range(G)
                )

    phi_l = np.zeros_like(P)
    phi_u = np.zeros_like(P)
    for y in range(L):
        for m in range(J):
            for t in range(G):
                phi_l[y, m, t] = (hp[y, t] - Ht) - (Dh[y, m, t] - Hz)
                phi_u[y, m, t] = hp[y, t] - Ht

    var_l = float((P * phi_l**2).sum())
    var_u = float((P * phi_u**2).sum())
    return lower, upper, W, var_l, var_u


def latent_gamma(pi, q, r, s) -> float:
    # I(Y;E|T) = H(Y|T) - H(Y|E), since Y independent of T given E.
    P = sum(pi[e] * np.einsum("i,j,k->ijk", q[e], r[e], s[e]) for e in range(len(pi)))
    return h_y_given_t(P) - sum(pi[e] * entropy(q[e]) for e in range(len(pi)))


# Interior population model.
L = J = G = 2
alpha = float(CONFIG["alpha"])
eta = float(CONFIG["eta"])
true_delta = float(CONFIG["true_delta"])
U = floor_matrix(L, alpha)
V = floor_matrix(J, eta)
S = floor_matrix(G, true_delta / G)

pi = np.asarray(CONFIG["latent_weights"], dtype=float)
a_coord = np.asarray(CONFIG["outcome_extreme_coordinates"], dtype=float)
b_coord = np.asarray(CONFIG["proxy_extreme_coordinates"], dtype=float)
c_coord = np.asarray(CONFIG["report_extreme_coordinates"], dtype=float)
q = (U @ a_coord.T).T
r = (V @ b_coord.T).T
s = (S @ c_coord.T).T
P = sum(pi[e] * np.einsum("i,j,k->ijk", q[e], r[e], s[e]) for e in range(len(pi)))
true_gamma = latent_gamma(pi, q, r, s)
witness = cmi_y_m_given_t(P)

# Max compatible delta by bisection under fixed alpha, eta.
lo, hi = 0.0, 0.999999
for _ in range(70):
    mid = (lo + hi) / 2
    if endpoints(P, alpha, eta, mid) is not None:
        lo = mid
    else:
        hi = mid
delta_max = lo

# Sensitivity curves.
deltas = np.linspace(0.0, delta_max * 0.995, int(CONFIG["sensitivity_points"]))
lower_vals, upper_vals, widths, kappas = [], [], [], []
Vi = inv_floor_matrix(J, eta)
for d in deltas:
    ep = endpoints(P, alpha, eta, float(d))
    lower_vals.append(ep[0])
    upper_vals.append(ep[1])
    widths.append(ep[1] - ep[0])
    Si = inv_floor_matrix(G, d / G)
    kappas.append(np.linalg.norm(Vi, 1) * np.linalg.norm(Si, 1))

with (DATA / "simulation_population.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["alpha", "eta", "true_delta", "delta_max", "witness_bits", "true_gamma_bits", "true_lower_bits", "true_upper_bits"])
    w.writeheader()
    ep0 = endpoints(P, alpha, eta, true_delta)
    w.writerow({
        "alpha": alpha, "eta": eta, "true_delta": true_delta,
        "delta_max": delta_max, "witness_bits": witness,
        "true_gamma_bits": true_gamma, "true_lower_bits": ep0[0], "true_upper_bits": ep0[1],
    })

fig, ax = plt.subplots(figsize=(7.0, 4.5))
ax.plot(deltas, lower_vals, label="sharp lower endpoint")
ax.plot(deltas, upper_vals, label="sharp upper endpoint")
ax.axhline(true_gamma, linestyle="--", label="true latent gap")
ax.axhline(witness, linestyle=":", label="observable witness")
ax.set_xlabel("assumed report overlap $\\delta$")
ax.set_ylabel("information (bits)")
ax.set_title("Population identified interval under stronger report overlap")
ax.legend()
fig.tight_layout()
fig.savefig(FIG / "simulation_identification.png", dpi=int(CONFIG["figure_dpi"]))
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.0, 4.5))
ax.plot(deltas, widths, label="identified-set width")
ax.set_xlabel("assumed report overlap $\\delta$")
ax.set_ylabel("width (bits)")
ax2 = ax.twinx()
ax2.plot(deltas, kappas, linestyle="--", label="decontamination operator bound")
ax2.set_ylabel("operator-norm bound")
lines = ax.get_lines() + ax2.get_lines()
ax.legend(lines, [line.get_label() for line in lines], loc="best")
ax.set_title("Identification--stability trade-off")
fig.tight_layout()
fig.savefig(FIG / "simulation_stability.png", dpi=int(CONFIG["figure_dpi"]))
plt.close(fig)

# Interior endpoint inference simulation.
cells = np.array([(y, m, t) for y in range(L) for m in range(J) for t in range(G)])
probs = np.array([P[tuple(c)] for c in cells])
truth = endpoints(P, alpha, eta, true_delta)
true_lower, true_upper = truth[0], truth[1]
rows = []
for n in CONFIG["sample_sizes"]:
    n = int(n)
    R = int(CONFIG["replicates"])
    lower_est, upper_est = [], []
    cover_lower = cover_upper = cover_set = valid = 0
    z = norm.ppf(1.0 - (1.0 - float(CONFIG["confidence_level"])) / 2.0)
    for _ in range(R):
        counts = RNG.multinomial(n, probs)
        Phat = np.zeros_like(P)
        for c, count in zip(cells, counts):
            Phat[tuple(c)] = count / n
        ep = endpoints(Phat, alpha, eta, true_delta)
        if ep is None:
            continue
        valid += 1
        lohat, uphat, _, vl, vu = ep
        sel, seu = math.sqrt(max(vl, 0) / n), math.sqrt(max(vu, 0) / n)
        lower_est.append(lohat)
        upper_est.append(uphat)
        cover_lower += int(lohat - 1.96 * sel <= true_lower <= lohat + 1.96 * sel)
        cover_upper += int(uphat - 1.96 * seu <= true_upper <= uphat + 1.96 * seu)
        cover_set += int((lohat - z * sel <= true_lower) and (true_upper <= uphat + z * seu))
    lower_est = np.asarray(lower_est)
    upper_est = np.asarray(upper_est)
    rows.append({
        "n": n,
        "replicates": R,
        "compatible_fraction": valid / R,
        "mean_lower": lower_est.mean(),
        "mean_upper": upper_est.mean(),
        "rmse_lower": float(np.sqrt(np.mean((lower_est - true_lower)**2))),
        "rmse_upper": float(np.sqrt(np.mean((upper_est - true_upper)**2))),
        "pointwise_coverage_lower": cover_lower / valid,
        "pointwise_coverage_upper": cover_upper / valid,
        "outer_set_coverage": cover_set / valid,
    })

with (DATA / "simulation_coverage.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

fig, ax = plt.subplots(figsize=(7.0, 4.5))
ns = [r["n"] for r in rows]
ax.plot(ns, [r["pointwise_coverage_lower"] for r in rows], marker="o", label="lower endpoint")
ax.plot(ns, [r["pointwise_coverage_upper"] for r in rows], marker="o", label="upper endpoint")
ax.plot(ns, [r["outer_set_coverage"] for r in rows], marker="o", label="outer identified-set region")
ax.axhline(0.95, linestyle="--", label="nominal 0.95")
ax.set_ylim(0.88, 1.005)
ax.set_xlabel("sample size")
ax.set_ylabel("coverage")
ax.set_title("Interior influence-function inference")
ax.legend()
fig.tight_layout()
fig.savefig(FIG / "simulation_coverage.png", dpi=int(CONFIG["figure_dpi"]))
plt.close(fig)

print("Population:")
print({"witness": witness, "true_gamma": true_gamma, "delta_max": delta_max,
       "lower": true_lower, "upper": true_upper})
print("Coverage:")
for row in rows:
    print(row)

output_hashes = {}
for path in sorted(ROOT.rglob("*")):
    if path.is_file():
        output_hashes[path.relative_to(ROOT).as_posix()] = sha256_file(path)
manifest = {
    "schema_version": 1,
    "run_id": CONFIG["run_id"],
    "seed": int(CONFIG["seed"]),
    "config_sha256": sha256_file(CONFIG_PATH),
    "script_sha256": sha256_file(Path(__file__)),
    "python": platform.python_version(),
    "numpy": np.__version__,
    "scipy": __import__("scipy").__version__,
    "matplotlib": __import__("matplotlib").__version__,
    "reproduction_timezone": "UTC",
    "argv": sys.argv,
    "outputs": output_hashes,
}
with (ROOT / "manifest.json").open("w", encoding="utf-8", newline="\n") as handle:
    json.dump(manifest, handle, ensure_ascii=False, sort_keys=True, indent=2)
    handle.write("\n")
