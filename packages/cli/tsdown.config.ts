import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'tsdown';

const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')) as { version: string };

// One ESM file with a shebang, everything bundled (the SDK from source),
// except @napi-rs/keyring: a native module, installed with the package.
export default defineConfig({
  entry: { salli: 'src/bin.ts' },
  format: 'esm',
  platform: 'node',
  target: 'node22',
  outDir: 'dist',
  clean: true,
  dts: false,
  sourcemap: false,
  fixedExtension: false,
  banner: '#!/usr/bin/env node',
  alias: {
    '@leafmonkeylabs/salli-sdk': fileURLToPath(new URL('../sdk/src/index.ts', import.meta.url)),
  },
  define: {
    __SALLI_CLI_VERSION__: JSON.stringify(pkg.version),
  },
  deps: {
    neverBundle: ['@napi-rs/keyring'],
    onlyBundle: false,
  },
  outputOptions: {
    codeSplitting: false,
  },
});
