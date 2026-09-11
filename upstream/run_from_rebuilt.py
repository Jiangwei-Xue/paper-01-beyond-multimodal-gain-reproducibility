"""Run the frozen paper analyses on independently regenerated input tables."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from verify_inputs import verify, FILES

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-dir', type=Path, default=ROOT / 'work/rebuilt_input_data')
    p.add_argument('--work-dir', type=Path, default=ROOT / 'work/upstream_downstream')
    p.add_argument('--python-sim', type=Path, default=ROOT / '.venv-sim/bin/python')
    a = p.parse_args(); inputs, work = a.input_dir.resolve(), a.work_dir.resolve()
    report = verify(ROOT / 'input_data', inputs)
    if report['status'] != 'PASS':
        print(json.dumps(report)); return 1
    if work.exists():
        raise FileExistsError('Select a fresh downstream work directory')
    work.mkdir(parents=True)
    for name in ('analysis', 'config'):
        shutil.copytree(ROOT / name, work / name, ignore=shutil.ignore_patterns('__pycache__'))
    (work / 'input_data').mkdir()
    for names in FILES.values():
        for name in names:
            shutil.copyfile(inputs / name, work / 'input_data' / name)
    results = work / 'results'
    env = {**os.environ, 'TZ': 'UTC', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONWARNINGS': 'ignore::FutureWarning'}
    def run(args):
        subprocess.run([str(x) for x in args], cwd=work, env=env, check=True)
    sim_python = Path(os.path.abspath(a.python_sim))
    run([sim_python, ROOT / 'analysis/run_simulation.py', '--config', ROOT / 'config/simulation.json', '--output-dir', results / 'simulation'])
    run([sim_python, ROOT / 'analysis/verify_simulation_rerun.py', '--reference', ROOT / 'canonical_results/simulation', '--candidate', results / 'simulation'])
    run([sys.executable, ROOT / 'analysis/run_meld_reproduction.py', '--config', ROOT / 'config/meld_reproduction.json', '--data-dir', work / 'input_data', '--output-dir', results / 'meld'])
    run([sys.executable, ROOT / 'analysis/verify_meld_rerun.py', '--reference', ROOT / 'canonical_results/meld', '--candidate', results / 'meld', '--tolerance', '1e-10'])
    run(['Rscript', ROOT / 'analysis/run_empirical_reproduction.R', work, results / 'empirical'])
    run(['Rscript', ROOT / 'analysis/run_nhanes_floor_diagnostics.R', work, results / 'floor_diagnostics'])
    for name in ('empirical', 'floor_diagnostics'):
        run(['Rscript', ROOT / 'analysis/verify_empirical_rerun.R', ROOT / 'canonical_results' / name, results / name])
    (work / 'end_to_end_validation.json').write_text(json.dumps({
        'status': 'PASS', 'input_equivalence': report,
        'downstream_comparators': ['simulation', 'meld', 'empirical', 'floor_diagnostics'],
        'input_source': 'independently rebuilt tables; released inputs used only for validation',
    }, indent=2) + '\n')
    print('UPSTREAM_TO_PAPER_RESULTS=PASS')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
