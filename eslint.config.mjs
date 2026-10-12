// Lint for the TypeScript packages (packages/*). The Python code has its own
// linter (ruff), and the CLA bot under .github/ is plain CommonJS with its own
// tests.
import js from '@eslint/js';
import { defineConfig } from 'eslint/config';
import globals from 'globals';
import tseslint from 'typescript-eslint';

// Money is a decimal string from the API to the screen. Converting one to a
// JavaScript number (a binary float) is how 0.1 + 0.2 bugs get in, so these
// conversions are refused everywhere. A genuine non-money number (a port, a
// count, a timeout) is allowed with a reason the guard test checks for:
//
//   // eslint-disable-next-line no-restricted-syntax -- not money: TCP port
// The console renders text an agent or a bank wrote (payees, rule-set
// sources, decision notes), so it renders only through React's escaping:
// no HTML from strings, no code from strings. These have no escape hatch
// (packages/console/test/guards.test.ts fails on a disable comment for them).
const HTML_SINK = 'The console renders text only through React, never as HTML (docs/design/console.md, section 2).';
const htmlSinks = {
  meta: { type: 'problem', schema: [], messages: { sink: HTML_SINK } },
  create(context) {
    const HTML_PROPERTIES = new Set(['innerHTML', 'outerHTML', 'srcdoc']);
    const HTML_METHODS = new Set(['insertAdjacentHTML', 'createContextualFragment', 'setHTMLUnsafe', 'parseHTMLUnsafe', 'write', 'writeln']);
    const nameOf = (node) => (node.type === 'Identifier' ? node.name : node.type === 'Literal' ? String(node.value) : undefined);
    return {
      JSXAttribute(node) {
        if (node.name.name === 'dangerouslySetInnerHTML') context.report({ node, messageId: 'sink' });
      },
      Property(node) {
        if (nameOf(node.key) === 'dangerouslySetInnerHTML') context.report({ node, messageId: 'sink' });
      },
      MemberExpression(node) {
        const name = nameOf(node.property);
        if (name && HTML_PROPERTIES.has(name)) context.report({ node, messageId: 'sink' });
        if (name && HTML_METHODS.has(name) && (name !== 'write' && name !== 'writeln' ? true : nameOf(node.object) === 'document')) {
          context.report({ node, messageId: 'sink' });
        }
      },
    };
  },
};

const NOT_MONEY =
  'Amounts stay decimal strings: format them with formatAmount(), never convert them to numbers. ' +
  'For a value that is not money, add `// eslint-disable-next-line no-restricted-syntax -- not money: <why>`.';

export default defineConfig(
  {
    ignores: [
      '**/node_modules/**',
      '**/dist/**',
      '**/coverage/**',
      'packages/sdk/src/generated/**',
      '.github/**',
      '.venv/**',
      'src/**',
      'tests/**',
    ],
  },
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    files: ['packages/**/*.{ts,tsx,mts,mjs,js}'],
    languageOptions: {
      globals: globals.node,
    },
    rules: {
      'no-restricted-syntax': [
        'error',
        { selector: "CallExpression[callee.name='Number']", message: NOT_MONEY },
        { selector: "CallExpression[callee.name='parseFloat']", message: NOT_MONEY },
        { selector: "CallExpression[callee.name='parseInt']", message: NOT_MONEY },
        {
          selector: "CallExpression[callee.object.name='Number'][callee.property.name=/^parse(Float|Int)$/]",
          message: NOT_MONEY,
        },
        {
          selector: "UnaryExpression[operator='+'][argument.type!='Literal']",
          message: `Unary + converts to a float. ${NOT_MONEY}`,
        },
      ],
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrors: 'none' },
      ],
    },
  },
  {
    // The console runs in a browser: the money rules above apply under its
    // globals, with no HTML and no code from strings.
    files: ['packages/console/src/**/*.{ts,tsx}'],
    languageOptions: {
      globals: globals.browser,
    },
    plugins: { salli: { rules: { 'no-html-sinks': htmlSinks } } },
    rules: {
      'salli/no-html-sinks': 'error',
      'no-eval': 'error',
      'no-implied-eval': 'error',
      'no-new-func': 'error',
      'no-script-url': 'error',
    },
  },
  {
    files: ['packages/**/test/**/*.{ts,tsx}', 'packages/console/e2e/**/*.ts'],
    rules: {
      '@typescript-eslint/no-non-null-assertion': 'off',
    },
  },
);
