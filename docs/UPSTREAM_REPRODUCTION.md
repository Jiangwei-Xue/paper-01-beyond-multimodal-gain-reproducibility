# Optional upstream reconstruction

This route reconstructs all four compact input CSVs and reruns the reported
analyses. Large source objects are acquired separately; they are not included
in the GitHub upload. The existing compact-input route remains offline and
self-contained after dependency installation.

## 1. What is covered

| Dataset | Starting point | Reconstructed input | Remaining boundary |
|---|---|---|---|
| MELD | Published MM-Align train/test sequence features and pinned MELD CSVs | 2,330 continuous and discrete next-turn pairs | Neural feature extraction from original audio/video is not implemented |
| NHANES | Official 2003--2004 and 2005--2006 PAXRAW minute records, DEMO, PAQ, and 2019 public-use mortality files | 6,565 survey-analysis rows | No restricted mortality records are used |
| CrossCheck | Pinned public cleaned daily CSV | 5,607 pairs in 60 participant clusters | Cleaning original phone-sensor streams is not implemented |

The included manuscript PDF is unchanged from v1.8. Its minimal-input
reproduction statement describes the compact-input route; this release adds
the optional source-reconstruction interface without changing paper results.

## 2. Dependencies and resource budget

First create the two Python environments using
[REPRODUCTION_PROTOCOL.md](REPRODUCTION_PROTOCOL.md). Upstream MELD uses the
same frozen Python 3.14 environment. NHANES additionally needs R 4.6.1, the
recommended package `foreign` (tested 0.8-91), and a C compiler usable by
`R CMD SHLIB`. On macOS this requires the command-line developer tools.

Check R's reader:

```bash
Rscript -e 'stopifnot(requireNamespace("foreign", quietly=TRUE)); print(packageVersion("foreign"))'
```

| Source download | Approximate transfer |
|---|---:|
| MM-Align feature archive | 2.14 GiB |
| Two NHANES PAXRAW source archives | 0.84 GiB combined |
| Nine direct CSV/XPT/DAT objects | 0.02 GiB combined |
| Total source data | About 3 GiB |

These amounts exclude Python/R installation. Only the selected train/test
feature files are extracted from MM-Align (about 1.96 GiB). The two PAXRAW XPT
files total about 5.14 GiB after extraction. Source archives are temporary;
the downloader removes its temporary copy after extraction or failure.

Reserve **20 GiB of free disk space**, including sources, temporary downloads,
environments, and working outputs. NHANES is processed one cycle at a time;
32 GiB RAM is the tested machine capacity. Peak memory was not independently
profiled for this release, so a smaller-memory guarantee is not made. No GPU
or model API is needed.

## 3. Acquire or reuse frozen sources

From the extracted package root:

```bash
python3 upstream/fetch_sources.py --source-dir work/upstream_sources --small-only
python3 upstream/fetch_sources.py --source-dir work/upstream_sources
python3 upstream/fetch_sources.py --source-dir work/upstream_sources --verify-only
```

The first command fetches only nine small objects; the second fetches missing
large sources. Existing exact files are reused. Downloads and extracted
members must match both the declared size and SHA-256 in
`upstream/sources.json`. A different response, login page, or changed file
fails validation. Failed network operations are retried up to three times;
a file already present with the wrong hash is never silently overwritten.

The MM-Align Google Drive source can require browser confirmation or become
temporarily unavailable. CDC endpoints can also time out. These are external
availability limits. To use a separately acquired source copy, place the
extracted files in this exact layout, then run the verification command:

```text
work/upstream_sources/
  meld/
    train.pkl
    test.pkl
    train_sent_emo.csv
    test_sent_emo.csv
  nhanes/
    2003-2004/
      PAXRAW_C.xpt
      DEMO_C.xpt
      PAQ_C.xpt
      NHANES_2003_2004_MORT_2019_PUBLIC.dat
    2005-2006/
      PAXRAW_D.xpt
      DEMO_D.xpt
      PAQ_D.xpt
      NHANES_2005_2006_MORT_2019_PUBLIC.dat
  crosscheck/
    crosscheck_daily_data_cleaned_w_sameday.csv
```

