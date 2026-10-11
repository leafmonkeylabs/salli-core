# Releasing

Salli has three things to release, each from GitHub Actions, each with its own
version and its own tags:

| What | Where | Tag |
|---|---|---|
| `packages/cli` (the `salli` command) | [`@leafmonkeylabs/salli`](https://www.npmjs.com/package/@leafmonkeylabs/salli) on npm | `cli-v<version>` |
| `packages/sdk` | [`@leafmonkeylabs/salli-sdk`](https://www.npmjs.com/package/@leafmonkeylabs/salli-sdk) on npm | `sdk-v<version>` |
| The server's container image | `ghcr.io/leafmonkeylabs/salli` | `server-v<version>` |

The CLI and SDK are released by [`release.yml`](.github/workflows/release.yml), the
image by [`image.yml`](.github/workflows/image.yml) ([below](#the-server-image)).

## The CLI and SDK

Pushing a tag tests, builds and packs the package, then **stages** it on npm with
provenance. A staged version reaches no one until a maintainer approves it with 2FA, so
a compromised workflow or a leaked credential cannot publish by itself. A CLI release
also builds standalone binaries, each on its own platform. Each release gets a **draft**
GitHub release holding them and `SHA256SUMS`.

### A release

1. Bump the version in a pull request: `npm version 0.2.0 --workspace @leafmonkeylabs/salli --no-git-tag-version`,
   or `--workspace @leafmonkeylabs/salli-sdk` for the SDK. Merge it.
2. Tag the merge commit on `main` and push the tag:

   ```bash
   git tag cli-v0.2.0 origin/main && git push origin cli-v0.2.0
   ```

   The tag has to match the version in `package.json`, or the workflow stops. A
   version with a pre-release part (`0.2.0-beta.1`) goes to the `next` dist-tag, not
   `latest`.
3. Wait for the **Release** workflow. Then approve the staged version on npmjs.com,
   or with `npm stage list @leafmonkeylabs/salli` and `npm stage approve <id>`.
4. Publish the draft release on GitHub.

To rehearse, open **Actions → Release → Run workflow** and pick a package. A rehearsal
runs every check and builds every binary, and publishes nothing.

### Once: the first release

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
4. **Release:** release both packages as above (`cli-v0.1.1` and `sdk-v0.1.0`), and
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

npm refuses the unscoped name `salli` as too similar to existing packages (`sails`,
`vanli`), so the CLI is published under the organisation's scope. The command is still
`salli`. Its first release is 0.1.1: the `cli-v0.1.0` tag was cut under the refused name,
and nothing was published from it.

## The server image

The version is `project.version` in `pyproject.toml`. Pushing `server-v<version>`
builds the image for amd64 and arm64 and, once a maintainer approves the job in the
`ghcr` environment, pushes it to `ghcr.io/leafmonkeylabs/salli` as:

- `<version>` (`0.2.0`);
- `<major>.<minor>` (`0.2`);
- `latest`, unless the version is a pre-release (`0.2.0rc1`, `0.2.0-beta.1`).

Each push carries an SBOM and a provenance attestation (`provenance: mode=max`),
which `docker buildx imagetools inspect ghcr.io/leafmonkeylabs/salli:<version>
--format '{{ json .Provenance }}'` shows.

1. Bump `version` in `pyproject.toml` in a pull request (`uv lock` updates the lock
   file's entry for Salli). The OpenAPI document carries the version, so
   regenerate it too: `uv run python -m salli.interfaces.api.spec >
   openapi/openapi.json`. The pull request builds the image and runs
   `compose.yaml` end to end. Merge it.
2. Tag the merge commit and push the tag:

   ```bash
   git tag server-v0.2.0 origin/main && git push origin server-v0.2.0
   ```

   A tag that doesn't match `pyproject.toml` stops the workflow.
3. Approve the **publish** job when it waits for the `ghcr` environment.
4. Say what changed in a GitHub release for the tag, including any setting a
   self-hoster has to change.

To rehearse, run **Actions → Image → Run workflow**: it builds both platforms and
pushes nothing.

### Once: before the first image

1. In **Settings → Environments**, create `ghcr` and add yourself as a required
   reviewer. Restrict it to tags matching `server-v*`.
2. After the first push, open the package on GitHub (**Packages → salli**):
   - make it public, so `docker compose pull` needs no login;
   - connect it to the `salli-core` repository, so the workflow's token can push
     later versions.

Until the first image is published, `compose.yaml` works only from a checkout:
`docker compose up -d --build`.

## Not yet

- musl Linux binaries, a Homebrew tap, an install script, and Scoop or winget.
- macOS notarisation and Windows code signing, which are needed before 1.0 and need paid
  developer accounts.
