# Security

Salli holds people's financial records, so we take reports seriously.

**Please report vulnerabilities privately** through GitHub's
[private vulnerability reporting](https://github.com/leafmonkeylabs/salli-core/security/advisories/new)
rather than a public issue, or by email to
[security@salli.money](mailto:security@salli.money). Include what you found,
how to reproduce it, and the impact you expect. We'll acknowledge within a few working days and keep
you updated until it's fixed.

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
