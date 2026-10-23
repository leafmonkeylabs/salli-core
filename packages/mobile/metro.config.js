/* eslint-disable @typescript-eslint/no-require-imports -- Metro reads its config as CommonJS */
// Metro for the app inside the npm workspace. Expo finds the workspace's
// node_modules itself; the SDK is bundled from its TypeScript source, as the
// console's Vite build does, so no SDK build has to run first.
const path = require('node:path');
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);
const sdk = path.resolve(__dirname, '../sdk/src/index.ts');

const resolve = config.resolver.resolveRequest;
config.resolver.resolveRequest = (context, moduleName, platform) => {
  if (moduleName === '@leafmonkeylabs/salli-sdk') return { type: 'sourceFile', filePath: sdk };
  return (resolve ?? context.resolveRequest)(context, moduleName, platform);
};

module.exports = config;
