# Contamination and leakage audit

## Scope and decision

Scope: the compact-input pipelines and optional reconstruction from published
MELD features, NHANES minutes, and the public cleaned CrossCheck table.

Decision: **PASS_WITH_DOCUMENTED_BOUNDARY**. No downstream split leakage, output reuse, test-label transform fitting, or presentation/raw-media leakage was found. The MELD train-only transforms and empirical input builders are executable;
external source objects are checked before use. Neural media extraction and
raw mobile-sensor cleaning are outside scope.

## Data lineage

| Stage | Evidence | Status |
|---|---|---|
| Upstream MELD annotations/features | frozen commits and source SHA-256 values | retained-hash evidence |
| Feature transforms | executable train-only, label-free fitting; exact rebuilt CSV comparison | pass |
| Public compact inputs | 2,330 aligned pairs, 268 dialogues; SHA-256 frozen in config | pass |
| Outer validation | each dialogue appears in exactly one OOF test fold | pass |
| Inner tuning | `StratifiedGroupKFold`, fixed seed, train portion only | pass |
| OOF predictions | one row per pair with frozen fold and three modality scores | pass |
| Tables/figures | generated from OOF/model outputs and hash-bound | pass |
| NHANES compact rows | survey strata, PSU labels, weights, and discrete analysis variables retained | pass |
| NHANES inference | PSUs resampled within cycle-specific survey strata | pass |
| CrossCheck compact rows | finite variables, weights, row order, and participant-cluster labels retained | pass |
| CrossCheck inference | participant remains the independent resampling unit | pass |

## Leakage checks

- Split overlap: no dialogue is assigned to more than one outer test fold.
- Label exposure: the target labels are used for training and scoring only inside the declared cross-validation procedure. They are not used to fit TF-IDF/SVD/PCA/scalers/K-means by the executable upstream transform code.
- Preprocessing: fold-local `StandardScaler` is inside the predictive pipeline; hyperparameter selection uses only inner training folds.
- Output reuse: the analysis script does not read `canonical_results/`; those files are reference outputs used only by verification.
- Benchmark pollution: not applicable to model pretraining. MELD is used as an explicit evaluation dataset, not as hidden model training data.
- Input boundary: transcripts, media, and pre-PCA MM-Align vectors are outside
  the downstream MELD replay.
- Outcome reuse: NHANES/CrossCheck scripts read compact inputs but never read
  canonical result files; canonical outputs are used only by the separate
  verifier.
- Positive-floor diagnostics: no pseudocount or outcome-guided smoothing is
  applied. Post-canonical coarsenings are labelled exploratory and are not
  substituted for the frozen primary estimand.

## Supported scope

The downstream canonical MELD, NHANES, CrossCheck, and simulation results are
rerunnable from the compact public inputs in their declared environments.

The optional upstream route replays NHANES minute processing and the declared
MELD/CrossCheck transforms. It does not independently replay neural raw-media
feature extraction or CrossCheck raw sensor cleaning, audit the pretrained
feature models' training corpora, or expand source redistribution rights.
