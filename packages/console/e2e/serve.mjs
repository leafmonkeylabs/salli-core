#!/usr/bin/env node
/**
 * Serves a console build at /console as the Salli server does
 * (interfaces/api/console.py): files from the build, any other path the
 * console's index.html, and on every response the server's CSP and headers
 * (console-headers.json, which a server test holds to CONSOLE_HEADERS). The
 * API is not here: the accessibility, visual and CSP runs answer it from
 * fixtures (fixtures.ts).
 *
 *     node e2e/serve.mjs [dist] [port]
 */
import { createReadStream, readFileSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { extname, join, normalize, resolve } from 'node:path';

const dist = resolve(process.argv[2] ?? 'dist');
const port = Number.parseInt(process.argv[3] ?? '4173', 10); // eslint-disable-line no-restricted-syntax -- not money: TCP port
const headers = JSON.parse(readFileSync(new URL('./console-headers.json', import.meta.url), 'utf8'));
const TYPES = {
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
  '.txt': 'text/plain; charset=utf-8',
  '.json': 'application/json',
};

function file(path) {
  try {
    return statSync(path).isFile() ? path : undefined;
  } catch {
    return undefined;
  }
}

createServer((request, response) => {
  const url = new URL(request.url ?? '/', 'http://localhost');
  if (!url.pathname.startsWith('/console')) {
    response.writeHead(404, { 'Content-Type': 'text/plain' }).end('Not found');
    return;
  }
  const asked = decodeURIComponent(url.pathname.slice('/console'.length)).replace(/^\/+/, '');
  const relative = asked ? normalize(asked) : '';
  if (relative && (relative.startsWith('..') || relative.split('/').some((part) => part.startsWith('.')))) {
    response.writeHead(404, headers).end('Not found');
    return;
  }
  const found = relative ? file(join(dist, relative)) : undefined;
  const path = found ?? join(dist, 'index.html');
  if (!found && relative.startsWith('assets/')) {
    response.writeHead(404, headers).end('Not found');
    return;
  }
  response.writeHead(200, {
    ...headers,
    'Content-Type': TYPES[extname(path)] ?? 'application/octet-stream',
    'Cache-Control': relative.startsWith('assets/') ? 'public, max-age=31536000, immutable' : 'no-cache',
  });
  createReadStream(path).pipe(response);
}).listen(port, '127.0.0.1', () => {
  console.log(`Serving ${dist} at http://localhost:${port}/console`);
});
