import { defineConfig } from 'tsdown';

export default defineConfig({
  entry: ['src/index.ts'],
  format: 'esm',
  // fetch, streams, WebCrypto: runs anywhere they do (Node 22+, Bun, browsers).
  platform: 'neutral',
  target: 'es2023',
  dts: true,
  sourcemap: true,
  clean: true,
});
