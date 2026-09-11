"""Rebuild both MELD input tables from frozen public sequence features and CSVs."""
from __future__ import annotations
import argparse
import csv
import gc
import json
from pathlib import Path
import pickle
import numpy as np
from fetch_sources import verify_sources, digest
from meld_transforms import MAJOR_SPEAKERS, SENTIMENT_INDEX, fit_and_transform, fit_clusterers, transform_test, read_sentiment_map

class NumpyReader(pickle.Unpickler):
    def find_class(self, module, name):
        allowed = {
            ('numpy.core.multiarray', '_reconstruct'): np.core.multiarray._reconstruct,
            ('numpy', 'ndarray'): np.ndarray,
            ('numpy', 'dtype'): np.dtype,
        }
        if (module, name) not in allowed:
            raise pickle.UnpicklingError('Unsupported feature constructor')
        return allowed[module, name]

def mean_feature(value):
    a = np.asarray(value)
    if a.ndim != 2 or not len(a) or not np.isfinite(a).all():
        raise ValueError('Expected finite nonempty sequence feature')
    return a.mean(axis=0, dtype=np.float64).astype(np.float32)

def load_split(source_dir, split):
    with (source_dir / (split + '_sent_emo.csv')).open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    index = {str(int(r['Dialogue_ID'])) + '_' + str(int(r['Utterance_ID'])): r for r in rows}
    if len(index) != len(rows):
        raise ValueError('Duplicate source CSV keys')
    with (source_dir / (split + '.pkl')).open('rb') as f:
        records = NumpyReader(f).load()
    if not isinstance(records, dict):
        raise ValueError('Expected feature dictionary')
    keys = sorted(records, key=lambda key: tuple(map(int, key.split('_'))))
    missing = sorted(set(index) - set(records))
    if missing != (['125_3'] if split == 'train' else []):
        raise ValueError('Unexpected feature coverage')
    audio, visual = [], []
    for key in keys:
        if key not in index or set(records[key]) != {'audio_features', 'video_features', 'label', 'token_ids'}:
            raise ValueError('Feature schema or alignment mismatch')
        audio.append(mean_feature(records[key]['audio_features']))
        visual.append(mean_feature(records[key]['video_features']))
    result = {
        'key': np.asarray(keys),
        'dialogue_id': np.asarray([int(index[k]['Dialogue_ID']) for k in keys], dtype=np.int32),
        'utterance_id': np.asarray([int(index[k]['Utterance_ID']) for k in keys], dtype=np.int32),
        'speaker': np.asarray([index[k]['Speaker'] for k in keys]),
        'transcript': np.asarray([index[k]['Utterance'] for k in keys]),
        'audio': np.stack(audio), 'visual': np.stack(visual),
    }
    del records; gc.collect()
    expected = 9988 if split == 'train' else 2610
    if result['audio'].shape != (expected, 32) or result['visual'].shape != (expected, 2048):
        raise ValueError('Feature dimension mismatch')
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); verify_sources(a.source_dir, 'meld')
    a.output_dir.mkdir(parents=True, exist_ok=True)
    names = ['meld_reanalysis_continuous_features.csv', 'meld_reanalysis_pairs.csv']
    if any((a.output_dir / n).exists() for n in names):
        raise FileExistsError('Use a fresh output directory')
    source = a.source_dir / 'meld'
    print('Aggregating train sequences', flush=True); train = load_split(source, 'train')
    print('Aggregating test sequences', flush=True); test = load_split(source, 'test')
    sentiment = read_sentiment_map(source / 'test_sent_emo.csv')
    seed = 20260901
    print('Fitting continuous representations on train', flush=True)
    text, audio, visual = fit_and_transform(train, test, seed)
    print('Fitting four-cluster representations on train', flush=True)
    clusters = transform_test(test, fit_clusterers(train, seed, 4, 4, 32, 16, 32))
    base_fields = ['dialogue_id', 'source_key', 'target_key', 'y_sentiment',
                   'y_sentiment_name', 'c_stratum', 'source_major', 'next_same_speaker']
    feature_fields = [f'text_svd_{i:02d}' for i in range(32)] + [f'audio_pca_{i:02d}' for i in range(16)] + [f'visual_pca_{i:02d}' for i in range(32)]
    discrete_fields = base_fields[:5] + ['t_cluster', 'audio_cluster', 'visual_cluster', 'fused_cluster'] + base_fields[5:]
    continuous_rows, discrete_rows = [], []
    order = np.lexsort((test['utterance_id'], test['dialogue_id']))
    for left, right in zip(order[:-1], order[1:]):
        if test['dialogue_id'][left] != test['dialogue_id'][right]:
            continue
        source_key, target_key = str(test['key'][left]), str(test['key'][right])
        major = int(str(test['speaker'][left]) in MAJOR_SPEAKERS)
        same = int(test['speaker'][left] == test['speaker'][right])
        y = sentiment[target_key]
        row = dict(zip(base_fields, [int(test['dialogue_id'][left]), source_key, target_key,
             SENTIMENT_INDEX[y], y, f'major={major}|same={same}', major, same]))
        values = np.concatenate([text[left], audio[left], visual[left]])
        continuous_rows.append({**row, **{key: format(float(value), '.8g') for key, value in zip(feature_fields, values)}})
        discrete_rows.append({**row, **{field: int(clusters[key][left]) for field, key in
            [('t_cluster', 'text'), ('audio_cluster', 'audio'), ('visual_cluster', 'visual'), ('fused_cluster', 'fused')]}})
    if len(continuous_rows) != 2330:
        raise ValueError('Pair count mismatch')
    for name, fields, rows in [(names[0], base_fields + feature_fields, continuous_rows), (names[1], discrete_fields, discrete_rows)]:
        with (a.output_dir / name).open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    summary = {'status': 'PASS', 'seed': seed, 'pairs': 2330, 'train_rows': 9988,
               'test_rows': 2610, 'fit_split': 'train', 'output_sha256': {n: digest(a.output_dir / n) for n in names}}
    (a.output_dir / 'meld_build.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))

if __name__ == '__main__':
    main()
