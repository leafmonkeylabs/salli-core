# Releasing the CLI and SDK

The TypeScript packages are released from GitHub Actions
([`.github/workflows/release.yml`](.github/workflows/release.yml)). Each one has its own
version and its own tags:

| Package | npm | Tag |
|---|---|---|
| `packages/cli` | [`salli`](https://www.npmjs.com/package/salli) | `cli-v<version>` |
| `packages/sdk` | [`@leafmonkeylabs/salli-sdk`](https://www.npmjs.com/package/@leafmonkeylabs/salli-sdk) | `sdk-v<version>` |

Pushing a tag tests, builds and packs the package, then **stages** it on npm with
provenance. A staged version reaches no one until a maintainer approves it with 2FA, so
a compromised workflow or a leaked credential cannot publish by itself. A CLI release
also builds standalone binaries, each on its own platform. Each release gets a **draft**
GitHub release holding them and `SHA256SUMS`.

## A release

1. Bump the version in a pull request: `npm version 0.2.0 --workspace salli --no-git-tag-version`,
   or `--workspace @leafmonkeylabs/salli-sdk` for the SDK. Merge it.
2. Tag the merge commit on `main` and push the tag:

   ```bash
   git tag cli-v0.2.0 origin/main && git push origin cli-v0.2.0
   ```

   The tag has to match the version in `package.json`, or the workflow stops. A
   version with a pre-release part (`0.2.0-beta.1`) goes to the `next` dist-tag, not
   `latest`.
3. Wait for the **Release** workflow. Then approve the staged version on npmjs.com,
   or with `npm stage list salli` and `npm stage approve <id>`.
4. Publish the draft release on GitHub.

To rehearse, open **Actions → Release → Run workflow** and pick a package. A rehearsal
runs every check and builds every binary, and publishes nothing.

## Once: the first release

npm can only trust a workflow for a package that already exists. The first release of
each package therefore stages with a short-lived token:

1. **On npmjs.com:**
   - Have an account with 2FA.
   - Create the `leafmonkeylabs` organisation, which the SDK's scope needs.
2. **The token:** create a granular access token.
   - Permission: **stage only**, for all packages.
   - Expiry: a week.
3. **In the repository:** go to **Settings → Environments → `npm`** (the first workflow
   run creates it).
   - Add the token as the secret `NPM_BOOTSTRAP_TOKEN`.
   - Add yourself as a required reviewer.
4. **Release:** release both packages as above (`cli-v0.1.0` and `sdk-v0.1.0`), and
   approve both staged versions.
5. **Trusted publishing:** for each package, open **Settings → Trusted publishing** on
   npmjs.com and add GitHub Actions with:
   - repository `leafmonkeylabs/salli-core`;
   - workflow `release.yml`;
   - environment `npm`.

   Leave it stage-only.
6. **Clean up:**
   - Delete the `NPM_BOOTSTRAP_TOKEN` secret and revoke the token.
   - Under each package's publishing access on npmjs.com, disallow tokens.

From then on the workflow publishes through OIDC alone, and no npm credential is stored
anywhere.

## Not yet

- musl Linux binaries, a Homebrew tap, an install script, and Scoop or winget.
- macOS notarisation and Windows code signing, which are needed before 1.0 and need paid
  developer accounts.
