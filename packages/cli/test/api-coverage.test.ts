/**
 * Anything the API lets a person do, `salli` can do.
 *
 * Every operation in openapi/openapi.json must be reached by the CLI, or be
 * listed in EXEMPT with the reason a person never calls it. The check reads
 * the source rather than running commands: an operation counts as reached
 * when a CLI module imports its generated SDK function (type-only imports do
 * not count), or imports an SDK helper that wraps it. CI already proves the
 * generated SDK matches openapi.json (`npm run check:generated`), so the chain
 * from the API document to a command is closed.
 *
 * Adding a route therefore means adding its command, or writing down here why
 * it has none.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { describe, expect, it } from 'vitest';

const ROOT = fileURLToPath(new URL('../../../', import.meta.url));
const SDK_PACKAGE = '@leafmonkeylabs/salli-sdk';

/** Operations no `salli` command calls, and why. */
const EXEMPT: Record<string, string> = {
  'meta.health': 'liveness probe for the host or load balancer',
  'oauth.authorizationServerMetadata': 'OAuth discovery (RFC 8414); `salli login` reads the same endpoints from /v1/meta',
  'oauth.protectedResourceMetadata': 'OAuth discovery (RFC 9728), for MCP clients',
  'oauth.register': 'OAuth protocol: `salli login` reaches it through the SDK’s oauth module, at the URL /v1/meta names',
  'oauth.authorize': 'OAuth protocol: the browser step of `salli login`, at the URL /v1/meta names',
  'oauth.deviceAuthorization': 'OAuth protocol: `salli login --device`, at the URL /v1/meta names',
  'oauth.token': 'OAuth protocol: token exchange and refresh, at the URL /v1/meta names',
  'oauth.revoke': 'OAuth protocol: `salli logout` revokes at the URL /v1/meta names',
  'oauth.consentInfo': 'read by a web app’s MCP consent screen, not by a person',
  'oauth.consent': 'submitted by a web app’s MCP consent screen, not by a person',
  'advisor.cron.runDue': 'for the server’s scheduler, authenticated by X-Cron-Secret; operators run `salli-server jobs run-advisor`',
  'bankConnections.cron.syncDue': 'for the server’s scheduler, authenticated by X-Cron-Secret; operators run `salli-server jobs sync-banks`',
  'accounts.get': '`salli accounts show` uses accounts.overview, which returns the same account with its balances',
  'onboarding.goals': 'the onboarding wizard’s batch form of goals.create; `salli goals add` adds goals one at a time',
};

/** SDK helpers that wrap an operation, and the operations each one calls. */
const VIA_SDK_HELPER: Record<string, readonly string[]> = {
  streamAgentChat: ['agent.chat'],
  streamAgentResume: ['agent.resume'],
  streamStrategyGeneration: ['fi.strategy.generate'],
  // Every client checks the server's API version through /v1/meta.
  createClient: ['meta.get'],
};

interface Operation {
  id: string;
  method: string;
  path: string;
}

function operations(): Operation[] {
  const spec = JSON.parse(readFileSync(join(ROOT, 'openapi/openapi.json'), 'utf8')) as {
    paths: Record<string, Record<string, { operationId?: string }>>;
  };
  return Object.entries(spec.paths).flatMap(([path, ops]) =>
    Object.entries(ops).map(([method, op]) => ({ id: op.operationId ?? `${method} ${path}`, method: method.toUpperCase(), path })),
  );
}

function parse(file: string): ts.SourceFile {
  return ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
}

/** "GET /v1/accounts/" → "accountsList", from the generated SDK's own source. */
function generatedFunctions(): Map<string, string> {
  const byRoute = new Map<string, string>();
  const source = parse(join(ROOT, 'packages/sdk/src/generated/sdk.gen.ts'));
  for (const statement of source.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (!ts.isIdentifier(declaration.name) || !declaration.initializer) continue;
      const name = declaration.name.text;
      const visit = (node: ts.Node): void => {
        if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)) {
          const method = node.expression.name.text.toUpperCase();
          const options = node.arguments[0];
          if (options && ts.isObjectLiteralExpression(options)) {
            for (const prop of options.properties) {
              if (ts.isPropertyAssignment(prop) && ts.isIdentifier(prop.name) && prop.name.text === 'url' && ts.isStringLiteral(prop.initializer)) {
                byRoute.set(`${method} ${prop.initializer.text}`, name);
              }
            }
          }
        }
        ts.forEachChild(node, visit);
      };
      visit(declaration.initializer);
    }
  }
  return byRoute;
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true, recursive: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.ts'))
    .map((entry) => join(entry.parentPath, entry.name));
}

