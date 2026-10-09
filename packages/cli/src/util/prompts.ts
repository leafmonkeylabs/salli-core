/**
 * Questions for the user, asked on stderr (stdout stays the command's
 * result). Only in a terminal: a script that would have to answer gets a
 * usage error naming the flag that answers instead.
 */
import * as clack from '@clack/prompts';
import { InterruptedError, UsageError } from '../errors';
import type { InputStream, OutputStream } from '../runtime';

export interface Choice<T> {
  value: T;
  label: string;
  hint?: string;
}

export interface Spinner {
  start(message: string): void;
  message(message: string): void;
  stop(message?: string): void;
}

export interface Prompter {
  /** Whether questions can be asked (stdin and stderr are terminals). */
  readonly interactive: boolean;
  confirm(options: { message: string; initialValue?: boolean }): Promise<boolean>;
  text(options: {
    message: string;
    placeholder?: string;
    initialValue?: string;
    validate?: (value: string) => string | undefined;
  }): Promise<string>;
  password(options: { message: string }): Promise<string>;
  select<T>(options: { message: string; options: Choice<T>[]; initialValue?: T }): Promise<T>;
  /** A select with type-to-filter, for long lists (accounts). */
  search<T>(options: { message: string; options: Choice<T>[]; placeholder?: string; initialValue?: T }): Promise<T>;
  spinner(): Spinner;
}

function unwrap<T>(value: T | symbol): Exclude<T, symbol> {
  if (clack.isCancel(value)) throw new InterruptedError();
  return value as Exclude<T, symbol>;
}

/** Prompts drawn by @clack/prompts on stderr. */
export class ClackPrompter implements Prompter {
  readonly interactive: boolean;
  private readonly io: { input: InputStream; output: OutputStream };

  constructor(input: InputStream, output: OutputStream, env: Record<string, string | undefined>) {
    this.io = { input, output };
    this.interactive = input.isTTY === true && output.isTTY === true && !env.CI && env.SALLI_NO_INPUT !== '1';
  }

  async confirm(options: { message: string; initialValue?: boolean }): Promise<boolean> {
    return unwrap(
      await clack.confirm({ ...this.io, message: options.message, initialValue: options.initialValue ?? false }),
    );
  }

  async text(options: {
    message: string;
    placeholder?: string;
    initialValue?: string;
    validate?: (value: string) => string | undefined;
  }): Promise<string> {
    const validate = options.validate;
    return unwrap(
      await clack.text({
        ...this.io,
        message: options.message,
        ...(options.placeholder !== undefined ? { placeholder: options.placeholder } : {}),
        ...(options.initialValue !== undefined ? { initialValue: options.initialValue } : {}),
        ...(validate ? { validate: (value: string | undefined) => validate(value ?? '') } : {}),
      }),
    );
  }

  async password(options: { message: string }): Promise<string> {
    return unwrap(await clack.password({ ...this.io, message: options.message }));
  }

  async select<T>(options: { message: string; options: Choice<T>[]; initialValue?: T }): Promise<T> {
    return unwrap<T>(
      await clack.select<T>({
        ...this.io,
        message: options.message,
        options: options.options as Parameters<typeof clack.select<T>>[0]['options'],
        ...(options.initialValue !== undefined ? { initialValue: options.initialValue } : {}),
      }),
    );
  }

  async search<T>(options: { message: string; options: Choice<T>[]; placeholder?: string; initialValue?: T }): Promise<T> {
    return unwrap<T>(
      await clack.autocomplete<T>({
        ...this.io,
        message: options.message,
        options: options.options as Parameters<typeof clack.autocomplete<T>>[0]['options'],
        maxItems: 8,
        ...(options.placeholder !== undefined ? { placeholder: options.placeholder } : {}),
        ...(options.initialValue !== undefined ? { initialValue: options.initialValue } : {}),
      }),
    );
  }

  spinner(): Spinner {
    if (!this.interactive) return { start: () => undefined, message: () => undefined, stop: () => undefined };
    const s = clack.spinner({ output: this.io.output });
    return {
      start: (message) => s.start(message),
      message: (message) => s.message(message),
      stop: (message) => s.stop(message),
    };
  }
}

/** Fails with the flag to use when a question cannot be asked. */
export function requireInteractive(prompter: Prompter, needed: string): void {
  if (!prompter.interactive) {
    throw new UsageError(`This needs an answer, and there is no terminal to ask in.`, needed);
  }
}
