# Data license and provenance

## MELD source boundary

The compact inputs were derived locally from the MELD project and MM-Align feature materials. The upstream identifiers retained at export time are:

- MELD GitHub commit: `e8cedf27b5d2877e198332c957127e16eb214afe`
- MELD Hugging Face commit: `9abc51ee7903424ffb971297608aa6d3d0de3bfa`
- MM-Align commit: `e2448590b3d9b308350515bcb147526f4baa6ac7`
- source `test_sent_emo.csv` SHA-256: `8d37103938f7067600839fe29d5a114a6cd1bcdafb75bec101e06464c5006888`
- local train compact SHA-256: `2fc8b0f22e21453fcb74fd5f473ae9af95e5a5991bba4a65b997ecb33ebd49f7`
- local test compact SHA-256: `a76bc68d9a6fdb7ebecb9317e9694b76340efc3e601f01ecf7ff44d7c7347d94`

The public inputs contain 32 text-SVD, 16 audio-PCA, and 32 visual-PCA values
per adjacent-turn pair, plus outcome/context labels and dialogue/utterance
keys. The keys correspond to public MELD indices and are retained for row
alignment and dialogue-grouped inference. Transcripts, raw audio/video, and
pre-reduction feature arrays are not included.

## Transform boundary

`upstream/rebuild_meld.py` reads the frozen MM-Align train/test sequence
features and MELD CSVs. It aggregates sequences, fits TF-IDF/SVD/PCA/scalers
and K-means on train only without outcome labels, transforms test once, and
constructs adjacent-turn pairs. Both reconstructed CSVs match the references
byte for byte in the tested environment. The neural extraction of these
published sequence features from source media is outside the supported chain.

`upstream/sources.json` records exact source sizes, SHA-256 values, revisions,
and download URLs. `docs/UPSTREAM_REPRODUCTION.md` gives executable acquisition,
reconstruction, and comparison commands. These source files are external
dependencies; no additional redistribution right is asserted.

## Layered license policy

The top-level `LICENSE` file is controlling for package-authored material:

- project documentation and author-generated derived result artifacts use
  CC BY 4.0;
- analysis code and executable configuration use the MIT License;
- the manuscript PDF under `paper/` is included for reference and retains
  author copyright; and
- third-party libraries, public-source data, compact inputs derived from them,
  and model outputs remain governed by their original terms.

The MELD repository at the frozen commit includes a GNU GPL v3 license file. A
copy is retained under `third_party/MELD_LICENSE_GPL-3.0.txt` for notice.
Dataset, dialogue, media, and feature redistribution rights may involve terms
beyond a software repository license. Neither CC BY 4.0 nor MIT in this
repository expands those upstream rights.

## NHANES source boundary

The public NHANES input was derived from the 2003--2004 and 2005--2006 DEMO,
PAQ, PAXRAW, and 2019 public-use linked-mortality files. Official source
documentation is maintained by the US National Center for Health Statistics:

- https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2003/DataFiles/PAXRAW_C.htm
- https://www.cdc.gov/nchs/linked-data/mortality-files/index.html

The released table contains no NHANES respondent sequence number or raw minute
records. It keeps a package-local row number, cycle, derived age flag, discrete
analysis variables, survey design labels, and analysis weight. It supports the
downstream survey-weighted finite-table calculation. Optional raw-minute
reprocessing, survey/mortality joins, and discretization are implemented in
`upstream/build_empirical_inputs.R` and `upstream/pax_nci_aggregate.c`.

## CrossCheck source boundary

The CrossCheck input is derived from the public cleaned data accompanying the
longitudinal mobile-sensing study described by Adler et al. (2022), DOI
`10.1371/journal.pone.0266516`. The compact table contains finite analysis
variables, weights, row order, and package-local participant-cluster labels
needed for participant bootstrap. Calendar dates, continuous sensor summaries,
and source EMA values are not included. The table remains pseudonymized
human-subject-derived data and may be linkable to upstream public records
through rare patterns; the upstream terms and appropriate research-data
handling continue to apply.

The optional CrossCheck builder starts from the pinned public cleaned daily
CSV, reconstructs adjacent assessments and finite variables, and assigns
arbitrary cluster labels. Validation preserves row-wise participant membership,
weights, and all scientific cells. Labels alone do not make trajectories
anonymous. Source and work directories can contain sensitive source variables
and must remain local; they are not part of the upload package.
