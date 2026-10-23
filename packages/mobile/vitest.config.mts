import { defineConfig } from 'vitest/config';

// The app's plain TypeScript (src/lib): what it does with an address, a
// sign-in's PKCE and an amount, without React Native.
export default defineConfig({
  resolve: {
    alias: { '@leafmonkeylabs/salli-sdk': new URL('../sdk/src/index.ts', import.meta.url).pathname },
  },
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
  },
});
