# Listing Salli in the AI connector directories

Anyone can connect their own Salli to an AI client by its URL
(`https://<your domain>/mcp`, [ai-clients.md](ai-clients.md)). A directory
listing is for a hosted Salli that people find by name in Claude's or
ChatGPT's directory. This is the kit for submitting one: what each directory
asks (as published in October 2026; check the pages below before
submitting, they change), what Salli already does about it, and what the
submitter supplies.

## What both directories check

| Requirement | Salli | Checked by |
|---|---|---|
| A remote MCP server over Streamable HTTP, on HTTPS | `/mcp` on the instance's `SALLI_PUBLIC_URL` ([hosting.md](hosting.md)) | |
| OAuth for an authenticated server: the authorization code grant with PKCE (S256), a public client | `/mcp/oauth/authorize`, `/mcp/oauth/token`; `code_challenge_methods_supported: ["S256"]`, `token_endpoint_auth_methods_supported: ["none"]` | `tests/unit/api/test_connector_directory.py` |
| Authorization server metadata (RFC 8414) at `/.well-known/oauth-authorization-server`, its `issuer` the instance's origin | yes, with `scopes_supported` | same |
| Protected resource metadata (RFC 9728) at `/.well-known/oauth-protected-resource` and at the path derived from the resource (`.../oauth-protected-resource/mcp`), naming the issuer | yes, with `scopes_supported` and `bearer_methods_supported` | same |
| A 401 from `/mcp` whose `WWW-Authenticate` names the resource metadata | `Bearer ... resource_metadata="<origin>/.well-known/oauth-protected-resource/mcp"` | same |
| Dynamic client registration (RFC 7591), or a client id metadata document | `/mcp/oauth/register`: any https redirect, so the directories' callbacks register (`https://claude.ai/api/mcp/auth_callback`, `https://claude.com/api/mcp/auth_callback`, `https://chatgpt.com/connector_platform_oauth_redirect`) | same |
| Every tool annotated: a title, and whether it only reads (`readOnlyHint`) or changes or removes something (`destructiveHint`) | every tool has both; writes are refused unless the person ticked "Allow changes" | same, and `tests/unit/api/test_mcp_scopes.py` |
| Tool descriptions that say what the tool does, without promotion | the descriptions are Salli's plain sentences | review |
| A privacy policy, terms and a support contact, on the service's own site | the hosted service's | submitter |
| A test account with sample data, usable without two-step sign-in or SMS codes, for the reviewers | an owner-made member on a demo instance (`salli-server members add`), with two-step sign-in off | submitter |
| Setup documentation for users | [ai-clients.md](ai-clients.md), adapted to the hosted URL | submitter |

## Claude (Anthropic's connector directory)

- Submission guide: <https://claude.com/docs/connectors/building/submission>,
  and for remote servers <https://support.claude.com/en/articles/12922490>.
- Asks for: a production remote server, OAuth 2.0 where authentication is
  needed, accurate tool annotations (a title, and `readOnlyHint` or
  `destructiveHint` on each tool), documentation, a support channel, a test
  account with sample data, and an allowlist of any external links the
  connector opens (Salli opens none).

## ChatGPT (OpenAI's app directory)

- Submission: <https://developers.openai.com/apps-sdk/deploy/submission>;
  authentication: <https://developers.openai.com/apps-sdk/build/auth>.
- Asks for: the MCP server's URL and its OAuth metadata, dynamic client
  registration or a client id metadata document, the authorization code
  grant with PKCE, a verified OpenAI organisation, a domain verification
  token served at `/.well-known/openai-apps-challenge`, privacy policy and
  terms, test prompts with expected results, and a reviewer account.
- Salli does not serve the domain verification token: the hosted service's
  reverse proxy answers that one path with the token OpenAI gives (a
  `respond` line in Caddy, beside `reverse-proxy`).

## Before submitting

1. Stand up the demo instance with [hosting.md](hosting.md), with sample
   books in the reviewer's account.
2. Check the metadata from outside:
   `curl https://<domain>/.well-known/oauth-authorization-server` and
   `curl -i -X POST https://<domain>/mcp` (a 401 naming the resource
   metadata).
3. Connect it once from each client by URL, approve on the consent page,
   and run a read and, with "Allow changes" ticked, a write.
4. Submit, with the test account and the documents above.
