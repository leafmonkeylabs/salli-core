# Security

Salli holds people's financial records, so we take reports seriously.

**Please report vulnerabilities privately** through GitHub's
[private vulnerability reporting](https://github.com/leafmonkeylabs/salli-core/security/advisories/new)
rather than a public issue. Include what you found, how to reproduce it, and
the impact you expect. We'll acknowledge within a few working days and keep
you updated until it's fixed.

## Running your own instance safely

- Keep `.env` out of version control and readable only by you (`salli setup`
  writes it with mode 600).
- Leave `SALLI_REGISTRATION=closed` unless you mean to let anyone who can
  sign in create an account.
- Never set `SALLI_INSECURE_DEV_AUTH` outside local development.
- If you expose the API beyond your machine, put it behind HTTPS and set
  `MCP_PUBLIC_BASE_URL` to its public URL.
