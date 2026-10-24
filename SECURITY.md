# Security

Salli holds people's financial records, so we take reports seriously.

**Please report vulnerabilities privately** through GitHub's
[private vulnerability reporting](https://github.com/leafmonkeylabs/salli-core/security/advisories/new)
rather than a public issue, or by email to
[security@salli.money](mailto:security@salli.money). Include what you found,
how to reproduce it, and the impact you expect.

## What happens next

| Step | Within |
|---|---|
| We acknowledge your report | 3 working days |
| We confirm it, or say why not, with a severity | 10 working days |
| A fix released for a critical or high severity issue | 30 days of confirming it |
| A fix released for anything else | the next minor release |

We keep you updated until it's fixed, credit you in the advisory unless you
would rather we didn't, and publish a GitHub security advisory when the fix
ships. Please give us 90 days, or until the fix is out if sooner, before you
disclose. We won't pursue anyone who reports in good faith, keeps to their
own account and data, and gives us that time.

## Supported versions

Salli is before 1.0: only the latest release of each part gets security
fixes.

| Part | Supported |
|---|---|
| The server image (`ghcr.io/leafmonkeylabs/salli`) and the console | the latest `server-v` release |
| The `salli` CLI (`@leafmonkeylabs/salli`) | the latest `cli-v` release |
| The SDK (`@leafmonkeylabs/salli-sdk`) | the latest `sdk-v` release |
| `main` | yes, as the next release |

The threat model and controls are in [docs/security.md](docs/security.md);
what personal data Salli keeps and who else sees it is in
[docs/privacy.md](docs/privacy.md).

## Running your own instance safely

- Keep `.env` out of version control and readable only by you (`salli-server
  setup` writes it with mode 600).
- There is no sign-up: only accounts the owner creates can sign in. Keep the
  `secrets` volume and your backups as private as the database.
- Never set `SALLI_INSECURE_DEV_AUTH` outside local development.
- If you expose the API beyond your machine, put it behind HTTPS (compose's
  `tls` profile) and set `SALLI_PUBLIC_URL` to its public URL.
  The console signs in only over HTTPS, or at localhost on the server's own
  machine.
- [docs/self-host.md](docs/self-host.md#security) says how passwords, sessions,
  refresh tokens (a reused one ends its sign-in), the console's headers and
  sign-in throttling work.
