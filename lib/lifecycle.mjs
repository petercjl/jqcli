import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { buildPython, exists, fail, name, pkg, read, root, source, verifyPython } from './runtime.mjs';

const receiptName = '.quant-managed.json';
const uiMetadata = 'agents/openai.yaml';
const inside = (directory, item) => {
  const rel = path.relative(directory, item);
  return rel === '' || (!path.isAbsolute(rel) && rel !== '..' && !rel.startsWith('..' + path.sep));
};

export const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
export function hashes(directory, options = {}) {
  const files = {};
  function walk(current, prefix) {
    for (const entry of fs.readdirSync(current, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const key = prefix + entry.name;
      if (key === receiptName || (options.ignoreGenerated && /^(?:__pycache__|.*\.pyc|\.(?:git|npm)ignore)$/.test(entry.name))) continue;
      const location = path.join(current, entry.name);
      if (entry.isDirectory()) walk(location, key + '/');
      else if (entry.isFile() && fs.lstatSync(location).nlink === 1) files[key] = digest(location);
      else throw fail('UNSAFE_PATH', 'Runtime and Skill files must be physical copies: ' + key);
    }
  }
  walk(directory, '');
  return files;
}

export const sourceInfo = () => ({
  name, package: pkg.name, version: pkg.version, source, path: source,
  provenance: { ownership: 'package', registryContentVerified: false },
});

function targetOf(options) {
  if (!/^[a-z][a-z0-9-]{0,63}$/.test(options.agent || '')) throw fail('AGENT_REQUIRED', 'Supply the current Agent name with --agent NAME');
  if (!options.target || !path.isAbsolute(options.target)) throw fail('TARGET_REQUIRED', 'Resolve the current Agent Skill directory and supply its absolute --target');
  const target = path.resolve(options.target);
  const own = path.basename(root) === '.runtime' && path.dirname(root) === target;
  if (target === path.parse(target).root || (!own && (inside(target, root) || inside(root, target)))) {
    throw fail('TARGET_CONFLICT', 'The exact Skill directory must be independent of the bootstrap package');
  }
  for (let item = path.dirname(target); item !== path.dirname(item); item = path.dirname(item)) {
    const stat = fs.lstatSync(item, { throwIfNoEntry: false });
    const systemAlias = process.platform === 'darwin' && ['/var', '/tmp'].includes(item) && stat?.uid === 0;
    if (stat && !stat.isDirectory() && !systemAlias) throw fail('UNSAFE_PATH', 'Skill destination parents must be physical directories');
  }
  return target;
}

function inspect(options) {
  const target = targetOf(options);
  const info = fs.lstatSync(target, { throwIfNoEntry: false });
  if (info && !info.isDirectory() && !info.isSymbolicLink()) throw fail('UNSAFE_PATH', 'Skill target must be a directory');
  const installed = !!info;
  const linked = !!info?.isSymbolicLink();
  let record;
  let real;
  if (installed) {
    try {
      real = fs.realpathSync(target);
      const file = path.join(real, receiptName);
      if (fs.lstatSync(file).isFile()) record = read(file);
    } catch { /* Missing or invalid receipt is unmanaged. */ }
  }
  const legacy = record?.schemaVersion === undefined;
  const validHashes = record?.hashes && typeof record.hashes === 'object' && !Array.isArray(record.hashes);
  const managed = !!(validHashes && record.package === pkg.name &&
    (legacy ? !linked || record.source === real : !linked && record.target === target && record.agent === options.agent));
  const actual = managed ? hashes(real) : {};
  const edits = managed && Object.keys(actual).some(key => key !== uiMetadata && record.hashes[key] !== actual[key]);
  // Missing managed files are repairable. Unrecognized or modified files are local edits.
  const complete = managed && Object.keys(record.hashes).every(key => key === uiMetadata || actual[key] === record.hashes[key]);
  const release = read(path.join(root, 'release-integrity.json')).files;
  const canonical = managed && actual['.runtime/release-integrity.json'] === digest(path.join(root, 'release-integrity.json')) && Object.entries(release).every(([key, value]) => key === uiMetadata || actual[key] === value);
  const current = !!(complete && canonical && !linked && !edits && !legacy && record.version === pkg.version);
  const entry = path.join(target, '.runtime', 'bin', 'cli.mjs');
  return {
    ...sourceInfo(), target, installed, managed, current, edited: !!edits, agent: options.agent,
    installedVersion: managed ? record.version : null, entry, adapter: 'generic',
    verification: { verified: current, algorithm: 'sha256' },
    hostDiscovery: { authority: 'host', verified: false },
    recovery: { required: installed && !current, action: edits ? 'Preserve and reconcile local edits' : 'Run skill update for the exact target' },
    backup: managed ? record.backup ?? null : null,
    linked,
  };
}

export const status = options => inspect(options);

export function requireReplaceable(before, adopt) {
  if (before.installed && !before.managed && !adopt) throw fail('UNMANAGED_TARGET', 'Choose a fresh destination or explicitly authorize adoption and backup');
  if (before.edited && !adopt) throw fail('LOCAL_EDITS', 'Local Skill edits detected; review before adopting');
  if (before.linked && !before.managed) throw fail('UNSAFE_PATH', 'Only verified managed legacy links can be migrated');
}

export function install(options) {
  const before = inspect(options);
  requireReplaceable(before, options.adopt);
  if (before.current) {
    try { verifyPython(path.dirname(path.dirname(before.entry))); return { ...before, changed: false }; }
    catch { /* Rebuild a runtime with missing or broken prerequisites. */ }
  }
  const { target } = before;
  const parent = path.dirname(target);
  fs.mkdirSync(parent, { recursive: true });
  const lock = path.join(parent, '.' + path.basename(target) + '.jqcli-lock');
  let fd;
  try { fd = fs.openSync(lock, 'wx', 0o600); }
  catch { throw fail('TARGET_LOCKED', 'Another Skill operation holds the target lock'); }
  const id = crypto.randomUUID();
  const staging = path.join(parent, '.' + path.basename(target) + '.jqcli-stage-' + id);
  const backup = before.installed ? path.join(parent, '.' + path.basename(target) + '.jqcli-backup-' + id) : null;
  let moved = false;
  let activated = false;
  try {
    const original = before.installed ? hashes(fs.realpathSync(target)) : null;
    const release = read(path.join(root, 'release-integrity.json'));
    if (release.version !== pkg.version) throw fail('VERSION_MISMATCH', 'Package and release integrity metadata differ');
    fs.mkdirSync(staging, { mode: 0o700 });
    for (const [destination, expected] of Object.entries(release.files)) {
      const from = destination.startsWith('.runtime/') ? path.join(root, destination.slice(9)) : path.join(source, destination);
      const to = path.join(staging, destination);
      if (!inside(staging, to) || digest(from) !== expected) throw fail('RELEASE_INTEGRITY', 'Packaged file integrity failed: ' + destination);
      fs.mkdirSync(path.dirname(to), { recursive: true });
      fs.copyFileSync(from, to, fs.constants.COPYFILE_EXCL);
    }
    fs.copyFileSync(path.join(root, 'release-integrity.json'), path.join(staging, '.runtime/release-integrity.json'), fs.constants.COPYFILE_EXCL);
    const oldUi = path.join(target, uiMetadata);
    if (exists(oldUi)) {
      if (!fs.lstatSync(oldUi).isFile()) throw fail('UNSAFE_PATH', 'Host UI metadata must be a file');
      fs.copyFileSync(oldUi, path.join(staging, uiMetadata));
    }
    buildPython(path.join(staging, '.runtime'), path.join(staging, '.runtime'), options.python);
    const record = {
      schemaVersion: 1, package: pkg.name, version: pkg.version, agent: options.agent, target,
      hashes: hashes(staging), source, backup, operationId: id,
    };
    fs.writeFileSync(path.join(staging, receiptName), JSON.stringify(record, null, 2), { flag: 'wx', mode: 0o600 });
    const again = inspect(options);
    if (before.installed !== again.installed || before.managed !== again.managed ||
        (before.installed && JSON.stringify(original) !== JSON.stringify(hashes(fs.realpathSync(target))))) {
      throw fail('TARGET_CHANGED', 'The selected Skill changed during preparation');
    }
    if (backup) {
      if (before.linked) {
        fs.cpSync(fs.realpathSync(target), backup, { recursive: true, force: false, errorOnExist: true });
        fs.unlinkSync(target);
      } else fs.renameSync(target, backup);
      moved = true;
    }
    fs.renameSync(staging, target);
    activated = true;
    const result = inspect(options);
    if (!result.current) throw fail('INSTALL_VERIFY_FAILED', 'Installed Skill hashes or version differ');
    verifyPython(path.join(target, '.runtime'));
    return { ...result, changed: true, backup, operationId: id, completion: { cli: true, skill: true, hostDiscovery: false } };
  } catch (error) {
    let restored = false;
    try {
      if (activated) fs.renameSync(target, staging);
      if (moved) { fs.renameSync(backup, target); restored = true; }
    } catch { /* Keep surviving directories and report their locations. */ }
    const journal = path.join(parent, '.' + path.basename(target) + '.jqcli-recovery-' + id + '.json');
    const recovery = { target, backup: moved && !restored ? backup : null, operationId: id, restored,
      journal, action: 'Inspect the exact target before retrying' };
    try { fs.writeFileSync(journal, JSON.stringify({ ...recovery, code: error.code || 'INSTALL_FAILED' }), { flag: 'wx', mode: 0o600 }); }
    catch { delete recovery.journal; }
    throw fail(error.code || 'INSTALL_FAILED', error.message, recovery);
  } finally {
    fs.rmSync(staging, { force: true, recursive: true });
    fs.closeSync(fd);
    fs.unlinkSync(lock);
  }
}
