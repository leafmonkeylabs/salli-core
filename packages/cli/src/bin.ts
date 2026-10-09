/**
 * The `salli` executable.
 */
import { InterruptedError } from './errors';
import { main } from './main';
import { processRuntime } from './runtime';

const controller = new AbortController();
let interrupted = false;
process.on('SIGINT', () => {
  // A second Ctrl-C does not wait for anything.
  if (interrupted) process.exit(130);
  interrupted = true;
  controller.abort(new InterruptedError());
});

// Lets output finish (a pipe on macOS is written asynchronously) before exiting.
function flushed(stream: NodeJS.WriteStream): Promise<void> {
  return new Promise((resolve) => {
    if (stream.destroyed || !stream.writable) resolve();
    else stream.write('', () => resolve());
  });
}

const code = await main(process.argv.slice(2), processRuntime(controller.signal));
await Promise.all([flushed(process.stdout), flushed(process.stderr)]);
process.exit(interrupted && code === 0 ? 130 : code);
