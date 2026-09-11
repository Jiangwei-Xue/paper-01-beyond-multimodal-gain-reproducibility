"""Fetch frozen public inputs, or validate an existing local source directory."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import time
import tarfile
import tempfile
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def manifest():
    return json.loads((HERE / 'sources.json').read_text())

def selected(dataset):
    return [r for r in manifest()['sources'] if dataset == 'all' or r['dataset'] == dataset]

def valid(path, record):
    return path.is_file() and path.stat().st_size == record['bytes'] and digest(path) == record['sha256']

def verify_sources(source_dir, dataset='all'):
    rows = selected(dataset)
    failures = [r['path'] for r in rows if not valid(Path(source_dir) / r['path'], r)]
    if failures:
        raise ValueError('Missing or hash-mismatched sources: ' + ', '.join(failures))
    return {'status': 'PASS', 'files': len(rows), 'dataset': dataset}

def transfer_once(url, destination, expected):
    request = urllib.request.Request(url, headers={'User-Agent': 'BMG-Reproduction/1.9'})
    h = hashlib.sha256(); size = 0
    with urllib.request.urlopen(request, timeout=30) as response, destination.open('wb') as output:
        while block := response.read(4 * 1024 * 1024):
            size += len(block)
            if size > expected['bytes']:
                raise ValueError('Downloaded object exceeds its frozen size')
            h.update(block); output.write(block)
    if size != expected['bytes'] or h.hexdigest() != expected['sha256']:
        raise ValueError('Downloaded object failed frozen size/SHA-256 validation; source may have changed or access may require browser confirmation')

def transfer(url, destination, expected):
    for attempt in range(3):
        try:
            return transfer_once(url, destination, expected)
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(1)

def safe_member(name):
    p = PurePosixPath(name)
    return not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name

def extract_selected(container, format_name, records, destination):
    # Original archives are read only; write only selected, hash-checked data files.
    if format_name == 'zip':
        archive = zipfile.ZipFile(container, mode='r')
        members = archive.infolist()
        if any(stat.S_ISLNK(m.external_attr >> 16) for m in members):
            archive.close(); raise ValueError('Unsupported archive member type')
        names = [(m.filename, m) for m in members if not m.is_dir()]
        reader = archive.open
    elif format_name == 'tar':
        archive = tarfile.open(container, mode='r:*')
        members = archive.getmembers()
        if any(m.issym() or m.islnk() or (not m.isfile() and not m.isdir()) for m in members):
            archive.close(); raise ValueError('Unsupported archive member type')
        names = [(m.name, m) for m in members if m.isfile()]
        reader = archive.extractfile
    else:
        raise ValueError('Unsupported source archive format')
    try:
        if len(members) > 100000 or any(not safe_member(n) for n, _ in names):
            raise ValueError('Unsafe source archive layout')
        for r in records:
            hits = [m for n, m in names if PurePosixPath(n).name.lower() == r['member_basename'].lower()]
            if len(hits) != 1:
                raise ValueError('Expected exactly one source member: ' + r['member_basename'])
            member = hits[0]
            size = member.file_size if format_name == 'zip' else member.size
            if size != r['bytes']:
                raise ValueError('Source member size mismatch')
            target = destination / r['path']; target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if valid(target, r):
                    continue
                raise FileExistsError('Existing source has different content: ' + r['path'])
            partial = target.with_suffix(target.suffix + '.partial')
            try:
                with reader(member) as src, partial.open('wb') as dst:
                    shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
                if not valid(partial, r):
                    raise ValueError('Extracted source hash mismatch: ' + r['path'])
                os.replace(partial, target)
            finally:
                partial.unlink(missing_ok=True)
    finally:
        archive.close()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir', type=Path, default=Path('work/upstream_sources'))
    p.add_argument('--dataset', choices=['all', 'meld', 'nhanes', 'crosscheck'], default='all')
    p.add_argument('--verify-only', action='store_true')
    p.add_argument('--small-only', action='store_true', help='Fetch direct CSV/XPT/DAT sources only; leave the large source archives untouched')
    a = p.parse_args(); a.source_dir.mkdir(parents=True, exist_ok=True)
    if a.verify_only:
        print(json.dumps(verify_sources(a.source_dir, a.dataset))); return
    rows = selected(a.dataset); groups = {}
    for r in rows:
        path = a.source_dir / r['path']
        if path.exists():
            if not valid(path, r):
                raise ValueError('Existing source failed hash validation: ' + r['path'])
            continue
        if 'archive' in r:
            groups.setdefault(r['archive'], []).append(r); continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='bmg-fetch-', dir=a.source_dir) as tmp:
            payload = Path(tmp) / 'source.download'
            transfer(r['url'], payload, r)
            os.replace(payload, path)
        print('SOURCE_READY=' + r['path'], flush=True)
    if not a.small_only:
        for key, needed in groups.items():
            info = manifest()['archives'][key]
            print('SOURCE_TRANSFER=' + key + ' bytes=' + str(info['bytes']), flush=True)
            with tempfile.TemporaryDirectory(prefix='bmg-fetch-', dir=a.source_dir) as tmp:
                payload = Path(tmp) / 'source.download'
                transfer(info['url'], payload, info)
                extract_selected(payload, info['format'], needed, a.source_dir)
        print(json.dumps(verify_sources(a.source_dir, a.dataset)))
    else:
        direct = [r for r in rows if 'url' in r]
        if not all(valid(a.source_dir / r['path'], r) for r in direct):
            raise ValueError('Direct source validation failed')
        print(json.dumps({'small_sources': 'PASS', 'files': len(direct), 'large_sources': 'NOT_REQUESTED'}))

if __name__ == '__main__':
    main()
