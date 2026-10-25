# Releasing

Salli has four things to release, each from GitHub Actions. Three have their
own version and tag; the console shares the server's:

| What | Where | Tag |
|---|---|---|
| `packages/cli` (the `salli` command) | [`@leafmonkeylabs/salli`](https://www.npmjs.com/package/@leafmonkeylabs/salli) on npm | `cli-v<version>` |
| `packages/sdk` | [`@leafmonkeylabs/salli-sdk`](https://www.npmjs.com/package/@leafmonkeylabs/salli-sdk) on npm | `sdk-v<version>` |
| The server's container image, with the console built into it | `ghcr.io/leafmonkeylabs/salli` | `server-v<version>` |
| `packages/console` | [`@leafmonkeylabs/salli-console`](https://www.npmjs.com/package/@leafmonkeylabs/salli-console) on npm, for editions that build on it | `server-v<version>` (the same tag) |

The CLI, the SDK and the console's npm package are released by
[`release.yml`](.github/workflows/release.yml), the image by
[`image.yml`](.github/workflows/image.yml) ([below](#the-server-image)).

## Breaking changes

A change is **breaking** when something written against the last release
stops working or quietly means something else:

- **REST API:** a route, method, field or enum value removed or renamed; a
  field whose meaning changes (the same name, a different figure); a request
  field newly required, or a value accepted before now refused; a status code
  or problem type changed for the same request. Adding a route, an optional
  request field or a response field is not breaking: clients ignore fields
  they don't know.
- **SDK:** an exported function, type or option removed or renamed, or a
  type narrowed so that code which compiled no longer does.
- **CLI:** a command, option or argument format removed or renamed, a
  default changed, an exit code changed, or `--json` output reshaped.
  Wording meant for people may change freely.
- **MCP:** a tool or prompt removed or renamed, or a tool's arguments or
  result reshaped. AI clients call tools by name, so a rename is breaking
  even when the tool does the same thing.

A breaking change:

1. is listed in `CHANGELOG.md` under **Breaking**, saying what to do
   instead;
2. ships with a minor version bump while the part is before 1.0 (0.4 to
   0.5), and a major one from 1.0 (1.x to 2.0), for each part it touches:
   the server, the SDK, the CLI;
3. keeps a removed REST route answering `410 Gone`, with a problem saying
   what replaced it, for one minor release where practical.

The API stays under `/v1` before 1.0; a breaking change there is announced
by the server's version and the changelog, not by a new path.

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
4. Say what changed in the GitHub release for the tag, including any setting a
   self-hoster has to change. The same tag releases the console's npm package
   ([below](#the-console)), and a tag holds one release, so the Release
   workflow puts the console's files on this one: usually it runs first and
   leaves a draft titled "Server <version>" with a "The console on npm"
   section. Write the server's notes above that section
   (`gh release edit server-v<version> --notes-file notes.md`), keep it, and
   publish the draft. If you made the release first, the workflow attaches the
   console's package and `SHA256SUMS-console` to it and adds the section.

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

## The console

The console ships at the server's version (docs/design/console.md, decision
24): the image built from `server-v<version>` carries it, and the same tag
stages `@leafmonkeylabs/salli-console` at that version on npm, so an edition
can build against exactly the open console its base image carries.

- Bump `packages/console/package.json`'s version with the server's
  (`npm version <version> --workspace @leafmonkeylabs/salli-console
  --no-git-tag-version`): a test fails while they differ, and so does the
  release.
- The npm package is the console's source (`src/`), which an edition's own
  Vite build compiles; it depends on `@leafmonkeylabs/salli-sdk` at an exact
  version. **Release that SDK version first** (`sdk-v<version>`): the release
  stops while it isn't on npm. The console in this tree needs SDK 0.5.0.
- The first release of the console is staged with the bootstrap token, like
  the others' first releases ([above](#once-the-first-release)). 0.4.0 was
  that release.
- Its GitHub release is the server's: the package and `SHA256SUMS-console`
  are attached to the `server-v<version>` release, with a "The console on
  npm" section, never a release of their own. A tag holds one release, so a
  separate draft could not be published.

## Not yet

- musl Linux binaries, a Homebrew tap, an install script, and Scoop or winget.
- macOS notarisation and Windows code signing, which are needed before 1.0 and need paid
  developer accounts.
