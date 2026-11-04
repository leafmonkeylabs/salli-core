# Putting the phone app in the App Store and Google Play

Bundle id and Android package: `money.salli.app`. Builds run on EAS
(`packages/mobile/eas.json`); nothing here needs a Mac except the first
iOS sign-in prompts, which EAS handles.

## Owner steps (accounts only the owner can open)

1. **Apple Developer Program** (USD 99 a year), enrolled as the company.
   Then in App Store Connect: New App, bundle id `money.salli.app`, and put
   its numeric Apple ID in `eas.json` (`submit.production.ios.ascAppId`).
   Register the app group `group.money.salli.app` (the widget and the
   Shortcuts action share it); EAS creates the three identifiers on the
   first build.
2. **Google Play Console** (USD 25 once), as an organisation. Create the app
   `money.salli.app`. A new personal account needs 12 testers for 14 days
   before production; an organisation account does not.
3. **Expo account**, `npm i -g eas-cli`, `eas login`, then in
   `packages/mobile`: `eas init` (writes `extra.eas.projectId`, which push
   needs).
4. **Play service account key**: Play Console, Setup, API access, create a
   service account with release rights, save its JSON as
   `packages/mobile/play-service-account.json` (git-ignored).
5. A public **privacy policy URL** and a **support URL** (the site's
   terms/privacy pages are still open).

## Build and send

```bash
cd packages/mobile
eas build --platform all --profile production
eas submit --platform ios --profile production
eas submit --platform android --profile production   # lands as an internal draft
```

Version numbers: `version` in `app.json` is the marketing version; EAS
raises the build number and version code (`appVersionSource: remote`).
Android's first upload must be done once by hand in the Play Console; the
API takes over after it.

## What review will ask, and the answers

- **Where is the server?** The app signs in to a Salli server the person
  chooses (their own, or Salli's hosted one). Give App Review a demo server
  address and a demo account (the seeded sample household:
  `packages/mobile/scripts/seed-sample-household.py`) in the review notes.
- **Account deletion** (Apple 5.1.1(v), Play's data-deletion form): the
  hosted sign-up lives on the web; the app has no Delete account yet. Add
  one under More, Servers and sign-ins before submitting, going to the
  server's erasure (`salli.erase_user`). Needs a canvas board first.
- **Encryption:** `usesNonExemptEncryption: false` (HTTPS and standard
  platform crypto only).
- **Privacy labels / Data safety:** data is the person's own financial
  entries, email and name, held on their server; no tracking, no ads, no
  third-party analytics, no data sold. Push goes through Salli's relay and
  carries no amounts or names. Face ID is local.
- **Category:** Finance. Age rating 4+ (no user-generated public content).
- **No financial advice:** the app compares and describes; say so in the
  description.
- **Screenshots:** iPhone 6.9" (1320 x 2868) and 6.5", Android phone and a
  7"/10" tablet set (Play asks even for phone-only apps to declare it).
- **Privacy manifest:** set in `app.json` (`privacyManifests`).

## Android gaps

The widget and the Shortcuts action are iOS only. Everything else is the
same code; run the whole tour on a Pixel emulator before the first upload
(`eas build --profile preview --platform android`).
