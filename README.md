# Salli CLA signatures

This branch is the public record of who has accepted the
[Salli Contributor License Agreement](https://github.com/leafmonkeylabs/salli-core/blob/main/CLA.md).

The CLA bot (`.github/cla/check.js` on the default branch) adds an entry to
`signatures.json` when someone a pull request needs posts the sign phrase on
it. Each entry records:

- `id`, `login`: the GitHub account that accepted the agreement
- `version`: the version of the agreement accepted
- `document_sha256`: the SHA-256 of `CLA.md` as it read at the time, so the
  exact text can be found in the repository's history
- `signed_at`, `pull_request`, `comment_url`: when and where

Please don't edit this branch by hand. For a correction, open an issue.
