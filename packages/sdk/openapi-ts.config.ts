// Generates src/generated from the API contract committed at the repository
// root. Run `npm run generate` after the contract changes; CI fails when the
// committed output and a fresh generation differ.
import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  input: '../../openapi/openapi.json',
  output: {
    path: 'src/generated',
    // Deterministic output: no formatter, so regeneration is byte-for-byte
    // reproducible on any machine.
    postProcess: [],
  },
  plugins: ['@hey-api/client-fetch', '@hey-api/typescript', '@hey-api/sdk'],
});
