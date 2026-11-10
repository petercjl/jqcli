import fs from 'node:fs';
import { setTimeout } from 'node:timers/promises';

const { name } = JSON.parse(fs.readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const [version, tag, mode] = process.argv.slice(2);
if (!/^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/.test(version) || !['latest', 'next'].includes(tag)) {
  throw new Error('Supply an exact release version and npm tag');
}
const url = new URL(encodeURIComponent(name), 'https://registry.npmjs.org/');
async function observe() {
  url.searchParams.set('releaseCheck', String(Date.now()));
  const response = await fetch(url, { headers: { 'Cache-Control': 'no-cache' }, signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error('npm metadata HTTP ' + response.status);
  const packument = await response.json();
  return {
    published: !!packument.versions?.[version]?.dist?.integrity,
    tagVersion: packument['dist-tags']?.[tag] ?? null,
  };
}
if (mode === 'check-absent') {
  const observed = await observe();
  if (observed.published) throw new Error(name + '@' + version + ' already exists; inspect the tag without uploading again');
  console.log(JSON.stringify(observed));
} else {
  let observed;
  // Public npm metadata can lag behind a successful OIDC publish.
  const attempts = 40;
  for (let attempt = 0; attempt < attempts; attempt++) {
    try { observed = await observe(); }
    catch (error) { observed = { error: error.message }; }
    if (observed.published && observed.tagVersion === version) break;
    if (attempt + 1 < attempts) await setTimeout(15000);
  }
  console.log(JSON.stringify({ name, version, tag, ...observed }));
  if (!observed.published || observed.tagVersion !== version) process.exitCode = 1;
}
