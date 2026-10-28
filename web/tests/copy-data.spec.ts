// T11 fix round 1 (M8): copy-data copies results/test/ only when every artifact matches the sha256 the test
// entry point logged in its last export line. Runs scripts/copy-data.mjs on a temporary checkout (COPY_DATA_REPO);
// no browser, no real results.
import { expect, test } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const SCRIPT = join(process.cwd(), 'scripts', 'copy-data.mjs');
const sha = (t: string) => createHash('sha256').update(t).digest('hex');

function checkout(exported: Record<string, string>, onDisk: Record<string, string>) {
  const repo = mkdtempSync(join(tmpdir(), 'copy-data-'));
  mkdirSync(join(repo, 'results', 'test'), { recursive: true });
  writeFileSync(join(repo, 'results', 'metrics.json'), '{}\n');
  for (const [f, t] of Object.entries(onDisk)) writeFileSync(join(repo, 'results', 'test', f), t);
  const line = { event: 'export', artifacts_sha256: Object.fromEntries(Object.entries(exported).map(([f, t]) => [f, sha(t)])) };
  writeFileSync(join(repo, 'results', 'test_reads.jsonl'), JSON.stringify({ event: 'invocation' }) + '\n' + JSON.stringify(line) + '\n');
  return repo;
}
const run = (repo: string) => spawnSync('node', [SCRIPT], { env: { ...process.env, COPY_DATA_REPO: repo, GRIDPILOT_DATA_DIR: join(repo, 'no-data') }, encoding: 'utf8' });
const MAN = JSON.stringify({ window: 'test', run_id: '20261028T000000Z', freeze: { wallclock_frozen_at: '2026-10-27T23:00:00Z' } });

test('copy-data copies results/test only when it matches the logged export', () => {
  const ok = checkout({ 'manifest.json': MAN, 'metrics.json': '{"window":"test"}' }, { 'manifest.json': MAN, 'metrics.json': '{"window":"test"}' });
  const r = run(ok);
  expect(r.status, r.stderr).toBe(0);
  expect(existsSync(join(ok, 'web', 'public', 'data', 'results', 'test', 'metrics.json'))).toBe(true);
  const idx = JSON.parse(readFileSync(join(ok, 'web', 'public', 'data', 'results', 'index.json'), 'utf8'));
  expect(idx.test.available).toBe(true);

  const edited = checkout({ 'manifest.json': MAN, 'metrics.json': '{"window":"test"}' }, { 'manifest.json': MAN, 'metrics.json': '{"window":"test","edited":1}' });
  const r2 = run(edited);
  expect(r2.status).not.toBe(0);
  expect(r2.stderr).toContain('does not match the logged export: metrics.json');
  expect(existsSync(join(edited, 'web', 'public', 'data', 'results', 'test'))).toBe(false);
});

test('copy-data publishes the T16 case-days artifact byte for byte and lists it in the index', () => {
  const repo = mkdtempSync(join(tmpdir(), 'copy-data-'));
  mkdirSync(join(repo, 'results'), { recursive: true });
  const text = readFileSync(join(process.cwd(), '..', 'results', 'case-days.json'), 'utf8');
  writeFileSync(join(repo, 'results', 'case-days.json'), text);
  const r = run(repo);
  expect(r.status, r.stderr).toBe(0);
  expect(readFileSync(join(repo, 'web', 'public', 'data', 'results', 'case-days.json'), 'utf8')).toBe(text);
  const idx = JSON.parse(readFileSync(join(repo, 'web', 'public', 'data', 'results', 'index.json'), 'utf8'));
  expect(idx.files).toContain('case-days.json');
});
