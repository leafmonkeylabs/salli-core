---
name: salli-monthly-review
description: Walk the user through a monthly money review in Salli — spending against budget, subscriptions, alerts, net worth and progress towards financial independence. Use when the user asks "how did I do this month", "review my finances" or "what should I look at".
---

# A monthly review

Read the `salli-cli` skill first. Every number below comes from a command; if
one fails, say what is missing rather than estimating.

1. **Alerts first.**

       salli reminders sync-alerts --json
       salli reminders list --alerts-only --json

2. **Spending vs. budget.**

       salli budget list --json
       salli budget summary <budget-id> --json

   Lead with categories over their limit.

3. **Subscriptions.**

       salli subscription report --json

   Flag missed charges and price changes.

4. **Position.**

       salli reports net-worth --json
       salli fi score --json

5. **One next step.** Optionally run the advisor (an AI step, needs an API key)
   and present its top recommendation:

       salli advisor run --json

Keep it short: what changed, what needs attention, one suggestion.
