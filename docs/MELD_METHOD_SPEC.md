# Canonical MELD real-data method specification

## Scope

This document freezes the real-data MELD analysis used as a negative/control
stress test. The repository also reproduces the paper's simulation section,
but CREMA-D, historical pilot outputs, and planned experiments are outside the
current manuscript package. It contains no transcript text, raw audio, raw
video, or pre-reduction continuous embeddings.

## Observations and variables

- 2,330 adjacent-turn pairs from 268 dialogues.
- Outcome: next-turn official MELD sentiment with three classes.
- Report representation: 32 source-turn text SVD components.
- Non-report representations: 16 audio PCA components, 32 visual PCA
  components, and their concatenation.
- Context: source speaker major-character indicator and next-turn same-speaker
  indicator.
- Grouping unit: dialogue identifier.

The continuous and discrete tables must have identical dialogue, source key,
target key, and outcome columns in identical row order. The driver fails closed
when they do not.

## Predictive protocol

- Primary seed: 20260901.
- Outer splitting: 5-fold `StratifiedGroupKFold`, grouped by dialogue.
- Inner tuning: 4-fold `StratifiedGroupKFold` within each outer training fold.
- Learner: multinomial ridge logistic regression with `lbfgs`.
- Fold-local preprocessing: `StandardScaler` fitted on each model-training
  fold.
- Ridge grid: `1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1`.
- Base and augmented models are tuned separately; the base OOF fit is reused
  across modalities within one run.
- Score: row-level base-2 log probability difference for the observed class.
- Probability clipping: `1e-12`.

The exact outer fold assignment for each observation is stored in
`canonical_results/meld/oof_predictions.csv`. Fold sizes, selected ridge
values, and full inner-grid losses are stored under
`canonical_results/meld/folds/`.

## Cluster inference

For each dialogue, centered row scores are summed. Ten thousand independent
Rademacher multiplier draws are applied to dialogue sums. The two-sided 95%
interval uses the 95th percentile of the absolute multiplier statistic. The
modality-specific multiplier seeds are the analysis seed plus 1000, 1001, and
1002 for audio, visual, and fused inputs.

The same-speaker analysis refits the entire nested grouped protocol on the 565
same-speaker pairs. It is exploratory.

## Stability and representation ladder

- Repeated split seeds: 11, 23, 37, 53, 71, 89, 107, 131.
- Text dimensions: 4, 8, 16, and 32 leading SVD components.
- Every setting reruns the full nested grouped procedure.

## Continuous-report model-based calculation

For each modality, the four-cluster proxy is combined with the three-class
outcome into a 12-class joint label. Dialogue-grouped nested multinomial models
estimate row-wise `P(Y,M|R,C)`. The report overlap parameter is fixed at
`delta=0`. These are model-based point functionals, not confidence-valid
population identified-set intervals.

## Frozen software

The canonical run used Python 3.14.5, NumPy 2.5.2, SciPy 1.18.1,
scikit-learn 1.9.0, and Matplotlib 3.11.1. `requirements-lock.txt` records the
complete local environment used by the run.
