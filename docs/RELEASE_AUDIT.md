# Scientific reproducibility release audit

## A. Scope

Release `bmg-minimal-reproduction-v1.9.0` supports full clean downstream
reproduction from the compact inputs included in the package, plus optional
reconstruction from frozen public starting files. It covers the
population and finite-sample simulations, NHANES, CrossCheck, and the canonical
MELD analyses mapped in `manuscript_binding/PAPER_RESULTS_MAP.json`.

The optional chain covers published MELD sequence features to compact pairs,
NHANES minute/survey/mortality files to analysis rows, and public cleaned
CrossCheck daily data to finite pairs. Neural media feature extraction and
original phone-sensor cleaning remain outside scope. See
`docs/UPSTREAM_REPRODUCTION.md`.

## B. Experiment inventory

- Population sharp-identification simulation.
- Finite-sample coverage and stability simulation.
- NHANES primary and robustness witnesses, boundary screen, and positive-floor
  representation sensitivity.
- CrossCheck participant-clustered witness.
- MELD primary grouped nested cross-validation, eight-seed stability,
  same-speaker subgroup, representation ladder, and exploratory general-T
  endpoints.

Reference inputs are under `input_data/`; frozen configurations are under
`config/`; reference outputs are under `canonical_results/`.

## C. Experimental-design completeness

The research questions, estimands, controls, experiment matrix, confirmatory
and exploratory status, seeds, resampling units, folds, grids, and evaluation
rules are stated in `docs/EXPERIMENT_DESIGN.md` and the method specifications.
The machine-readable inventory is `config/EXPERIMENT_MANIFEST.json`.

## D. Reproduction scaffolding

The package contains setup instructions, frozen dependency files, data readers,
result-generating runners, aggregation code, figure and table generation,
reference outputs, and result comparators. `Makefile` provides both staged
targets and `make verify-full`.

## E. Data and input provenance

- MELD: 2,330 next-turn pairs from 268 dialogues, with 32 text-SVD, 16
  audio-PCA, and 32 visual-PCA dimensions plus the discrete analysis table.
- NHANES: 6,565 analysis rows with survey strata, PSUs, weights, discrete
  self-report/activity variables, and mortality outcomes.
- CrossCheck: 5,607 longitudinal pairs from 60 participant clusters with the
  finite analysis variables and weights.
- Simulation: the complete data-generating process is specified in
  `config/simulation.json`.

Source repositories, dataset versions, source hashes where distributable, and
license boundaries are listed in `docs/DATA_LICENSE_AND_PROVENANCE.md`.

## F. Result provenance

The public artifact manifest links each input, configuration, runner, output,
and paper-facing artifact by relative path and SHA-256. MELD fold and tuning
manifests bind the grouped outer folds, inner tuning, and OOF predictions.
NHANES and CrossCheck outputs retain bootstrap replicates and sensitivity
tables. Simulation manifests retain the DGP, seed, tables, and figures.

## G. Dependencies and environment requirements

- Simulation: Python 3.11 with `requirements-simulation-lock.txt`.
- MELD: Python 3.14 with `requirements-lock.txt`.
- NHANES and CrossCheck analysis: R 4.6.1 base packages.
- Upstream NHANES: R `foreign` 0.8-91 and an R-compatible C compiler.
- Analysis timezone: UTC.

The tested scope is macOS on arm64. No native binary is distributed in the
package, but a broader operating-system compatibility claim has not been
independently tested.

## H. Validation and tests

The dependency-free package validator checks required scientific files,
input hashes, sample counts, feature dimensions, MELD row alignment and fold
isolation, run manifests, paper binding, and public manifest closure. The full
replay then runs each analysis and its corresponding numerical or byte-level
comparator.

VCR, HDF5, and E5 are not part of the frozen method. Their applicability is
explained in `docs/VALIDATION_APPLICABILITY.md`.

## I. Full reproduction

The compact-input interface is `TZ=UTC make verify-full`. The v1.9 extension
also regenerates the inputs and runs `upstream/run_from_rebuilt.py`, which
uses only those regenerated inputs for estimation. Fresh-environment and
clean-extraction checks exercise the following stages:

