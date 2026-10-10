import http from 'node:http';
import type { AddressInfo } from 'node:net';

export interface RecordedRequest {
  method: string;
  path: string;
  headers: http.IncomingHttpHeaders;
  body: string;
}

export type Handler = (
  request: RecordedRequest,
  response: http.ServerResponse,
) => void | Promise<void>;

export interface TestServer {
  url: string;
  requests: RecordedRequest[];
  close(): Promise<void>;
}

/** An HTTP server on a free loopback port that records what it receives. */
export async function startServer(handler: Handler): Promise<TestServer> {
  const requests: RecordedRequest[] = [];
  const server = http.createServer((req, res) => {
    const chunks: Buffer[] = [];
    req.on('data', (chunk: Buffer) => chunks.push(chunk));
    req.on('end', () => {
      const recorded: RecordedRequest = {
        method: req.method ?? 'GET',
        path: req.url ?? '/',
        headers: req.headers,
        body: Buffer.concat(chunks).toString('utf8'),
      };
      requests.push(recorded);
      Promise.resolve(handler(recorded, res)).catch((error: unknown) => {
        res.statusCode = 500;
        res.end(String(error));
      });
    });
  });
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address() as AddressInfo;
  return {
    url: `http://127.0.0.1:${port}`,
    requests,
    close: () =>
      new Promise<void>((resolve) => {
        server.closeAllConnections();
        server.close(() => resolve());
      }),
  };
}

export function sendJson(
  response: http.ServerResponse,
  status: number,
  body: unknown,
  headers: Record<string, string> = {},
): void {
  const text = typeof body === 'string' ? body : JSON.stringify(body);
  response.writeHead(status, { 'Content-Type': 'application/json', ...headers });
  response.end(text);
}

export function sendProblem(
  response: http.ServerResponse,
  status: number,
  problem: { type?: string; title: string; detail?: unknown },
): void {
  response.writeHead(status, { 'Content-Type': 'application/problem+json' });
  response.end(JSON.stringify({ type: problem.type ?? 'about:blank', status, ...problem }));
}
