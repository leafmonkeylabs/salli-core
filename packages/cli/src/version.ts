// Replaced at build time with the package version (tsdown `define`).
declare const __SALLI_CLI_VERSION__: string | undefined;

export const VERSION: string = typeof __SALLI_CLI_VERSION__ === 'string' ? __SALLI_CLI_VERSION__ : '0.0.0-dev';
