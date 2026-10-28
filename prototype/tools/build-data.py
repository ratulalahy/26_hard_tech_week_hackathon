#!/usr/bin/env python3
"""Package selected, already committed outputs; never read raw data or run models."""
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'prototype'
PIN = OUT / 'source-commit.txt'
commit = PIN.read_text().strip() if PIN.exists() else subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
sources = {}
def read(path):
    raw = subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)
    sources[path] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return json.loads(raw)
m = read('results/test/metrics.json')
e = read('results/test/extras.json')
s = read('results/storage.json')

def contrast(policy):
    return next(c for c in m['contrasts'] if c['candidate'] == policy and c['reference'] == 'U')['blocks']['4']
mob = e['extensions']['mobility_le_8gpus']
schedules = e['storage']['schedule_comparison']['schedules']
data = {
    'source_commit': commit, 'sources': sources, 'run_id': m['run_id'],
    'covered': m['covered'], 'cohort': m['cohort'], 'workload': m['workload'],
    'baseline': m['policies']['U']['metrics'],
    'routing': {
        'primary': {'contrast': contrast('S'), 'metrics': m['policies']['S']['metrics'], 'run_id': m['run_id'], 'source': 'results/test/metrics.json', 'field': 'contrasts[candidate=S, reference=U].blocks.4'},
        'limited': {'contrast': mob['vs_U']['S']['4'], 'metrics': mob['policies']['S'], 'run_id': mob['run_id'], 'source': 'results/test/extras.json', 'field': 'extensions.mobility_le_8gpus.vs_U.S.4'},
        'timing': {'contrast': contrast('W_time')},
    },
    'knobs': mob['knobs'],
    'storage': {
        'run_id': e['extras_run_id'], 'window': e['storage']['window'], 'rush': e['storage']['rush'],
        'assumptions': s['assumptions'], 'headline': s['headline'],
        'schedules': {key: {'charge_hours': val['charge_hours'], 'discharge_hours': val['discharge_hours'], 'metrics': val['cases']['U']['4']} for key, val in schedules.items()},
    },
}
# Preserve original envelopes (value, unit, evidence, provenance, status) throughout.
for name in ('funnel-display-latin-500-normal.woff2', 'funnel-sans-latin-400-normal.woff2', 'funnel-sans-latin-600-normal.woff2', 'LICENSE-funnel.txt'):
    raw = subprocess.check_output(['git', 'show', f'{commit}:docs/pitch/deck/fonts/{name}'], cwd=ROOT)
    (OUT / 'assets' / name).write_bytes(raw)
PIN.write_text(commit + '\n')
serialized = json.dumps(data, ensure_ascii=False, indent=2)
(OUT / 'data.js').write_text('/* Generated from pinned committed outputs. See tools/build-data.py. */\nwindow.PILOT_DATA = ' + serialized + ';\n')
(OUT / 'sources.json').write_text(json.dumps({'commit': commit, 'sources': sources}, indent=2) + '\n')
print(f'Packaged {len(sources)} committed outputs at {commit[:12]}; no model execution.')
