# Experiment design

## Research role of the package

The package separates an observable predictive witness,
`I(Y; M | T, C)`, from latent-state information that is only partially
identified. It contains one simulation family and three real-data analyses.
The analyses use no generative-model API, agent workflow, prompt, or AI judge.

## Experiment matrix

| Experiment | Purpose | Public input | Baseline/control | Grouping or sampling unit | Frozen randomness | Main output |
|---|---|---|---|---|---|---|
| Population simulation | Check population sharp bounds and stability as channel restrictions vary | Parameters in `config/simulation.json` | Observable witness and unrestricted endpoints | Exact finite distribution | seed 20260901 | `simulation_population.csv` |
| Finite-sample simulation | Evaluate endpoint error and interval coverage | Simulated samples from the frozen DGP | Population values from the same DGP | Independent Monte Carlo replicate | seed 20260901; 1,500 replicates at each sample size | `simulation_coverage.csv` |
| MELD | Test next-turn sentiment gain beyond source-turn text | Two aligned compact pair tables | Text-only nested grouped model | Dialogue | seed 20260901; 5 outer folds; 4 inner folds; 10,000 multiplier draws | `primary_predictive_gain.csv` |
| NHANES | Estimate an objective-activity witness beyond self-report | Compact public-use survey table | Conditional entropy/unrestricted zero-floor benchmark | PSU within cycle-specific survey stratum | seed 2026090501; 1,000 bootstrap and permutation replicates | `nhanes/witness_results.csv` |
| NHANES floor diagnostics | Evaluate compatibility at positive channel floors | Same compact NHANES table | Canonical unsmoothed finite table | PSU block and representation-specific bootstrap | seed 2026090502; 1,000 replicates | `floor_diagnostics/` |
| CrossCheck | Test next-assessment symptom gain from mobile sensing | Compact adjacent-assessment pairs | Current-report-only finite table | Participant | seed 2026090501; 1,000 bootstrap and permutation replicates | `crosscheck/witness_results.csv` |

## Variables and controls

### MELD

- `Y`: three-class next-turn sentiment.
- `T`: 32-dimensional source-turn text SVD representation.
- `M`: 16 audio PCA components, 32 visual PCA components, or their
  concatenation.
- `C`: major-character and same-speaker indicators.
- Control: text-only model.
- Leakage control: every outer and inner split is grouped by dialogue;
  preprocessing is fitted only in each training fold.

### NHANES

- `Y`: death within 120 months; 60 months is a robustness outcome.
- `T`: four-level self-reported activity.
- `M`: accelerometer counts-per-minute category with two, three, or four
  weighted-quantile bins; four bins is primary.
- `C`: sex crossed with age below or at least 60.
- Survey weights: pooled `WTMEC2YR / 2`.
- Resampling: PSUs within cycle-specific survey strata.

### CrossCheck

- `Y`: next negative-symptom EMA tertile.
- `T`: current EMA tertile.
- `M`: tertile of the four-sensor composite.
- `C`: sensing-quality category.
- Each participant receives equal total weight and is the resampling unit.

## Prespecified and exploratory components

- The primary MELD full-sample modality gains are confirmatory stress-test
  outputs for the frozen model class.
- MELD same-speaker and general-T endpoints are exploratory.
- NHANES primary and horizon/bin robustness rows belong to the frozen formal
  protocol.
- NHANES representation coarsening is post-canonical exploratory sensitivity
  analysis and changes the estimand.
- CrossCheck is participant-clustered and inconclusive under its primary
  interval.

## Aggregation and inference

- Predictive gains and witnesses are reported in bits.
- MELD uncertainty uses dialogue-level Rademacher multiplier inference.
- NHANES and CrossCheck use cluster bootstrap inference at their declared
  independent units.
- Compatibility, `delta_max`, and sharp sensitivity grids use the frozen
  values in `config/`.
- The package uses the frozen canonical outputs listed in the experiment
  manifest; reference files are read only by the verification stage.

## Public replay boundary

The released inputs are compact derivatives. Downstream analysis, aggregation,
tables, and figures are replayable without source downloads. The optional
`upstream/` route reconstructs the four input tables from pinned public MELD
sequence features, NHANES minute/survey/mortality records, and the public cleaned
CrossCheck daily table. Raw-media neural feature extraction and raw-phone-sensor
cleaning are outside that route. It introduces no new estimand or experiment.
