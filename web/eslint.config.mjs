import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';
export default defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores(['.next/**', '.next-current/**','next-env.d.ts', 'public/maplibre-worker.js']),
  { rules: { 'react-hooks/set-state-in-effect': 'off' } },
]);
