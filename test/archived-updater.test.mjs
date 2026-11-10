import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import test from 'node:test';
import { pkg, root } from '../lib/runtime.mjs';

const exec = promisify(execFile);
const oldVersion = '0.1.1';
const packageName = pkg.name;
const executable = process.execPath;

test('actual published updater CLI with real npm, historical copy migration, Skill sync failure and same-version recovery', {
  timeout: 600000,
  skip: process.platform === 'win32' ? 'Published 0.1.1 cannot spawn npm.cmd on Windows' : false,
}, async t => {
  const area = fs.mkdtempSync(path.join(os.tmpdir(), 'jqcli-archive-'));
  t.after(() => fs.rmSync(area, { recursive: true, force: true }));
  const prefix = path.join(area, 'global');
  const userConfig = path.join(area, 'npm-user');
  const globalConfig = path.join(area, 'npm-global');
  fs.writeFileSync(userConfig, '');
  fs.writeFileSync(globalConfig, '');
  const env = {
    ...process.env, JQCLI_UPDATE_CHECK: '0', QUANT_PLUGIN_HOME: path.join(area, 'runtime'),
    PATH: path.join(prefix, 'bin') + path.delimiter + process.env.PATH, npm_config_prefix: prefix,
    npm_config_userconfig: userConfig, npm_config_globalconfig: globalConfig,
  };
  const run = async (command, args, extra = {}) => (await exec(command, args, { env, cwd: root, timeout: 300000, ...extra })).stdout;
  const npm = (...args) => run('npm', args);
  const cli = async (entry, ...args) => JSON.parse(await run(executable, [entry, ...args]));
  const releaseVersion = pkg.version === oldVersion ? '0.2.0' : pkg.version;
  const packed = JSON.parse(await npm('pack', '--json', '--pack-destination', area))[0];
  const packPath = path.join(area, packed.filename);
  const fixturePrefix = path.join(area, 'fixture');
  await npm('install', '--prefix', fixturePrefix, '--ignore-scripts', '--no-audit', '--no-fund', packPath);
  const fixture = path.join(fixturePrefix, 'node_modules', packageName);
  await run('npm', ['pkg', 'set', 'version=' + releaseVersion], { cwd: fixture });
  await run(executable, ['scripts/release-identity.mjs', 'sync'], { cwd: fixture });
  const candidate = JSON.parse(await run('npm', ['pack', '--json', '--pack-destination', area], { cwd: fixture }))[0];
  const tar = fs.readFileSync(path.join(area, candidate.filename));

  const server = http.createServer((request, response) => {
    if (request.url === '/candidate.tgz') {
      response.writeHead(200, { 'Content-Type': 'application/octet-stream' });
      return response.end(tar);
    }
    const dist = { tarball: 'http://127.0.0.1:' + server.address().port + '/candidate.tgz', integrity: candidate.integrity };
    const release = { name: packageName, version: releaseVersion, dist, bin: { jqcli: 'bin/cli.mjs' } };
    response.writeHead(200, { 'Content-Type': 'application/json' });
    response.end(JSON.stringify({ name: packageName, 'dist-tags': { latest: releaseVersion }, versions: { [releaseVersion]: release } }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => server.close());

  await npm('install', '-g', '--ignore-scripts', '--no-audit', '--no-fund', packageName + '@' + oldVersion);
  const oldGlobal = path.join(prefix, 'lib/node_modules', packageName);
  const oldCopy = path.join(area, 'archived');
  fs.cpSync(oldGlobal, oldCopy, { recursive: true });
  const old = path.join(oldCopy, 'bin/cli.mjs');
  const fresh = path.join(oldGlobal, 'bin/cli.mjs');
  assert.equal((await cli(old, 'version')).result.version, oldVersion);
  const target = path.join(area, 'selected', 'jqcli');
  const untouched = path.join(area, 'unrelated', 'jqcli');
  const chosen = ['--agent', 'codex', '--target', target];
  await cli(old, 'skill', 'install', ...chosen);
  await cli(old, 'skill', 'install', '--agent', 'sealseek', '--target', untouched);
  const skill = path.join(target, 'SKILL.md');
  // A local edit must survive the old updater's npm-first handoff.
  const original = fs.readFileSync(skill);
  fs.appendFileSync(skill, '\nUser edit');
  const archivedArgs = [old, 'update', 'install', '--version', releaseVersion, ...chosen];
  const registry = 'http://127.0.0.1:' + server.address().port;
  fs.writeFileSync(userConfig, '@petercjl:registry=' + registry + '\n');
  const local = { ...env, npm_config_registry: registry };
  let failed;
  await assert.rejects(run(executable, archivedArgs, { env: local }), error => {
    failed = error.stdout;
    return true;
  });
  assert.equal((await cli(fresh, 'version')).result.version, releaseVersion, failed);
  assert.equal((await cli(fresh, 'skill', 'status', ...chosen)).result.edited, true);
  assert.match(fs.readFileSync(skill, 'utf8'), /User edit/);
  fs.writeFileSync(skill, original);
  const succeeded = JSON.parse(await run(executable, archivedArgs, { env: local }));
  assert.equal(succeeded.result.skill.result.current, true);
  const receipt = succeeded.result.skill.result;
  assert.deepEqual(fs.readFileSync(path.join(receipt.backup, 'SKILL.md')), original);
  assert.equal((await cli(receipt.entry, 'doctor')).result.runtime.package, releaseVersion);
  assert.equal((await cli(fresh, 'skill', 'status', '--agent', 'sealseek', '--target', untouched)).result.installedVersion, oldVersion);
  assert.equal((await cli(receipt.entry, 'update', 'install', '--version', releaseVersion, ...chosen)).result.changed, false);

  if (pkg.version !== releaseVersion) {
    const modernTarget = path.join(area, 'modern', 'jqcli');
    const sourceEntry = path.join(root, 'bin/cli.mjs');
    const update = [sourceEntry, 'update', 'install', '--agent', 'unlisted-agent', '--target', modernTarget];
    const result = JSON.parse(await run(executable, [...update, '--version', releaseVersion], { env: local }));
    assert.equal(result.result.selectedVersion, releaseVersion);
    assert.equal((await cli(sourceEntry, 'version')).result.version, pkg.version);
    assert.equal((await cli(result.result.entry, 'doctor')).result.runtime.package, releaseVersion);
  }
});
