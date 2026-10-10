import { stat } from 'node:fs/promises';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { parseCredentials, serializeCredentials, type StoredCredentials } from '../src/auth/credentials';
import { FileStore, openSecretStore } from '../src/auth/store';
import { tempConfigDir } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
});
afterEach(async () => {
  await cleanup();
});

describe('FileStore', () => {
  it('keeps one secret per context in a file only its owner can read', async () => {
    const store = new FileStore(dir);
    expect(await store.get('home')).toBeUndefined();
    await store.set('home', 'one');
    await store.set('work', 'two');
    expect(await store.get('home')).toBe('one');
    expect((await stat(join(dir, 'credentials.json'))).mode & 0o777).toBe(0o600);
    expect(await store.delete('home')).toBe(true);
    expect(await store.delete('home')).toBe(false);
    expect(await store.get('work')).toBe('two');
  });
});

describe('openSecretStore', () => {
  it('uses the file when asked to', async () => {
    const { store } = await openSecretStore({ env: { SALLI_CREDENTIAL_STORE: 'file' }, platform: 'linux', configDir: dir });
    expect(store.kind).toBe('file');
  });

  it('refuses the command store where there is no command for it', async () => {
    await expect(openSecretStore({ env: { SALLI_CREDENTIAL_STORE: 'command' }, platform: 'win32', configDir: dir })).rejects.toThrow(/needs macOS/);
  });
});

describe('stored credentials', () => {
  it('round-trip, and anything malformed reads as signed out', () => {
    const oauth: StoredCredentials = {
      kind: 'oauth',
      server: 'https://salli.example.com',
      client_id: 'client-1',
      token_endpoint: 'https://salli.example.com/mcp/oauth/token',
      method: 'browser',
      tokens: { access_token: 'at', refresh_token: 'rt', expires_at: 1 },
      signed_in_at: '2026-10-09T10:00:00.000Z',
    };
    expect(parseCredentials(serializeCredentials(oauth))).toEqual(oauth);
    expect(parseCredentials('{"kind":"token","server":"x","token":"t","signed_in_at":"y"}')).toMatchObject({ kind: 'token' });
    expect(parseCredentials('not json')).toBeUndefined();
    expect(parseCredentials('{"kind":"oauth","server":"x"}')).toBeUndefined();
    expect(parseCredentials(undefined)).toBeUndefined();
  });
});
