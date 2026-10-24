# Privacy: what Salli keeps and who else sees it

Salli runs on a server someone operates: you, for yourself and your
household, or a provider for its customers. Whoever runs it decides what it is
used for and answers for it under the law that applies to them. This page
says what the code does with personal data, so an operator can describe it
truthfully and assess it ([the template below](#impact-assessment-template)).
How it is protected is in [security.md](security.md).

## What Salli stores

All of it is in the instance's Postgres database, except uploaded files,
which are in `SALLI_STORAGE_DIR`. Tables are in
`src/salli/adapters/db/models.py`.

| Area | Tables | What it holds |
|---|---|---|
| Signing in | `logins`, `login_sessions`, `login_failures`, `personal_access_tokens`, `oauth_*` | Email, an argon2id password hash; for each sign-in a token hash, the user agent and times; failed sign-ins as a hash of the email or address tried; tokens' names, hashes, permissions and scopes |
| Profile | `user_profiles` | Email, display name, base currency, date of birth, dependants, employment status, employer and type, residency status, risk score and category, life stage, tax residency, tax ids, planning assumptions, time zone, AI preferences |
| Books | `accounts`, `journal_entries`, `postings`, `tags`, `posting_tags`, `categorization_rules`, `statements`, `parsed_transactions`, `documents` | The ledger, imported statements and their transactions, the person's sorting rules, and the uploaded files' records (the files in `SALLI_STORAGE_DIR`) |
| Bank feed | `bank_connections`, `bank_connection_accounts` | The sealed access URL, the bank's account names, institutions and last balances, sync status |
| Planning | `budgets`, `debts`, `holdings`, `holding_transactions`, `holding_prices`, `fi_goals`, `goal_allocations`, `fi_scores`, `fire_strategies`, `policies`, `insurance_targets`, `recurring_subscriptions`, `reminders` | What the person enters about their money and plans |
| Decisions | `principles`, `decisions`, `decision_notes`, `decision_reviews` | The decision journal, append-only |
| Tax | `tax_rule_sets`, `tax_rule_set_versions`, `tax_computations` | The person's rule sets and every computation with its inputs |
| AI | `user_llm_credentials`, `ai_connections`, `agent_sessions`, `agent_documents`, `advisory_reports`, `audit_logs`, LangGraph's `checkpoint*` tables | Sealed AI keys and ChatGPT sign-ins, conversation titles, what the agent saved, briefings, the AI's writes and the person's decisions on them; conversation messages and review workflows' state are in the checkpoint tables |
| Digests | `notification_preferences`, `notification_deliveries` | Choices and a log of what was sent: kinds, counts, dates and a hash, never the message |

## Who else sees it

Nothing leaves the server unless a feature below is used. Salli itself sends
no telemetry.

| Recipient | When | What is sent | Turned on by |
|---|---|---|---|
| **AI model provider**: Anthropic, OpenAI, or OpenAI through the person's ChatGPT plan | A conversation with Salli's agent (`/v1/agent/chat`) | The messages, files attached to them, the results of the tools the model calls (accounts, balances, entries, tax computations and so on) and a note on the person: today's date, base currency, tax residency and active rules (`domain/agents/jurisdiction.py`) | The person's own key or plan, or the operator's `ANTHROPIC_API_KEY` when they have neither (`llm_credential_service.py`) |
| | Importing a statement, or a bank feed's sync | The transactions the person's rules didn't sort (date, description, amount, direction, currency, reference) and the chart of accounts (`adapters/parsing/llm_classifier.py`) | The same |
| | Typing an entry in words (`/v1/entries/parse`) | The text and the chart of accounts | The same |
| | The monthly briefing (`/v1/advisor/run`, or daily when the person opts in) | Salli's figures as they would be shown, its signals (which may name a payee and an amount: "a charge went up") and whether the planning assumptions are placeholders; not the transactions (`domain/agents/briefing.py`) | The same |
| | Adding a key | The key alone, to the provider's models list, to check it (`adapters/llm/key_check.py`) | The person |
| **Tavily** (web search) | When Salli's agent searches during a conversation | The search query the model writes | The operator's `TAVILY_API_KEY` |
| **The person's AI connector** (an MCP client such as Claude or ChatGPT) | Whenever it calls Salli's tools | Whatever those tools return; it then goes to that client's provider | The person, who can switch MCP off (`/v1/mcp/connections/enabled`) |
| **The phone app's AI provider** (Anthropic, OpenAI, xAI, Meta or OpenRouter) | A conversation in the app | The conversation and Salli's tool results, from the phone straight to the provider, with the key kept on the phone (`packages/mobile/src/ai/`) | The person, in the app |
| **Exchange rates**: Frankfurter, then ExchangeRate-API | When a posting or a valuation needs a rate Salli hasn't cached | Two currency codes and a date (`adapters/fx/`) | Always |
| **SimpleFIN bridge** (bank feed) | Connecting, and each sync (asked for, or the scheduled job) | The access credential; the bridge answers with accounts and transactions (`adapters/banks/simplefin.py`) | The person |
| **A URL the person gives** | Importing a tax rule set from it | A request for that URL (`adapters/net/fetch.py`) | The person |
| **The deployment's notifier** | A digest is due | A message with no amount, name or ledger text in it (`domain/notifications/digest.py`) | An extension; Salli as shipped sends none |
| **LangSmith** | Each model call, if tracing is on | Model inputs and outputs (LangChain's tracing) | The operator, by setting `LANGSMITH_TRACING` and `LANGSMITH_API_KEY` in the server's environment |

Each provider keeps what it is sent under its own terms. An operator should
list the ones their instance uses, with links to those terms, in their own
privacy notice.

## Retention

Salli keeps everything until the person deletes their account or the
operator deletes it. The one automatic deletion: failed sign-ins older than
the 15-minute throttle window are pruned at the next sign-in
(`login_service.py`). Expired sessions and tokens stop working, but their
rows (hashes and times) stay. Backups keep what they hold until the operator
rotates them.

## Export and erasure

- **Export:** `GET /v1/onboarding/export` (`salli profile export`) is one
  JSON document of what Salli stores about the person, an extension's data
  included; `GET /v1/export/beancount` and `/v1/export/hledger` give the books
  as plain text. No credential is ever in it. It leaves out conversation
  messages, the uploaded files themselves, the sorting rules, the audit log
  and sign-in records.
- **Erasure:** `DELETE /v1/onboarding/account` (`salli profile
  delete-account`), with the person's email typed again, deletes their rows in
  every table above, the decision journal and an extension's tables included,
  after ending a connected ChatGPT plan's sign-in with OpenAI
  (`data_portability_service.py`, `repositories.py`
  `SQLDataPortabilityRepository.delete_all`). **Not yet:** it leaves the
  conversation messages in the checkpoint tables and the uploaded files in
  `SALLI_STORAGE_DIR`, which the operator has to remove, and data already
  sent to the recipients above.

## Impact assessment template

A short data protection impact assessment for an instance. Copy it, fill in
what is yours, and keep it with the instance's records. Review it when you
turn on a feature that sends data somewhere new.

**1. The processing.** Who runs the instance and for whom; how many people;
which features are on (the agent, statement import, the bank feed, web
search, digests, AI connectors); which recipients above that brings in, and
where they are.

**2. Necessity.** The basis you rely on under the law that applies to you;
why each recipient is needed; what you turned off to send less (no
`ANTHROPIC_API_KEY`, so only people who bring a key use AI; no
`TAVILY_API_KEY`; no tracing).

**3. Risks to people.**

| Risk | Likelihood | Severity | Measures | Left over |
|---|---|---|---|---|
| Someone else reads a person's books | | | Passwords, throttling, hashed tokens, HTTPS, sign-in review ([security.md](security.md#controls)) | |
| A provider keeps or misuses what it is sent | | | Only the features above send; the briefing sends figures and signals, not transactions; people choose their own provider | |
| A person acts on a wrong figure or on AI wording | | | The AI never computes money; briefings are labelled as the AI's and as not financial advice | |
| Data outlives an erasure | | | The erasure route; the known gaps above, handled by hand | |
| Data is lost | | | Backups as [self-host.md](self-host.md#backup-and-restore) says | |

**4. Sign-off.** Who assessed it, who approved it, the date, and when it is
next reviewed.