1. dependency-free package validation;
2. simulation generation and comparison;
3. MELD generation and numerical comparison;
4. NHANES and CrossCheck generation and exact comparison;
5. NHANES floor-diagnostic generation and exact comparison; and
6. a final package validation.

The scientific runners make no network request. Dependency installation and
optional source acquisition can use the network. All 13 frozen local source
objects passed their size/SHA-256 checks, and all nine small source objects
were freshly downloaded and verified. The three large source archive transfers
were not repeated; existing extracted objects were reused. This distinction
is recorded in `provenance/UPSTREAM_VALIDATION.json`.

## J. Result equivalence

- Simulation: 48 numerical cells agree within the frozen `1e-12` tolerance.
- MELD: all 111 compared numerical cells agree within `1e-10`; the observed
  maximum absolute difference is zero in the canonical rerun.
- NHANES and CrossCheck: all 10 declared empirical CSV files are identical to
  the references.
- NHANES floor diagnostics: all 12 declared CSV files are identical to the
  references.
- Simulation figures match their reference images pixel for pixel.

Input reconstruction also passed: both MELD CSVs and the NHANES CSV are
byte-identical to the references; CrossCheck scientific cells and row-wise
participant partitions match, with arbitrary label strings allowed to differ.
Four helper tests reject altered values, altered groups, and corrupted sources;
the synthetic C-kernel test matches its independent R reference.

## K. Figure and table provenance

Simulation and MELD figures are generated by the corresponding Python runners.
All paper-facing tables are generated by the MELD, simulation, or R analysis
entry points. The paper-result map lists the generating configuration, source
table, expected figure, and interpretive status of each item.

## L. Paper and result mapping

The included 41-page manuscript is built from the current local source and has
the declared title and author order recorded in `PUBLIC_ATTRIBUTION.json`. Its
extracted text and all 41 rendered pages match the source build. The package PDF
SHA-256 is
`084eda01edd19e7e73c7b20ee6e51726861ca8f27a38fd93c193c5127b291ed2`.

Every empirical table, simulation table, and figure reported in the manuscript
is mapped in `manuscript_binding/PAPER_RESULTS_MAP.json`.

## M. Archive and manifest integrity

The package is built from an explicit allowlist with normalized metadata and
two byte-identical builds. `provenance/PUBLIC_RELEASE_MANIFEST.jsonl` records
the scientific public files and their hashes. `RELEASE_METADATA/` provides the
archive member manifest, checksums, build attestation, documentation
attestation, and tool provenance.

## N. Scientific limitations and boundaries

This package establishes computational repeatability for the declared
compact-input and optional public-starting-file pipelines. It does not establish theoretical correctness,
independent scientific validity, external cross-platform reproduction, or
permission to redistribute any upstream dataset beyond its original terms.
The positive NHANES witness is not a causal effect or an identified latent
information magnitude. CrossCheck is inconclusive at the participant-clustered
level, and the primary MELD intervals include zero.

## O. Release decision

| Scientific check | Status | Public evidence |
|---|---|---|
| Experiment definition | PASS | design document and experiment manifest |
| Reproduction scaffolding | PASS | runners, Makefile, protocol, locks |
| Data provenance | PASS | data provenance document and compact inputs |
| Result provenance | PASS | run manifests and public artifact manifest |
| Dependency validation | PASS | frozen lock files and tested runtimes |
| Unit/helper validation | PASS | dependency-free package validator |
| Integration validation | PASS | four downstream result-generating chains |
| VCR | N/A | no HTTP/API cassette mechanism in the method |
| HDF5 | N/A | no HDF5 input or output in the method |
| E5 | N/A | no project-defined E5 layer in the method |
| Full downstream reproduction | PASS | `TZ=UTC make verify-full` |
| Result equivalence | PASS | declared numerical and exact comparisons |
| Figure/table provenance | PASS | runners and paper-result map |
| Paper/result mapping | PASS | paper binding and paper-result map |
| Manifest and archive integrity | PASS | final archive verification |
| Final package | PASS | final clean-extraction validation |

`PACKAGE VALIDATION: PASS`
