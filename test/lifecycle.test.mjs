import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { execFile, spawnSync } from 'node:child_process';
import { promisify } from 'node:util';
import { pkg, root } from '../lib/runtime.mjs';

const execute = promisify(execFile);
const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const node = process.execPath;
const env = { ...process.env, JQCLI_UPDATE_CHECK: '0' };
const sourceEntry = path.join(root, 'bin/cli.mjs');
function cli(entry, args, options = {}) {
  const result = spawnSync(node, [entry, ...args], { env, encoding: 'utf8', timeout: 270000, ...options });
  if (result.error) throw result.error;
  return { ...result, json: JSON.parse(result.stdout) };
}
function npmRun(args, options = {}) {
  const result = spawnSync(npm, args, { encoding: 'utf8', env, timeout: 120000, shell: process.platform === 'win32', ...options });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  return result.stdout;
}
function temporary(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'jqcli-test-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  return directory;
}
function checked(entry, args, options) {
  const result = cli(entry, args, options);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return result.json.result;
}
const selected = (agent, target) => ['--agent', agent, '--target', target, '--json'];

test('packed scripts-disabled install, managed runtime isolation, same-version repair and local-edits protection', { timeout: 480000 }, t => {
  const directory = temporary(t);
  const tarball = path.join(directory, JSON.parse(npmRun(['pack', '--json', '--pack-destination', directory], { cwd: root }))[0].filename);
  const bootstrap = path.join(directory, 'bootstrap');
  npmRun(['install', '--prefix', bootstrap, '--ignore-scripts', '--no-audit', '--no-fund', tarball]);
  const entry = path.join(bootstrap, 'node_modules', pkg.name, 'bin/cli.mjs');
  const alpha = path.join(directory, 'alpha', 'jqcli');
  const beta = path.join(directory, 'beta', 'jqcli');
  const a = selected('arbitrary-host', alpha);
  const b = selected('generic', beta);
  assert.equal(checked(entry, ['version', '--json']).version, pkg.version);
  assert.equal(checked(entry, ['doctor', '--json'], { env: { ...env, QUANT_PLUGIN_HOME: path.join(directory, 'unconfigured') } }).healthy, false);
  assert.equal(cli(entry, ['update', 'install', '--agent', 'generic', '--version', pkg.version]).json.error.code, 'TARGET_REQUIRED');
  assert.equal(cli(entry, ['skill', 'install', ...selected('BAD!', alpha)]).json.error.code, 'AGENT_REQUIRED');
  assert.equal(cli(entry, ['skill', 'install', ...a, '--typo']).json.error.code, 'INVALID_ARGUMENT');
  assert.equal(fs.existsSync(alpha), false);

  fs.mkdirSync(alpha, { recursive: true });
  const marker = path.join(alpha, 'SKILL.md');
  fs.writeFileSync(marker, 'User-owned');
  assert.equal(cli(entry, ['skill', 'install', ...a]).json.error.code, 'UNMANAGED_TARGET');
  assert.equal(fs.readFileSync(marker, 'utf8'), 'User-owned');
  fs.rmSync(alpha, { recursive: true });

  const one = checked(entry, ['skill', 'install', ...a]);
  const two = checked(entry, ['skill', 'install', ...b]);
  assert.equal(one.current, true);
  assert.equal(two.hostDiscovery.verified, false);
  assert.equal(checked(entry, ['update', 'install', '--version', pkg.version, ...b]).changed, false);
  const uiMetadata = path.join(beta, 'agents/openai.yaml');
  fs.writeFileSync(uiMetadata, 'interface:\n  display_name: 自定义\n');
  fs.unlinkSync(path.join(beta, 'references', 'research.md'));
  assert.equal(checked(entry, ['skill', 'status', ...b]).current, false);
  const repaired = checked(entry, ['update', 'install', '--version', pkg.version, ...b]);
  assert.equal(repaired.current, true);
  assert.ok(fs.statSync(repaired.backup).isDirectory());
  assert.match(fs.readFileSync(uiMetadata, 'utf8'), /自定义/);
  fs.appendFileSync(path.join(alpha, 'SKILL.md'), '\nLocal edit');
  assert.equal(cli(entry, ['update', 'install', '--version', pkg.version, ...a]).json.error.code, 'LOCAL_EDITS');
  assert.equal(checked(entry, ['skill', 'status', ...b]).current, true);
  assert.equal(fs.statSync(path.join(beta, 'SKILL.md')).nlink, 1);

  fs.rmSync(bootstrap, { recursive: true });
  fs.rmSync(alpha, { recursive: true });
  assert.equal(checked(two.entry, ['version']).version, pkg.version);
  assert.equal(checked(two.entry, ['doctor']).runtime.package, pkg.version);
  assert.equal(checked(two.entry, ['skill', 'status', ...b]).current, true);
  const file = path.join(directory, 'strategy.py');
  fs.writeFileSync(file, 'def initialize(context):\n    pass\n');
  const result = spawnSync(node, [two.entry, 'strategy', 'check', '--file', file], { encoding: 'utf8', env });
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('ordinary task detection is bounded, cached and disabled independently of installation', { timeout: 15000 }, async t => {
  const directory = temporary(t);
  let requests = 0;
  let failed = false;
  const server = http.createServer((request, response) => {
    requests++;
    response.writeHead(failed ? 503 : 200, { 'Content-Type': 'application/json' });
    response.end(JSON.stringify({ name: pkg.name, version: '999.1.0' }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => server.close());
  const detectionEnv = { ...env, JQCLI_UPDATE_CHECK: '1', JQCLI_UPDATE_STATE: directory,
    QUANT_PLUGIN_HOME: path.join(directory, 'unconfigured'), npm_config_registry: 'http://127.0.0.1:' + server.address().port };
  async function command(args, extra = {}) {
    try { return await execute(node, [sourceEntry, ...args], { env: { ...detectionEnv, ...extra } }); }
    catch (result) { return result; }
  }
  await command(['version']);
  await command(['backtest', 'show', '123']);
  await command(['strategy', '--help']);
  await command(['strategy', 'check', '--file', 'missing'], { JQCLI_UPDATE_CHECK: '0' });
  assert.equal(requests, 0);
  const first = await command(['strategy', 'check', '--file', 'missing']);
  assert.match(first.stderr, /jqcli\.update\.available/);
  assert.equal(requests, 1);
  await command(['strategy', 'check', '--file', 'missing']);
  assert.equal(requests, 1);
  const file = path.join(directory, 'registry-check.json');
  fs.writeFileSync(file, JSON.stringify({ available: '999.1.0', checkedAt: 1 }));
  failed = true;
  await command(['strategy', 'check', '--file', 'missing']);
  await command(['strategy', 'check', '--file', 'missing']);
  assert.equal(requests, 2);
  assert.equal(JSON.parse(fs.readFileSync(file)).error, 'REGISTRY_UNAVAILABLE');
});

test('locked directory activation defers before mutation and returns recovery guidance', t => {
  const directory = temporary(t);
  const target = path.join(directory, 'jqcli');
  fs.writeFileSync(path.join(directory, '.jqcli.jqcli-lock'), '');
  const result = cli(sourceEntry, ['skill', 'install', ...selected('generic', target)]);
  assert.equal(result.json.error.code, 'TARGET_LOCKED');
  assert.equal(fs.existsSync(target), false);
});
