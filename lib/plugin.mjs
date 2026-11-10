import path from 'node:path';
import { parseArgs } from 'node:util';
import { install, sourceInfo, status } from './lifecycle.mjs';
import { business, doctor, fail, name, pkg, read, root, setup } from './runtime.mjs';
import { checkUpdate, notifyUpdate, updateInstall, updateStatus } from './update.mjs';

export { root };
const manifest = read(path.join(root, 'capabilities.json'));
const { skills, discoveryContract, maintenanceContract, commandContracts } = manifest;
const sourceContract = { skills, discoveryContract, maintenanceContract, commandContracts };
const emit = result => console.log(JSON.stringify({ ...result, ok: true, result }));

const help = `jqcli | JoinQuant research CLI
  version | capabilities | doctor | setup [--python PATH]
  skill source [--name jqcli]
  skill status|install|update --agent NAME --target ABSOLUTE_PATH
  update status | update check [--tag latest|next]
  update install --agent NAME --target ABSOLUTE_PATH [--version VERSION] [--yes]
  strategy | backtest | live | auth | community | web
See INSTALL.md and UPDATE.md for the selected Agent lifecycle.
`;

export async function main(args = process.argv.slice(2)) {
  try {
    if (!args.length || (args.length === 1 && ['--help', '-h'].includes(args[0]))) {
      process.stdout.write(help);
      return 0;
    }
    if (args[0] === '--help' && args.length === 2 && args[1] === '--json') {
      emit(manifest);
      return 0;
    }
    const [first, second] = args;
    const action = first === '--version' ? 'version' : ['skill', 'update'].includes(first) ? first + ' ' + (second || '') : first;
    const contract = manifest.commandContracts[action];
    if (!contract) {
      if (['skill', 'update'].includes(first)) throw fail('COMMAND_UNKNOWN', 'Run jqcli --help for management commands');
      if (!args.some(value => ['--help', '-h'].includes(value)) && args.some(value => ['strategy', 'backtest'].includes(value))
        && !args.some(value => ['logs', 'wait', 'show', 'result', 'stats', 'positions', 'transactions'].includes(value))) {
        await notifyUpdate();
      }
      return business(args);
    }
    const trailing = args.slice(action.includes(' ') ? 2 : 1);
    if (trailing.includes('--help') && trailing.every(arg => ['--help', '--json'].includes(arg))) {
      if (trailing.includes('--json')) emit({ command: action, ...contract });
      else process.stdout.write('jqcli ' + action + ' ' + Object.keys(contract.options).join(' ') + '\n');
      return 0;
    }
    const accepted = Object.fromEntries(Object.entries(contract.options).map(([flag, spec]) => [flag.slice(2), { type: spec.type }]));
    let options;
    try { options = parseArgs({ args: trailing, options: accepted }).values; }
    catch (error) { throw fail('INVALID_ARGUMENT', error.message); }
    if (options.name && options.name !== name) throw fail('SKILL_UNKNOWN', 'Available Skill: jqcli');
    let result;
    switch (action) {
      case 'version': result = { package: pkg.name, version: pkg.version }; break;
      case 'capabilities': result = manifest; break;
      case 'doctor': result = doctor(); break;
      case 'setup': result = setup(options.python); break;
      case 'skill source': {
        const item = sourceInfo();
        result = { ...sourceContract, ...item, items: [{ ok: true, ...item }], complete: true };
        break;
      }
      case 'skill status': result = status(options); break;
      case 'skill install':
      case 'skill update': result = install(options); break;
      case 'update status': result = updateStatus(); break;
      case 'update check': result = await checkUpdate(options.tag); break;
      case 'update install': result = await updateInstall(options); break;
    }
    emit(result);
    return 0;
  } catch (error) {
    console.log(JSON.stringify({ ok: false, error: { code: error.code || 'OPERATION_FAILED', message: error.message, recovery: error.recovery } }));
    return 1;
  }
}
