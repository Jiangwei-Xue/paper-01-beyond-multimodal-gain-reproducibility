# Hash interlock report

## Decision

**PASS_WITH_DOCUMENTED_BOUNDARY** for a minimal public reproduction package.

- MELD downstream chain: compact input hashes, exact code/config, environment,
  outer folds, tuning records, OOF predictions, summaries, figures, and a
  duplicate rerun are linked.
- MELD published-feature-to-compact transition: pinned source hashes and
  executable train-only transforms reconstruct both CSVs; large sources are
  downloaded separately. Raw-media neural extraction is outside scope.
- Simulation numeric chain: code/config/seed/environment reproduce all 48
  compared numeric cells within `1e-12`.
- Simulation raster chain: canonical PNG bytes depend on fonts/rendering;
  verification checks dimensions and bounded pixel-content drift.
- NHANES/CrossCheck downstream chain: compact row tables, fixed seeds,
  cluster identifiers, weights, code, configs, bootstrap draws, sensitivity
  tables, and duplicate reruns are linked.
- NHANES minute-to-compact and CrossCheck cleaned-daily-to-compact transitions:
  executable builders and source hashes are included; source data are external.
  Scientific-cell equality and cluster-partition equality are checked.

## Chain inventory

```text
MELD pinned public sequence features + CSVs + executable transforms
  -> compact input metadata + compact CSV hashes
  -> meld config + analysis code + locked environment
  -> fold/tuning manifests + OOF scores
  -> primary / stability / subgroup / ladder / general-T tables
  -> manuscript figures + PAPER_RESULTS_MAP.json

simulation config + code + Python 3.11 / NumPy 1.26.4 lock
  -> population and 1,500-replicate coverage tables
  -> three manuscript figures
  -> PAPER_RESULTS_MAP.json

NHANES minute/survey/mortality records or CrossCheck cleaned daily CSV
  -> upstream R/C builder + compact scientific-cell/cluster comparison
  -> public NHANES/CrossCheck rows + R config + base-R analysis code
  -> cluster bootstrap and conditional-permutation outputs
  -> observable-witness and sharp-sensitivity tables
  -> boundary and post-canonical floor diagnostics
  -> PAPER_RESULTS_MAP.json
```

## Mechanical checks

- Broken hash links: 0 after manifest generation and verification.
- Missing required artifacts: 0.
- Duplicate run IDs: 0 (`sharp-id-simulation-20260901-v1`, `meld-realdata-reproduction-20260901-v1`).
- Conflicting hashes for the same canonical path: 0.
- MELD numerical rerun: 111/111 cells, maximum absolute difference 0.
- Simulation numerical rerun: 48/48 cells within `1e-12`.
- Public NHANES/CrossCheck replay: all declared CSVs are checked by exact
  SHA-256 against a duplicate run.
- Orphan scientific artifacts: 0 among allowlisted tables, figures, inputs, folds, and OOF records.

## Public scientific artifacts

Only the files listed by the release allowlist are public. They contain the current-paper experiments, verification code, documentation, and hash manifests.

## Scope boundaries

The package does not contain MELD raw media, transcripts, high-dimensional
features, NHANES minute-level PAXRAW, or CrossCheck continuous source
measurements. CREMA-D is not reported in the current manuscript and is outside
the experiment inventory.

The optional reconstruction interface is described in
`docs/UPSTREAM_REPRODUCTION.md`. Neither successful computation nor hash
matching resolves upstream licensing questions.
