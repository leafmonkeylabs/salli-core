# The Salli console

Your books in a browser: the pages a self-hosted household uses to see where
it stands, served by the Salli server at `{SALLI_PUBLIC_URL}/console`.
`salli ui` opens it. The design, and every decision behind it, is
[docs/design/console.md](../../docs/design/console.md).

The console is a client of the API, like the `salli` command:

- **It computes nothing.** Every figure is the server's, shown exactly, with
  where it came from. Amounts stay decimal strings from the response to the
  screen (`<Money>`); the console does no arithmetic on money, not even
  exact arithmetic. One module, `src/kit/chart/geometry.ts`, may turn an
  amount into a number, only to place a point on a chart.
- **Data comes only through the SDK** (`@leafmonkeylabs/salli-sdk`): no URL
  by hand, no response type of its own.
- **It adds no feature the CLI lacks**, and ranks nothing.

Licence: [AGPL-3.0-only](LICENSE), like the server. The SDK it is built on is
Apache-2.0, for anyone building their own UI.

## Working on it

From the repository's root (one npm workspace):

```bash
npm ci
npm run dev --workspace @leafmonkeylabs/salli-console      # http://localhost:5173/console
npm run build --workspace @leafmonkeylabs/salli-console    # dist/, then the budget check
npm test --workspace @leafmonkeylabs/salli-console          # component tests (Vitest, jsdom)
```

`vite` proxies `/v1`, `/mcp` and `/.well-known` to a local server
(`SALLI_DEV_SERVER`, default `http://localhost:8000`) so development is
same-origin. Start that server with `SALLI_PUBLIC_URL=http://localhost:5173`,
or the console moves to the public URL's origin before signing in.

To serve a build from a source checkout, point the server at it:
`SALLI_CONSOLE_DIR=packages/console/dist uv run salli-server serve`.

### Tests

| What | Where | Run |
|---|---|---|
| Components and pages, on fixtures the server writes | `test/` | `npm test` |
| The fixtures themselves | `test/fixtures/home.ts` and `lab.ts`, from `tests/console_fixtures.py` | `uv run python -m tests.console_fixtures` (write), `--check` |
| Nothing in the decision lab ranks | `test/lab-guards.test.tsx`: `tests/guardrails.py`'s words over the lab's catalogue and its rendered pages | `npm test` |
| Accessibility (axe), visual regression, CSP and request checks | `e2e/console.spec.ts`, `e2e/lab.spec.ts` | `npm run e2e` (in the Playwright image for screenshots; see below) |
| End to end against `compose.yaml` | `e2e/compose.spec.ts` | `npm run e2e:compose` |
| The budget | `scripts/budget.mjs` | part of `npm run build` |

Screenshots are compared pixel for pixel, so they are made in Playwright's
Linux image, as CI makes them:

```bash
docker run --rm --ipc=host -v "$PWD":/work -w /work/packages/console \
  mcr.microsoft.com/playwright:v1.63.0-noble \
  npx playwright test --project=fixtures --update-snapshots
```

## Rules

- **Every word in the catalogue**, `src/strings.ts` (the decision lab's in
  `src/lab-strings.ts`, which loads with its pages), in the brand's voice
  ([docs/brand/README.md](../../docs/brand/README.md)): British English,
  sentence case, no exclamation marks, nothing that ranks or urges.
- **Text is rendered only through React.** No `innerHTML`, no
  `dangerouslySetInnerHTML`, no `eval`: lint refuses them, with no escape.
  The console runs under a strict CSP with Trusted Types and no policy; no
  inline script or style, no third-party request, no telemetry, no service
  worker.
- **Colours only from `src/styles/tokens.css`**, the code copy of the brand's
  tables. Charts draw the baseline in ink and options in ledger green and
  graphite (dashed); the focus ring is ledger green, sand on dark.
- **No firm or billing words** in the open console: the guards in
  `tests/contract` scan `packages/*/src`.
- **Pinned dependencies**, exact versions, and as few as the budget allows
  (decision 14: 150 kB compressed for the shell and Home, 75 kB a page,
  500 kB in all, 40 kB of CSS).

## Building an edition

An edition imports this package and passes its extensions to
`createConsole`, which builds them into one bundle with the open console:

```ts
import '@leafmonkeylabs/salli-console/styles.css';
import { createConsole, type ConsoleExtension } from '@leafmonkeylabs/salli-console';

const example: ConsoleExtension = {
  requires: 'example', // the server extension it belongs to, as /v1/meta lists it
  routes: [{ path: '/example', load: () => import('./ExamplePage') }],
  navigation: [{ to: '/example', label: 'Example' }],
  settingsPanels: [{ id: 'example', title: 'Example', component: ExampleSettings }],
};

createConsole({ extensions: [example] }).mount(document.getElementById('root')!);
```

Its pages appear only when the server runs that extension. The kit
(`Money`, `Table`, `Page`, `Section`, `TextField`, `Confirm`, `ChartFigure`
and the rest) is exported, so its pages read and look like the console's own.