/** Every value the CLI imports from the SDK (not `type` imports). */
function cliImports(): Set<string> {
  const names = new Set<string>();
  for (const file of sourceFiles(join(ROOT, 'packages/cli/src'))) {
    for (const statement of parse(file).statements) {
      if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) continue;
      if (statement.moduleSpecifier.text !== SDK_PACKAGE) continue;
      const clause = statement.importClause;
      if (!clause || clause.isTypeOnly) continue;
      const bindings = clause.namedBindings;
      if (bindings && ts.isNamedImports(bindings)) {
        for (const element of bindings.elements) {
          if (!element.isTypeOnly) names.add((element.propertyName ?? element.name).text);
        }
      }
    }
  }
  return names;
}

/** The hand-written SDK module that exports `name`, as text. */
function helperSource(name: string): string | undefined {
  const declared = new RegExp(`export (async )?function\\*? ${name}\\b`);
  for (const file of sourceFiles(join(ROOT, 'packages/sdk/src'))) {
    if (file.includes('/generated/')) continue;
    const text = readFileSync(file, 'utf8');
    if (declared.test(text)) return text;
  }
  return undefined;
}

const ops = operations();
const functions = generatedFunctions();
const functionOf = (op: Operation): string | undefined => functions.get(`${op.method} ${op.path}`);
const imported = cliImports();
const viaHelper = new Set(Object.entries(VIA_SDK_HELPER).flatMap(([helper, ids]) => (imported.has(helper) ? ids : [])));
const reached = (op: Operation): boolean => {
  const fn = functionOf(op);
  return (fn !== undefined && imported.has(fn)) || viaHelper.has(op.id);
};

describe('the CLI covers the API', () => {
  it('finds a generated SDK function for every operation', () => {
    expect(ops.length).toBeGreaterThan(100);
    expect(ops.filter((op) => !functionOf(op)).map((op) => op.id)).toEqual([]);
  });

  it('reaches every operation, or says why a person never calls it', () => {
    const missing = ops.filter((op) => !reached(op) && !(op.id in EXEMPT)).map((op) => `${op.id} (${op.method} ${op.path})`);
    expect(missing, 'Add a `salli` command for these, or list them in EXEMPT with a reason').toEqual([]);
  });

  it('exempts only operations that exist and that no command reaches', () => {
    const ids = new Set(ops.map((op) => op.id));
    expect(Object.keys(EXEMPT).filter((id) => !ids.has(id)), 'stale exemptions').toEqual([]);
    const covered = ops.filter((op) => op.id in EXEMPT && reached(op)).map((op) => op.id);
    expect(covered, 'reached by a command now: drop the exemption').toEqual([]);
    expect(Object.entries(EXEMPT).filter(([, why]) => !why.trim())).toEqual([]);
  });

  it('counts an SDK helper only when the CLI uses it and it calls what it is said to', () => {
    for (const [helper, ids] of Object.entries(VIA_SDK_HELPER)) {
      expect(imported.has(helper), `the CLI no longer imports ${helper}`).toBe(true);
      const source = helperSource(helper);
      expect(source, `no SDK module exports ${helper}`).toBeDefined();
      for (const id of ids) {
        const op = ops.find((o) => o.id === id);
        const fn = op && functionOf(op);
        expect(fn, `${id} is not an operation`).toBeDefined();
        const dataType = `${fn!.charAt(0).toUpperCase()}${fn!.slice(1)}Data`;
        expect(source!.includes(fn!) || source!.includes(dataType), `${helper} does not call ${id}`).toBe(true);
      }
    }
  });
});
