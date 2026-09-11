# Canonical results

This directory contains the frozen outputs used by the manuscript experiment
commit identified in `manuscript_binding/LOCAL_PAPER_BINDING.json`.

- `simulation/`: population values, finite-sample coverage, and generated
  figures.
- `meld/`: grouped folds, out-of-fold predictions, predictive gains,
  stability and subgroup tables, exploratory endpoints, and figures.
- `empirical/nhanes/`: formal NHANES witness and sharp-sensitivity outputs.
- `empirical/crosscheck/`: formal CrossCheck witness and
  sharp-sensitivity outputs.
- `floor_diagnostics/`: canonical NHANES boundary screen and explicitly
  exploratory representation-coarsening diagnostics.

Canonical files must not be overwritten by a rerun. The commands in
`docs/REPRODUCTION_PROTOCOL.md` write to `rerun_results/`; verifier scripts
then compare those candidates with this directory.
