import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { digest, hashes } from '../lib/lifecycle.mjs';
import { name, pkg, read, root, source } from '../lib/runtime.mjs';

const releaseFile = path.join(root, 'release-integrity.json');
const metadata = ['capabilities.json', 'skills/jqcli/capabilities.json'];
const python = [
  ['pyproject.toml', /^version = "([^"]+)"/m],
  ['jqcli/__init__.py', /^__version__ = "([^"]+)"/m],
];

if (process.argv[2] === 'sync') {
  for (const item of metadata) {
    const file = path.join(root, item);
    const value = read(file);
    value.version = pkg.version;
    fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n');
  }
  for (const [item, pattern] of python) {
    const file = path.join(root, item);
    const original = fs.readFileSync(file, 'utf8');
    assert.match(original, pattern);
    fs.writeFileSync(file, original.replace(pattern, (match, version) => match.replace(version, pkg.version)));
  }
}

for (const item of metadata) assert.equal(read(path.join(root, item)).version, pkg.version, item);
for (const [item, pattern] of python) assert.equal(fs.readFileSync(path.join(root, item), 'utf8').match(pattern)?.[1], pkg.version, item);

const skill = hashes(source, { ignoreGenerated: true });
const runtime = { ...Object.fromEntries(Object.entries(skill).map(([key, value]) => ['skills/' + name + '/' + key, value])) };
for (const dir of ['bin', 'lib', 'jqcli']) {
  const files = hashes(path.join(root, dir), { ignoreGenerated: true });
  for (const [key, value] of Object.entries(files)) runtime[dir + '/' + key] = value;
}
for (const item of ['README.md', 'INSTALL.md', 'UPDATE.md', 'LICENSE', 'package.json', 'pyproject.toml', 'capabilities.json', 'scripts/install-notice.mjs', 'scripts/release-identity.mjs']) {
  runtime[item] = digest(path.join(root, item));
}
const release = {
  package: pkg.name, version: pkg.version, algorithm: 'sha256',
  files: { ...skill, ...Object.fromEntries(Object.entries(runtime).map(([key, value]) => ['.runtime/' + key, value])) },
};
if (process.argv[2] === 'sync') fs.writeFileSync(releaseFile, JSON.stringify(release, null, 2) + '\n');
else assert.deepEqual(read(releaseFile), release, 'Release inventory drift; reconcile canonical files and version');
