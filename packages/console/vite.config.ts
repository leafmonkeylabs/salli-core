/**
 * Building the console: static files for the server to serve at /console
 * (docs/design/console.md, sections 1 and 4).
 *
 * - Everything is a file: no asset is inlined as a data: URL (the CSP allows
 *   images and fonts from 'self' only) and no script or style is inline.
 * - Each hashed file gets .br and .gz copies beside it, which the server
 *   sends when the browser accepts them.
 * - `vite` (development) proxies the API, the sign-in pages and the
 *   well-known documents to a local server, so development is same-origin
 *   too: run the server with SALLI_PUBLIC_URL=http://localhost:5173.
 */
import { copyFileSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { brotliCompressSync, constants, gzipSync } from 'node:zlib';
import { defineConfig, type Plugin } from 'vite';

const sdk = fileURLToPath(new URL('../sdk/src/index.ts', import.meta.url));
const api = process.env.SALLI_DEV_SERVER ?? 'http://localhost:8000';

const require = createRequire(import.meta.url);

/** The OFL travels with the fonts it covers: licences/ beside the build. */
const FONT_LICENCES: Record<string, string> = {
  'geist.txt': '@fontsource-variable/geist/LICENSE',
  'geist-mono.txt': '@fontsource/geist-mono/LICENSE',
};

/** Writes .br and .gz beside each built asset, and the fonts' licences. */
function precompress(): Plugin {
  let outDir = 'dist';
  return {
    name: 'salli-precompress',
    apply: 'build',
    configResolved(config) {
      outDir = config.build.outDir;
    },
    closeBundle() {
      const assets = join(outDir, 'assets');
      for (const name of readdirSync(assets)) {
        const path = join(assets, name);
        if (!statSync(path).isFile() || /\.(br|gz|woff2?)$/.test(name)) continue;
        const data = readFileSync(path);
        writeFileSync(`${path}.br`, brotliCompressSync(data, { params: { [constants.BROTLI_PARAM_QUALITY]: 11 } }));
        writeFileSync(`${path}.gz`, gzipSync(data, { level: 9 }));
      }
      mkdirSync(join(outDir, 'licences'), { recursive: true });
      for (const [name, from] of Object.entries(FONT_LICENCES)) copyFileSync(require.resolve(from), join(outDir, 'licences', name));
      copyFileSync('NOTICE', join(outDir, 'licences', 'NOTICE.txt'));
    },
  };
}

export default defineConfig({
  base: '/console/',
  resolve: {
    alias: { '@leafmonkeylabs/salli-sdk': sdk },
  },
  build: {
    outDir: 'dist',
    target: 'es2022',
    assetsInlineLimit: 0,
    manifest: true,
    modulePreload: { polyfill: false },
    sourcemap: false,
    reportCompressedSize: false,
    rolldownOptions: {
      // React libraries mark modules "use client" for server rendering,
      // which a client-only bundle has no use for.
      onLog(level, log, handler) {
        if (log.code === 'MODULE_LEVEL_DIRECTIVE') return;
        handler(level, log);
      },
    },
  },
  plugins: [precompress()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: Object.fromEntries(['/v1', '/mcp', '/.well-known', '/healthz'].map((path) => [path, { target: api, changeOrigin: false }])),
  },
});
