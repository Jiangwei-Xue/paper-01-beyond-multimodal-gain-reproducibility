PYTHON ?= python3
PYTHON_SIM ?= .venv-sim/bin/python
PYTHON_MELD ?= .venv-meld/bin/python

.PHONY: verify-static run-simulation verify-simulation run-meld verify-meld run-empirical run-floor-diagnostics verify-empirical reproduce verify-full

verify-static:
	$(PYTHON) analysis/verify_static_package.py --root .

run-simulation:
	$(PYTHON_SIM) analysis/run_simulation.py --config config/simulation.json --output-dir rerun_results/simulation

verify-simulation:
	$(PYTHON_SIM) analysis/verify_simulation_rerun.py --reference canonical_results/simulation --candidate rerun_results/simulation

run-meld:
	PYTHONWARNINGS="ignore::FutureWarning" $(PYTHON_MELD) analysis/run_meld_reproduction.py --config config/meld_reproduction.json --data-dir input_data --output-dir rerun_results/meld

verify-meld:
	$(PYTHON_MELD) analysis/verify_meld_rerun.py --reference canonical_results/meld --candidate rerun_results/meld --tolerance 1e-10

run-empirical:
	Rscript analysis/run_empirical_reproduction.R . rerun_results/empirical

run-floor-diagnostics:
	Rscript analysis/run_nhanes_floor_diagnostics.R . rerun_results/floor_diagnostics

verify-empirical:
	Rscript analysis/verify_empirical_rerun.R canonical_results/empirical rerun_results/empirical
	Rscript analysis/verify_empirical_rerun.R canonical_results/floor_diagnostics rerun_results/floor_diagnostics

reproduce: verify-static run-simulation verify-simulation run-meld verify-meld run-empirical run-floor-diagnostics verify-empirical

verify-full: reproduce
	$(PYTHON) analysis/verify_static_package.py --root .

# Optional externally acquired public-source reconstruction.
SOURCE_DIR ?= work/upstream_sources
REBUILT_INPUT_DIR ?= work/rebuilt_input_data
UPSTREAM_WORK_DIR ?= work/upstream_build
UPSTREAM_RESULT_DIR ?= work/upstream_downstream

.PHONY: fetch-upstream verify-upstream-sources test-upstream rebuild-inputs verify-rebuilt-inputs reproduce-upstream
fetch-upstream:
	$(PYTHON) upstream/fetch_sources.py --source-dir $(SOURCE_DIR)

verify-upstream-sources:
	$(PYTHON) upstream/fetch_sources.py --source-dir $(SOURCE_DIR) --verify-only

test-upstream:
	$(PYTHON) upstream/test_upstream.py
	Rscript upstream/test_pax_kernel.R work/kernel_smoke

rebuild-inputs:
	$(PYTHON_MELD) upstream/rebuild_inputs.py --source-dir $(SOURCE_DIR) --work-dir $(UPSTREAM_WORK_DIR) --output-dir $(REBUILT_INPUT_DIR) --offline

verify-rebuilt-inputs:
	$(PYTHON) upstream/verify_inputs.py --candidate $(REBUILT_INPUT_DIR)

reproduce-upstream: rebuild-inputs verify-rebuilt-inputs
	$(PYTHON_MELD) upstream/run_from_rebuilt.py --input-dir $(REBUILT_INPUT_DIR) --work-dir $(UPSTREAM_RESULT_DIR) --python-sim $(PYTHON_SIM)
