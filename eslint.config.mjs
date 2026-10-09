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
      'supabase/**',
    ],
  },
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    files: ['packages/**/*.{ts,mts,mjs,js}'],
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
    files: ['packages/**/test/**/*.ts'],
    rules: {
      '@typescript-eslint/no-non-null-assertion': 'off',
    },
  },
);