An existing directory in this layout can be passed directly with
`--source-dir`; no duplicate source download is needed. Sources remain subject
to their original terms. Work directories contain source variables and
intermediates and must not be uploaded with this package.

## 4. Reconstruct and compare inputs

```bash
TZ=UTC python3 upstream/test_upstream.py
TZ=UTC Rscript upstream/test_pax_kernel.R work/kernel_smoke
TZ=UTC .venv-meld/bin/python upstream/rebuild_inputs.py \
  --source-dir work/upstream_sources \
  --work-dir work/upstream_build \
  --output-dir work/rebuilt_input_data \
  --offline
```

The offline flag requires all sources to exist and pass their hashes. Omit it
to fetch missing sources first. Select `--dataset meld`, `nhanes`, or
`crosscheck` to reconstruct only one dataset. Use a fresh output directory
for each run. Published reference inputs are never overwritten.

Outputs include four CSVs, a MELD build summary, and
`work/rebuilt_input_data/upstream_validation.json`. The input comparator checks
schema, row order, all scientific cells, and participant-group membership:

```bash
python3 upstream/verify_inputs.py --candidate work/rebuilt_input_data
```

In the tested environment both MELD CSVs and the NHANES CSV are byte-identical
to the references. CrossCheck labels are arbitrary per reconstruction; their
values need not match, but the row-wise cluster partition and every scientific
cell must match. This relabeling leaves the declared bootstrap unchanged.
The comparator tests this distinction and rejects changed values or clusters.

## 5. Recompute the paper results from rebuilt inputs

```bash
TZ=UTC .venv-meld/bin/python upstream/run_from_rebuilt.py \
  --input-dir work/rebuilt_input_data \
  --work-dir work/upstream_downstream \
  --python-sim .venv-sim/bin/python
```

Use a fresh work directory. The runner copies the rebuilt inputs into an
isolated analysis tree, runs simulation, MELD, NHANES, CrossCheck, and NHANES
floor diagnostics, and applies the frozen result comparators. Released inputs
and canonical results are read only for validation, not for producing the
new estimates. Expected final line: `UPSTREAM_TO_PAPER_RESULTS=PASS`.
A successful run writes `work/upstream_downstream/end_to_end_validation.json`.

After acquiring the source cache, the combined Make interface is:

```bash
TZ=UTC make reproduce-upstream
```

## 6. Method details and validation scope

MELD averages each sequence in float64 and stores the mean in float32 before
fitting the original train-only transforms. Text uses 32 SVD dimensions, audio
16 PCA dimensions, and visual 32 PCA dimensions. Four-cluster representations
are also fitted on train only. Source train utterance `125_3` has no published
feature entry and is excluded under the frozen coverage check; test coverage
is complete. Target sentiment labels are used after transform fitting.

NHANES uses the included NCI-compatible C minute processor: a 60-minute
nonwear window with the frozen two-minute tolerance, at least 600 wear minutes
per valid day, at least four valid days, and the documented artifact handling.
The synthetic R reference checks counts, wear time, and counts per minute.
Adult/inclusion filters, mortality horizons, pooled survey weights, and
weighted cutpoints are explicit in the R builder and processing configuration.

CrossCheck sorts the public daily rows by participant/date, forms adjacent
assessments one to seven days apart, and reconstructs the frozen sensor
composite, weighted cutpoints, quality strata, and participant-equal weights.
This is a finite-table association analysis; it is not a held-out predictive
model trained on newly collected phone streams.

The validation record is `provenance/UPSTREAM_VALIDATION.json`. Source-to-input
and rebuilt-input-to-result execution use exact frozen local source objects.
This verifies the computational chain from the declared starting files.
It does not establish future availability of hosting services, reproducibility
of the upstream pretrained feature models, theoretical correctness, or an
independent cross-platform replication.
