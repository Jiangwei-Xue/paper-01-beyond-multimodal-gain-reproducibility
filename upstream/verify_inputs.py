"""Compare independently rebuilt scientific inputs with the released references."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

FILES = {
    'meld': ['meld_reanalysis_continuous_features.csv', 'meld_reanalysis_pairs.csv'],
    'nhanes': ['nhanes_analysis_public.csv'],
    'crosscheck': ['crosscheck_pairs_public.csv'],
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)

def numeric_equal(a, b):
    try:
        x, y = float(a), float(b)
    except ValueError:
        return False
    return math.isfinite(x) and math.isfinite(y) and math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12)

def partition(rows):
    groups = {}; encoded = []
    for row in rows:
        value = row['participant_id']
        if value not in groups:
            groups[value] = len(groups)
        encoded.append(groups[value])
    return encoded

def verify(reference, candidate, dataset='all'):
    names = [n for k, values in FILES.items() if dataset in ('all', k) for n in values]
    result = []; failures = []
    for name in names:
        a, b = Path(reference) / name, Path(candidate) / name
        ah, ar = read(a); bh, br = read(b)
        if ah != bh or len(ar) != len(br):
            failures.append(name + ': schema or row count mismatch'); continue
        if 'participant_id' in ah and partition(ar) != partition(br):
            failures.append(name + ': participant partition mismatch')
        mismatch = 0; cells = 0; max_abs = 0.0
        for left, right in zip(ar, br):
            for key in ah:
                if key == 'participant_id':
                    continue
                cells += 1
                if left[key] != right[key] and not numeric_equal(left[key], right[key]):
                    mismatch += 1
                if numeric_equal(left[key], right[key]):
                    max_abs = max(max_abs, abs(float(left[key]) - float(right[key])))
        if mismatch:
            failures.append(name + ': scientific cell mismatches=' + str(mismatch))
        result.append({'file': name, 'rows': len(ar), 'compared_cells': cells,
                       'max_absolute_numeric_difference': max_abs,
                       'reference_sha256': sha(a), 'rebuilt_sha256': sha(b),
                       'byte_identical': sha(a) == sha(b), 'scientific_mismatches': mismatch})
    return {'status': 'PASS' if not failures else 'FAIL', 'absolute_tolerance': 1e-12,
            'relative_tolerance': 1e-12, 'participant_comparison': 'row-wise cluster membership up to a bijective relabeling',
            'files': result, 'failures': failures}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference', type=Path, default=Path(__file__).resolve().parents[1] / 'input_data')
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--dataset', choices=['all', *FILES], default='all')
    p.add_argument('--report', type=Path)
    a = p.parse_args(); report = verify(a.reference, a.candidate, a.dataset)
    if a.report:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report)); return 0 if report['status'] == 'PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
