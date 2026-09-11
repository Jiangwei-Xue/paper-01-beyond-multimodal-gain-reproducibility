"""Reconstruct compact inputs from frozen public upstream sources."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from fetch_sources import verify_sources
from verify_inputs import verify, FILES

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir', type=Path, default=ROOT / 'work/upstream_sources')
    p.add_argument('--work-dir', type=Path, default=ROOT / 'work/upstream_build')
    p.add_argument('--output-dir', type=Path, default=ROOT / 'work/rebuilt_input_data')
    p.add_argument('--dataset', choices=['all', *FILES], default='all')
    p.add_argument('--offline', action='store_true', help='Require existing hash-verified source files; no downloads')
    a = p.parse_args()
    src, work, out = a.source_dir.resolve(), a.work_dir.resolve(), a.output_dir.resolve()
    for folder in (work, out):
        if folder == ROOT or folder == ROOT / 'input_data' or (ROOT / 'input_data') in folder.parents:
            raise ValueError('Build directories must not overwrite released inputs')
    if any((out / n).exists() for k, names in FILES.items() if a.dataset in ('all', k) for n in names):
        raise FileExistsError('Select a fresh output directory')
    env = {**os.environ, 'TZ': 'UTC', 'PYTHONDONTWRITEBYTECODE': '1'}
    if not a.offline:
        subprocess.run([sys.executable, str(ROOT / 'upstream/fetch_sources.py'), '--source-dir', str(src), '--dataset', a.dataset], check=True, env=env)
    source_report = verify_sources(src, a.dataset)
    if a.dataset in ('nhanes', 'all'):
        subprocess.run(['Rscript', str(ROOT / 'upstream/test_pax_kernel.R'), str(work / 'kernel_smoke')], check=True, env=env)
    if a.dataset in ('all', 'nhanes', 'crosscheck'):
        choice = 'all' if a.dataset == 'all' else a.dataset
        subprocess.run(['Rscript', str(ROOT / 'upstream/build_empirical_inputs.R'), str(src), str(work / 'empirical'), str(out), choice], check=True, env=env)
    if a.dataset in ('all', 'meld'):
        subprocess.run([sys.executable, str(ROOT / 'upstream/rebuild_meld.py'), '--source-dir', str(src), '--output-dir', str(out)], check=True, env=env)
    report = verify(ROOT / 'input_data', out, a.dataset)
    report['sources'] = source_report
    out.mkdir(parents=True, exist_ok=True)
    (out / 'upstream_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return 0 if report['status'] == 'PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
