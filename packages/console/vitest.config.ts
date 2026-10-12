import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    alias: {
      '@leafmonkeylabs/salli-sdk': fileURLToPath(new URL('../sdk/src/index.ts', import.meta.url)),
    },
  },
  test: {
    include: ['test/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: ['test/setup.ts'],
    testTimeout: 15_000,
    // Dates are shown in local time: pin it, so tests read the same everywhere.
    env: { TZ: 'UTC' },
    css: false,
  },
});
