/** Keep MapLibre's module worker outside Turbopack's transformed chunk URLs. */
import { copyFile, mkdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const packageRoot = dirname(require.resolve('maplibre-gl/package.json'));
const publicRoot = resolve(webRoot, 'public');

await mkdir(publicRoot, { recursive: true });
await copyFile(
  resolve(packageRoot, 'dist/maplibre-gl-worker.mjs'),
  resolve(publicRoot, 'maplibre-worker.js'),
);
await copyFile(
  resolve(packageRoot, 'LICENSE.txt'),
  resolve(publicRoot, 'maplibre-worker.LICENSE.txt'),
);
console.log('MapLibre module worker and license copied to public/.');
