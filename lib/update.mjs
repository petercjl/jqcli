import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { install, requireReplaceable, status } from './lifecycle.mjs';
import { exists, fail, pkg, read } from './runtime.mjs';

const stable = /^\d+\.\d+\.\d+$/;
const semver = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/;
const timeoutMs = 1500;
const ttl = 24 * 60 * 60 * 1000;
const state = process.env.JQCLI_UPDATE_STATE || path.join(os.homedir(), '.cache', 'jqcli', 'update');
const cache = path.join(state, 'registry-check.json');

function isNewer(latest) {
  const current = pkg.version.split('-')[0].split('.').map(Number);
  for (const [index, value] of latest.split('.').map(Number).entries()) {
    if (value !== current[index]) return value > current[index];
  }
  return pkg.version.includes('-');
}

async function query(tag) {
  const registry = process.env.npm_config_registry || 'https://registry.npmjs.org/';
  try {
    const url = new URL(encodeURIComponent(pkg.name) + '/' + tag, registry.replace(/\/?$/, '/'));
    const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
    if (!response.ok) throw new Error();
    const result = await response.json();
    if (result.name !== pkg.name || !semver.test(result.version) || (tag === 'latest' && !stable.test(result.version))) throw new Error();
    return { current: pkg.version, available: result.version, newer: stable.test(result.version) && isNewer(result.version), tag };
  } catch { throw fail('REGISTRY_UNAVAILABLE', 'npm registry check failed; the installed CLI and Skill are available offline'); }
}

export function updateStatus() {
  const disabled = process.env.JQCLI_UPDATE_CHECK === '0';
  let lastCheck;
  try {
    const candidate = read(cache);
    if (Number.isFinite(candidate?.checkedAt) && (candidate.error || stable.test(candidate.available))) lastCheck = candidate;
  } catch { /* No usable cache. */ }
  lastCheck ??= null;
  return { enabled: !disabled, mode: 'notify', intervalHours: 24, timeoutMs, lastCheck };
}

export async function notifyUpdate() {
  const { enabled, lastCheck } = updateStatus();
  if (!enabled) return;
  if (lastCheck && Date.now() - lastCheck.checkedAt < (lastCheck.error ? 15 * 60 * 1000 : ttl)) {
    if (lastCheck.available && stable.test(lastCheck.available) && isNewer(lastCheck.available)) notify(lastCheck.available);
    return;
  }
  let lock;
  const lockPath = path.join(state, 'registry-check.lock');
  try {
    fs.mkdirSync(state, { recursive: true, mode: 0o700 });
    lock = fs.openSync(lockPath, 'wx', 0o600);
  } catch { return; }
  try {
    let result;
    try { result = await query('latest'); }
    catch (error) { result = { error: error.code }; }
    const fresh = { ...result, checkedAt: Date.now() };
    const scratch = cache + '.' + process.pid;
    // Preserve an invalid user-owned cache. Checks remain advisory.
    if (!exists(cache) || lastCheck) {
      fs.writeFileSync(scratch, JSON.stringify(fresh), { flag: 'wx', mode: 0o600 });
      fs.renameSync(scratch, cache);
    }
    if (result.newer) notify(result.available);
  } catch { /* Registry detection never prevents a business command. */ }
  finally {
    try { fs.closeSync(lock); fs.rmSync(lockPath, { force: true }); } catch { /* Detection is advisory. */ }
  }
}

function notify(version) {
  process.stderr.write(JSON.stringify({ event: 'jqcli.update.available', current: pkg.version, available: version,
    action: 'Run an explicit update for the current Agent and its Skill directory' }) + '\n');
}

export function checkUpdate(tag = 'latest') {
  if (!['latest', 'next'].includes(tag)) throw fail('INVALID_TAG', 'Use latest or next');
  return query(tag);
}

export async function updateInstall(options) {
  const before = status(options);
  requireReplaceable(before, false);
  // An exact version and explicit target were the historical authorization contract.
  if (!options.yes && !options.version) throw fail('CONFIRMATION_REQUIRED', 'Use --yes to select and install the current stable version');
  const version = options.version ?? (await checkUpdate()).available;
  if (!semver.test(version)) throw fail('VERSION_REQUIRED', 'Supply an exact npm version');
  if (version === pkg.version) return install(options);

  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'jqcli-candidate-'));
  const journal = path.join(directory, 'operation.json');
  const record = { target: before.target, previousVersion: before.installedVersion, candidateVersion: version, stage: 'acquisition' };
  const save = () => fs.writeFileSync(journal, JSON.stringify(record, null, 2), { mode: 0o600 });
  const recovery = { target: before.target, journal, action: 'Inspect the selected Skill status before retrying' };
  save();
  const { entry, prefix } = npmEntry();
  const acquired = spawnSync(entry, [...prefix, 'install', '--prefix', directory, '--ignore-scripts', '--no-audit', '--no-fund', pkg.name + '@' + version],
    { encoding: 'utf8', timeout: 120000, env: { ...process.env, npm_config_dry_run: 'false' } });
  if (acquired.status !== 0) throw fail('PACKAGE_ACQUISITION_FAILED', 'Candidate acquisition failed; selected Skill is preserved', recovery);
  const candidate = path.join(directory, 'node_modules', pkg.name);
  if (read(path.join(candidate, 'package.json')).version !== version || !exists(path.join(candidate, 'release-integrity.json'))) {
    throw fail('CANDIDATE_INCOMPATIBLE', 'The acquired version lacks the isolated installation contract', recovery);
  }
  record.stage = 'activation';
  save();
  const args = ['skill', 'update', '--agent', options.agent, '--target', before.target, '--json'];
  if (options.python) args.push('--python', options.python);
  const result = spawnSync(process.execPath, [path.join(candidate, 'bin/cli.mjs'), ...args], { encoding: 'utf8', timeout: 300000 });
  let receipt;
  try { receipt = JSON.parse(result.stdout); } catch { /* Unknown child outcome remains recoverable. */ }
  if (result.status !== 0 || !receipt?.ok || !receipt.result.current) {
    record.error = receipt?.error ?? { code: 'ACTIVATION_OUTCOME_UNKNOWN' };
    save();
    throw fail('CANDIDATE_ACTIVATION_FAILED', 'Inspect the recorded candidate and Skill activation state', recovery);
  }
  fs.rmSync(directory, { recursive: true, force: true });
  return { ...receipt.result, selectedVersion: version, bootstrapRetained: true };
}

function npmEntry() {
  if (process.platform !== 'win32') return { entry: 'npm', prefix: [] };
  const locations = spawnSync('where.exe', ['npm.cmd'], { encoding: 'utf8' }).stdout?.trim().split(/\r?\n/) ?? [];
  const entry = locations.map(location => path.join(path.dirname(location), 'node_modules/npm/bin/npm-cli.js'))
    .find(file => exists(file));
  if (!entry) throw fail('NPM_UNAVAILABLE', 'Install Node.js with npm on the Windows PATH');
  return { entry: process.execPath, prefix: [entry] };
}
