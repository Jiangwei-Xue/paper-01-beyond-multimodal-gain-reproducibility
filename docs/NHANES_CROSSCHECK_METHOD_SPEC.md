# NHANES and CrossCheck method specification

## Frozen formal analysis

Protocol `nhanes-crosscheck-formal-v1` was frozen on 2026-09-05 with seed
`2026090501`. Every declared witness analysis uses 1,000 cluster bootstrap and
1,000 conditional-permutation replicates.

NHANES combines the 2003--2004 and 2005--2006 examination cycles. The primary
outcome is death within 120 months of examination; the robustness outcome uses
60 months. The report is four-level PAQ180. The proxy is valid-wear
accelerometer counts per minute, discretized into two, three, or four weighted
quantile bins. The primary specification uses four bins and context equal to
sex crossed with age below or at least 60. Pooled examination weights are
`WTMEC2YR / 2`; bootstrap resampling uses PSUs within cycle-specific survey
strata. The finite table directly estimates `I(Y; M | T, C)`.

CrossCheck forms adjacent assessments separated by one to seven days. The
report is the current negative-symptom EMA tertile, the proxy is a tertile of a
four-sensor composite, the outcome is the next EMA tertile, and context records
sensing quality. Each participant receives equal total weight and is the
bootstrap unit.

## Positive-floor boundary

The canonical NHANES `4M x 4T x 4C` table has empirical empty cells. No
pseudocounts or probability smoothing are used. The public package includes:

- a conservative PSU-block simultaneous `l1` outer compatibility screen;
- post-canonical coarsening diagnostics with seed `2026090502`.

The screen does not reject the declared positive-floor grid but certifies no
point because its radii are wide. The coarsened diagnostics change the estimand
and are representation-sensitivity analyses. Neither supplies scientific
calibration for a positive channel floor.

## Public replay boundary

The compact inputs contain the variables needed for downstream statistical
replay. The NHANES table contains package-local rows, survey design variables,
weights, discrete analysis variables, and outcomes. The CrossCheck table
contains package-local rows and participant-cluster labels, weights, and finite
analysis variables. The optional upstream builder reconstructs NHANES from
PAXRAW minutes and public survey/mortality records, and CrossCheck from its
published cleaned daily table. The frozen wear-time rules, filters, weighted
cutpoints, and joins are in `upstream/processing_config.R` and
`upstream/build_empirical_inputs.R`. Raw CrossCheck sensor cleaning is not
reimplemented.
