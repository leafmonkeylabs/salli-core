---
name: salli-monthly-review
description: Walk the user through a monthly money review in Salli — spending against budget, subscriptions, alerts, net worth and progress towards financial independence. Use when the user asks "how did I do this month", "review my finances" or "what should I look at".
---

# A monthly review

Read the `salli-cli` skill first. Every number below comes from a command; if
one fails, say what is missing rather than estimating.

1. **Alerts first.**

       salli reminders sync-alerts --json
       salli reminders list --alerts --status pending --json
       salli insights signals --json

2. **Spending vs. budget.**

       salli budgets list --json
       salli budgets summary <budget-id> --json
       salli insights spending --json

   Lead with categories over their limit.

3. **Subscriptions.**

       salli subscriptions report --json

   Flag missed charges and price changes.

4. **Position.**

       salli reports net-worth --json
       salli fi score --json
       salli insights forecast --json

5. **One next step.** Optionally run the advisor (an AI step) and present its
   top recommendation:

       salli advisor run --json

Keep it short: what changed, what needs attention, one suggestion.
