# The Salli app

Salli for iPhone and Android: a client of your own Salli server. It signs in
on the server's own page, then shows where you stand from the server's
figures. The design, and every decision behind it, is
[docs/design/mobile.md](../../docs/design/mobile.md).

Like the CLI and the console, it is a client of the API:

- **It computes nothing.** Every figure is the server's, shown exactly
  through the SDK's `formatAmount`; amounts stay decimal strings from the
  response to the screen (`Money` in `src/kit.tsx`), and the lint refuses
  turning one into a number.
- **Data comes only through the SDK** (`@leafmonkeylabs/salli-sdk`), read with
  `useRead` (`src/api.tsx`) as the console reads it.
- **It adds no feature the CLI lacks**, and ranks nothing.

Licence: [AGPL-3.0-only](LICENSE), like the server and the console.

## Working on it

From the repository's root (one npm workspace), with Xcode for iOS or
Android Studio for Android:

```bash
npm ci
npm test --workspace @leafmonkeylabs/salli-mobile        # src/lib, without React Native
npm run typecheck --workspace @leafmonkeylabs/salli-mobile
cd packages/mobile && npx expo run:ios                   # builds, installs and opens it in a simulator
```

`npx expo start` runs Metro on its own once the app is installed. Metro
bundles the SDK from `packages/sdk/src` (`metro.config.js`), so no SDK build
has to run first.

A simulator reaches a server on this machine at localhost, the one place the
app signs in over plain HTTP: run one with
`SALLI_PUBLIC_URL=http://localhost:8000` and type `localhost:8000` in the
app. Anywhere else needs HTTPS, as the console does.

## How it signs in

As `salli-mobile`, Salli's own client (`core_0022`): the authorization code
with PKCE in the phone's secure browser sheet (`expo-web-browser`), back to
`money.salli.app:/oauth/callback`. PKCE is hashed with `expo-crypto`, since
React Native has no `crypto.subtle`; the code exchange and refreshes are the
SDK's. Tokens stay in the keychain or keystore (`expo-secure-store`), only on
this device. A refresh rotates the refresh token, and the new one is saved
before the old one could be used again.

## Rules

- **Every word in `src/strings.ts`,** in the brand's voice: British English,
  sentence case, no exclamation marks, nothing that ranks or urges.
- **Colours only from `src/theme.ts`,** the brand's tables with the console's
  light and night roles. Square corners; 48 px to touch.
- **The logo is the outlined file** (`src/brand/logo.ts`, from
  `docs/brand/assets`), never retyped.
- **Pinned dependencies,** exact versions, at the Expo SDK's own
  (`npx expo install`, then pin).
