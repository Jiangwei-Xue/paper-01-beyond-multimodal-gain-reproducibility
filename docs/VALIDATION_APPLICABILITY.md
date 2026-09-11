# Validation applicability

The attached publication checklist mentions VCR, H5, and E5 validation. Those
names are not universal test standards; they apply only when the underlying
project defines and uses them.

| Check | Status | Reason |
|---|---|---|
| VCR replay | Not applicable | No HTTP/API response cassette or model-call replay is part of these statistical experiments. |
| H5/HDF5 validation | Not applicable | The released pipeline neither reads nor writes HDF5 artifacts. |
| E5 validation | Not applicable | No project-defined E5 validator or E5 artifact exists in the frozen experimental method. |
| Package validation | Required | Verifies input structure, folds, manifests, hashes, paper binding, and result lineage. |
| Numerical rerun validation | Required | Simulation, MELD, NHANES, CrossCheck, and floor diagnostics each have explicit expected-result verifiers. |
| Archive release validation | Required | The final archive must pass `experiment-release verify`. |

VCR, H5, and E5 are therefore recorded as not applicable rather than treated
as unperformed project tests.
