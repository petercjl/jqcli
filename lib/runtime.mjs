import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

export const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
export const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
export const pkg = read(path.join(root, 'package.json'));
export const name = 'jqcli';
export const source = path.join(root, 'skills', name);
export const exists = file => fs.lstatSync(file, { throwIfNoEntry: false }) !== undefined;
export const fail = (code, message, recovery) => Object.assign(new Error(message), { code, recovery });
export const embedded = path.basename(root) === '.runtime' && exists(path.join(root, 'python.json'));
const state = process.env.QUANT_PLUGIN_HOME || path.join(os.homedir(), '.local', 'share', 'quant-plugins');
export const legacy = path.join(state, name, 'venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const bootstrap = path.join(state, name, 'versions', pkg.version);
const pythonMeta = directory => path.join(directory, 'python.json');

export function run(entry, args, options = {}) {
  const result = spawnSync(entry, args, { encoding: 'utf8', ...options });
  if (result.error || result.status !== 0) {
    throw fail('COMMAND_FAILED', `${path.basename(entry)} exited unsuccessfully${result.error ? ' (' + result.error.code + ')' : ' (' + result.status + ')'}`);
  }
  return result.stdout;
}

export function resolvePython(explicit) {
  const requested = explicit || process.env.QUANT_PYTHON;
  const entries = requested ? [[requested]] : [
    ...(exists(legacy) ? [[legacy]] : []),
    ...(process.platform === 'win32' ? [['py', '-3'], ['python'], ['python3']] : [['python3'], ['python']]),
  ];
  for (const [entry, ...args] of entries) {
    try {
      const result = JSON.parse(run(entry, [...args, '-I', '-B', '-c',
        'import sys,json; print(json.dumps([getattr(sys,"_base_executable",sys.executable),list(sys.version_info[:3])]))']));
      if (result[1][0] === 3 && result[1][1] >= 11) return { entry: result[0], version: result[1] };
    } catch { /* Try the next supported interpreter. */ }
  }
  throw fail('PYTHON_UNAVAILABLE', 'Install Python 3.11+ with pip or supply setup --python PATH');
}

const importScript = 'import sys; sys.path.insert(0,sys.argv.pop(1)); ';
const probeScript = importScript + 'import jqcli,click,httpx,flask,rich,json,sys; print(json.dumps({"package":jqcli.__version__,"version":sys.version.split()[0]}))';

export function verifyPython(directory) {
  const info = read(pythonMeta(directory));
  const result = JSON.parse(run(info.entry, ['-I', '-B', '-c', probeScript, path.join(directory, 'python')]));
  if (result.package !== info.package) throw fail('RUNTIME_VERSION_MISMATCH', 'Python package identity differs from its runtime receipt');
  return { ...result, entry: info.entry, available: true };
}

export function buildPython(packageRoot, destination, explicit) {
  const info = resolvePython(explicit);
  const vendor = path.join(destination, 'python');
  const build = fs.mkdtempSync(path.join(os.tmpdir(), 'jqcli-python-build-'));
  try {
    for (const item of ['pyproject.toml', 'README.md', 'jqcli']) {
      fs.cpSync(path.join(packageRoot, item), path.join(build, item), {
        recursive: true,
        filter: file => !/^(?:__pycache__|.*\.pyc)$/.test(path.basename(file)),
      });
    }
    run(info.entry, ['-I', '-B', '-m', 'pip', 'install', '--disable-pip-version-check', '--no-compile', '--retries', '1', '--timeout', '15', '--target', vendor, build], { timeout: 240000 });
  } finally {
    fs.rmSync(build, { force: true, recursive: true });
  }
  fs.writeFileSync(pythonMeta(destination), JSON.stringify({ ...info, package: read(path.join(packageRoot, 'package.json')).version }), { flag: 'wx' });
  return verifyPython(destination);
}

export function setup(explicit) {
  if (embedded) return verifyPython(root);
  if (exists(pythonMeta(bootstrap))) return verifyPython(bootstrap);
  fs.mkdirSync(path.dirname(bootstrap), { recursive: true, mode: 0o700 });
  const stage = fs.mkdtempSync(path.join(path.dirname(bootstrap), '.stage-'));
  try {
    const result = buildPython(root, stage, explicit);
    fs.renameSync(stage, bootstrap);
    return result;
  } finally {
    fs.rmSync(stage, { force: true, recursive: true });
  }
}

export function doctor() {
  let runtime;
  try { runtime = verifyPython(embedded ? root : bootstrap); }
  catch (error) { runtime = { available: false, code: error.code || 'RUNTIME_NOT_INSTALLED' }; }
  return {
    healthy: Number(process.versions.node.split('.')[0]) >= 22 && runtime.available,
    node: process.version, runtime, package: pkg.name, version: pkg.version,
    skill_source: source, configuration_required: true,
  };
}

export function business(args) {
  const directory = embedded ? root : bootstrap;
  if (!exists(pythonMeta(directory))) throw fail('RUNTIME_NOT_INSTALLED', 'Use the installed Skill runtime or run jqcli setup for the bootstrap CLI');
  const { entry } = read(pythonMeta(directory));
  const strategy = args.indexOf('strategy');
  const action = strategy < 0 ? null : args[strategy + 1];
  let pythonArgs = ['-I', '-B', '-X', 'utf8'];
  if (action === 'check' || action === 'scaffold') {
    const get = flag => {
      const index = args.indexOf(flag, strategy + 2);
      return index < 0 ? undefined : args[index + 1];
    };
    const input = action === 'check' ? get('--file') : get('--name');
    if (!input) throw fail('INPUT_REQUIRED', action === 'check' ? 'Use strategy check --file SOURCE' : 'Use strategy scaffold --name NAME --root DIR');
    const script = action === 'check' ? 'check_joinquant_strategy.py' : 'scaffold_strategy_workspace.py';
    // This operation intentionally uses the caller's working directory for relative input paths.
    pythonArgs.push(path.join(source, 'scripts', script), input);
    if (action === 'scaffold') pythonArgs.push('--root', get('--root') || '.');
  } else {
    pythonArgs.push('-c', importScript + 'from jqcli.cli import main; main()', path.join(directory, 'python'), ...args);
  }
  const result = spawnSync(entry, pythonArgs, { stdio: 'inherit' });
  if (result.error) throw fail('EXECUTABLE_UNAVAILABLE', 'Selected Python runtime is unavailable');
  return result.status ?? 1;
}
