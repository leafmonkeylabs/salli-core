/**
 * Where a server's AI conversations are kept: a file of the app's own,
 * under its documents, named for the server as its keychain keys are.
 */
import { File, Paths } from 'expo-file-system';
import { storeKeyOf } from '../lib/servers';

export function conversationsFile(server: string): File {
  return new File(Paths.document, `ai-${storeKeyOf(server, 'mcp').slice('salli.mcp.'.length)}.json`);
}
