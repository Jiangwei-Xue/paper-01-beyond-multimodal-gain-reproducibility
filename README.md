# Beyond Multimodal Gain: minimal reproduction package

This repository reproduces every empirical and simulation result reported in
the included current manuscript for **Beyond Multimodal Gain: Sharp
Partial Identification of Task-Relevant Latent-State Information**.

It covers:

1. population and finite-sample sharp-identification simulations;
2. NHANES survey-weighted finite-table witnesses, horizon and representation
   checks, and positive-floor boundary diagnostics without pseudocounts;
3. the CrossCheck participant-clustered longitudinal witness; and
4. the canonical MELD next-turn sentiment analysis, including the primary
   analysis, eight-seed stability, same-speaker subgroup, representation
   ladder, and exploratory general-T endpoints.

The repository includes the exact manuscript PDF bound to these results at
[`paper/Beyond_Multimodal_Gain.pdf`](paper/Beyond_Multimodal_Gain.pdf). It does
not contain the LaTeX source, raw transcripts, audio, video, high-dimensional
MM-Align features, or NHANES minute-level PAXRAW files. The analysis payload
contains compact inputs for downstream statistical replay. The optional
`upstream/` pipeline downloads frozen public sources and reconstructs all four
compact CSVs; large source files remain in an ignored local work directory.

This is release `bmg-minimal-reproduction-v1.9.0`. The analysis timezone is
fixed to UTC, and all scientific inputs, configurations, reference outputs,
and comparison tolerances used by the downstream replay are versioned here.

## Start here

Run the dependency-free package validation:

```bash
python3 analysis/verify_static_package.py --root .
```

Expected result: `PACKAGE_VALIDATION` is `PASS`.

The full execution order and environment setup are in
[`docs/REPRODUCTION_PROTOCOL.md`](docs/REPRODUCTION_PROTOCOL.md). The experiment
matrix is in [`docs/EXPERIMENT_DESIGN.md`](docs/EXPERIMENT_DESIGN.md), and the
paper-to-result mapping is in
[`manuscript_binding/PAPER_RESULTS_MAP.json`](manuscript_binding/PAPER_RESULTS_MAP.json).

After creating the two Python environments described in the protocol, the
complete downstream replay is:

```bash
TZ=UTC make verify-full
```

This command regenerates and verifies all simulation, MELD, NHANES,
CrossCheck, and floor-diagnostic outputs. It does not reconstruct compact
inputs. For source reconstruction, follow
[`docs/UPSTREAM_REPRODUCTION.md`](docs/UPSTREAM_REPRODUCTION.md). That route
covers published MELD sequence features, NHANES minute records, and the public
cleaned CrossCheck daily table, then runs the same result comparators.

## Repository map

```text
upstream/                 source acquisition, reconstruction, and comparison
analysis/                 analysis, aggregation, and verification code
config/                   frozen seeds, folds, grids, and simulation DGP
input_data/               compact MELD, NHANES, and CrossCheck inputs
canonical_results/meld/   MELD tables, figures, folds, OOF scores, manifest
canonical_results/simulation/
                          simulation tables, figures, and manifest
canonical_results/empirical/
                          NHANES and CrossCheck formal tables
canonical_results/floor_diagnostics/
                          NHANES boundary and sensitivity tables
manuscript_binding/       paper location to result-artifact mapping
paper/                    exact manuscript PDF; author copyright retained
docs/                     design, methods, protocol, provenance, and validation
provenance/               public scientific artifact manifest and checksums
LICENSES/                 license texts and authoritative references
```

## Frozen public identities

- Public release: `bmg-minimal-reproduction-v1.9.0`
- Included manuscript PDF SHA-256:
  `084eda01edd19e7e73c7b20ee6e51726861ca8f27a38fd93c193c5127b291ed2`
- Simulation run: `sharp-id-simulation-20260901-v1`, seed `20260901`
- MELD run: `meld-realdata-reproduction-20260901-v1`, seed `20260901`
- NHANES/CrossCheck protocol: `nhanes-crosscheck-formal-v1`, seed
  `2026090501`
- NHANES positive-floor diagnostics: seed `2026090502`

## Result boundaries

- MELD is a dialogue-grouped negative/control stress test: the primary audio,
  visual, and fused 95% cluster intervals all include zero.
- NHANES has a positive observable witness. It is not a causal effect and does
  not identify the magnitude of latent-state information.
- The NHANES zero-floor interval is an unrestricted benchmark. Positive floors
  were neither rejected by the low-power outer screen nor scientifically
  calibrated.
- The CrossCheck participant-bootstrap interval includes zero, so its
  participant-clustered conclusion is inconclusive.
- Same-speaker MELD and general-T endpoint calculations are exploratory.
- Downstream calculations are self-contained from compact public inputs.
  Optional reconstruction needs about 3 GiB of external downloads and a
  recommended 20 GiB of free disk space. MELD raw-media neural feature
  extraction and CrossCheck raw-phone-sensor cleaning remain outside scope.
- No model API or generated-model output enters the reported computation. VCR,
  HDF5, and E5 are not part of the frozen method and are recorded as not
  applicable in `docs/VALIDATION_APPLICABILITY.md`.

## Licensing

This repository uses layered licensing:

- project documentation and author-generated derived result artifacts:
  **CC BY 4.0**;
- analysis code and executable configuration: **MIT License**;
- the manuscript PDF under `paper/`: author copyright retained;
- third-party libraries, public-source data, derived compact inputs, and any
  model outputs: their original terms apply.

See [`LICENSE`](LICENSE) and
[`docs/DATA_LICENSE_AND_PROVENANCE.md`](docs/DATA_LICENSE_AND_PROVENANCE.md) for
the exact path-level scope. No license in this repository expands upstream
rights.

## Formal archive verification

Public archives must be built by the `experiment-release` workflow. Verify a
downloaded release archive with:

<!-- RELEASE_COMMAND:verify -->
```bash
python3 tools/VERIFY_ARCHIVE.py verify --archive <ARCHIVE_PATH> --public
```
<!-- END_RELEASE_COMMAND:verify -->

Archive verification checks package integrity, the documented interface,
deterministic construction, and the scientific reproduction contract. The
scientific validation scope is reported in `docs/RELEASE_AUDIT.md`.
