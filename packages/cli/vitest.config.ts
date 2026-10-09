import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    alias: {
      '@leafmonkeylabs/salli-sdk': fileURLToPath(new URL('../sdk/src/index.ts', import.meta.url)),
    },
  },
  define: {
    __SALLI_CLI_VERSION__: JSON.stringify('0.1.0-test'),
  },
  test: {
    include: ['test/**/*.test.ts'],
    testTimeout: 15_000,
  },
});
