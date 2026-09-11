# Reproduction protocol

## 1. Requirements

- Python 3.11 for the simulation environment.
- Python 3.14 for the frozen MELD environment.
- R 4.6.1 base packages for NHANES and CrossCheck.
- Sufficient local space for two Python virtual environments and rerun output.

Set `TZ=UTC` for every command. Host timezone is not part of the method.
`PUBLIC_ENVIRONMENT.json` records the tested runtime scope.

The compact-input route below does not require raw video, audio, PAXRAW,
or private source data. An optional upstream route is documented in
`docs/UPSTREAM_REPRODUCTION.md`.

## 2. Static validation

```bash
TZ=UTC python3 analysis/verify_static_package.py --root .
```

This checks required scientific files, compact input dimensions and row
counts, group-fold isolation, canonical manifests, paper binding, and public
artifact-manifest closure.

## 3. Simulation

```bash
TZ=UTC python3.11 -m venv .venv-sim
.venv-sim/bin/python -m pip install -r requirements-simulation-lock.txt
.venv-sim/bin/python analysis/run_simulation.py \
  --config config/simulation.json \
  --output-dir rerun_results/simulation
.venv-sim/bin/python analysis/verify_simulation_rerun.py \
  --reference canonical_results/simulation \
  --candidate rerun_results/simulation
```

Expected: 48 numerical cells agree within `1e-12`. PNGs are compared by
dimensions and pixel content because font stacks can alter byte-level output.

## 4. MELD

```bash
python3.14 -m venv .venv-meld
.venv-meld/bin/python -m pip install -r requirements-lock.txt
TZ=UTC PYTHONWARNINGS="ignore::FutureWarning" .venv-meld/bin/python \
  analysis/run_meld_reproduction.py \
  --config config/meld_reproduction.json \
  --data-dir input_data \
  --output-dir rerun_results/meld
.venv-meld/bin/python analysis/verify_meld_rerun.py \
  --reference canonical_results/meld \
  --candidate rerun_results/meld \
  --tolerance 1e-10
```

Expected: `RERUN_NUMERICAL_STATUS=PASS` and all 111 checked numerical cells
agree.

## 5. NHANES and CrossCheck

```bash
TZ=UTC Rscript analysis/run_empirical_reproduction.R \
  . rerun_results/empirical
TZ=UTC Rscript analysis/run_nhanes_floor_diagnostics.R \
  . rerun_results/floor_diagnostics
Rscript analysis/verify_empirical_rerun.R \
  canonical_results/empirical rerun_results/empirical
Rscript analysis/verify_empirical_rerun.R \
  canonical_results/floor_diagnostics rerun_results/floor_diagnostics
```

Expected: both verification commands report
`EMPIRICAL_REPROCHECK_IDENTICAL=PASS`.

## 6. Archive verification

```bash
python3 tools/VERIFY_ARCHIVE.py verify --archive <ARCHIVE_PATH>
```

Expected: `PACKAGE VALIDATION: PASS`.

## 7. One-command downstream replay

After the environments above are installed:

```bash
TZ=UTC make verify-full
```

This executes static validation, all four result-generating chains, numerical
or byte-level comparisons, and a post-run static validation. It makes no
network request during analysis. Dependency installation is the only step that
may use the network.

## 8. Result interpretation

Use `manuscript_binding/PAPER_RESULTS_MAP.json` to connect manuscript tables
and figures to canonical artifacts. See `docs/EXPERIMENT_DESIGN.md` for
confirmatory/exploratory status and `docs/DATA_LICENSE_AND_PROVENANCE.md` for
raw-data and license boundaries.

## 9. Scope boundary

The complete downstream path from compact inputs to every packaged table and
figure is executable. The optional upstream route reconstructs inputs from
separately acquired MELD sequence features, NHANES PAXRAW and survey/mortality
files, and the public cleaned CrossCheck daily table. It does not extract neural
features from MELD media or clean raw CrossCheck phone-sensor streams.
