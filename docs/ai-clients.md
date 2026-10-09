# Use Salli from Claude or ChatGPT

Salli runs an MCP server at `https://<your-salli>/mcp`. Connect it to the AI app you
already pay for, and that subscription does the thinking while Salli supplies the
numbers. Salli computes every amount; the model reads and explains them. It never
does the arithmetic itself.

Once connected, your AI can:
- read your cash flow, spending, net worth over time, recurring payments and your
  cash forecast;
- answer "can I afford…?" from your forecast and your FI plan;
- sort imported transactions, then book what you approve;
- create rules, so the next statement sorts itself;
- run the Wealth Advisor and read budgets, debts, portfolio, insurance and tax.

Three ready-made prompts come with the server: **review my month**, **sort my pending
transactions** and **can I afford**.

Before connecting anything:
- **The switch:** MCP must be on for your account (`salli mcp enable`), and you approve
  each client on Salli's consent page.
- **Writes:** these take effect when the AI calls them. The tools tell it to show you
  what it will do first.
- **Disconnecting:** `salli mcp connections` lists connected clients, and
  `salli mcp revoke` disconnects one.

## Claude (web, desktop, mobile)

Claude connects from Anthropic's cloud, not from your device, so your Salli has to be
reachable over the public internet over HTTPS. A Salli on your laptop or home network
needs a public address first, for example behind a reverse proxy with TLS.

1. In Claude, open **Customize → Connectors**, choose **+ Add**, then **Add custom
   connector**.
2. Name it `Salli` and enter `https://<your-salli>/mcp`.
3. Leave authentication on OAuth with automatic registration, and sign in to Salli when
   asked. You are approving Claude on Salli's consent page.
4. In a chat, open **+ → Connectors** and switch Salli on.

Free plans allow one custom connector; Pro and Max allow more. See Anthropic's guide,
[Get started with custom connectors using remote MCP](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

## Claude Code

```bash
claude mcp add --transport http salli https://<your-salli>/mcp
```

Run `/mcp` inside Claude Code to sign in. Claude Code runs on your machine, so a Salli on
`localhost` works here too.

## ChatGPT

ChatGPT adds custom MCP servers as apps. Where the option lives has changed several
times; recently it has been under **Settings → Apps** (or chatgpt.com/plugins), and on
some plans behind **Developer mode**. Add a new MCP app with the URL
`https://<your-salli>/mcp` and sign in to Salli when asked. On some plans, custom apps
may only read; sorting and booking then stay in Salli itself. See OpenAI's
[Developer mode and MCP apps in ChatGPT](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt).

## The other direction: your ChatGPT plan inside Salli

Salli's own AI features (statement sorting, quick add, the chat agent, the strategy and
briefings) can run on a ChatGPT Plus or Pro plan through OpenAI's
[Sign in with ChatGPT](https://developers.openai.com/siwc/token-sharing-open-source),
which OpenAI offers to open-source and self-hosted apps.

Anthropic does not allow Claude plans to be used this way
([Claude Code legal and compliance](https://code.claude.com/docs/en/legal-and-compliance)).
For Claude, connect Salli to Claude as above, or give Salli an Anthropic API key.
