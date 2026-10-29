import { cp, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
// O build standalone não copia assets automaticamente fora da imagem Docker.
const root = resolve(import.meta.dirname, '..');
await mkdir(resolve(root, '.next/standalone/.next'), { recursive: true });
await cp(resolve(root, '.next/static'), resolve(root, '.next/standalone/.next/static'), {
  recursive: true,
});
await cp(resolve(root, 'public'), resolve(root, '.next/standalone/public'), { recursive: true });
process.env.HOSTNAME ||= '127.0.0.1';
process.env.PORT ||= '3000';
await import(pathToFileURL(resolve(root, '.next/standalone/server.js')).href);
