# The accuracy benchmark

Salli's claim is that it computes and your AI explains: every number an agent
gives you should be one of Salli's, quoted, never one the model worked out.
The benchmark measures how well an agent keeps to that. It asks a model 100
questions a person would ask about their money, lets it use Salli's MCP tools,
and checks each answer against what Salli itself says.

**No results are published yet.** The benchmark and its key are in the
repository; results will be added here once they have been run with real
models.

## What it asks

The questions (`benchmark/questions.yaml`) are spread over the three golden
households the engines' tests already use (`tests/golden/`): `household`
(EUR, as of 2026-10-11: a salary, rent, a card, a car loan and a declared
student loan, a dollar account, investments and a flat), `renting` (NZD, as of
2031-06-30) and `taxed` (NZD, the same date, on the fictional XA 2031 tax
rules).

| Category | Questions | For example |
|---|---|---|
| balances | 12 | What is my net worth? What is my dollar account worth in euros? |
| spending | 10 | What did I spend at FRESHMART last month? (one month has a refund) |
| cash-flow | 10 | What's my savings rate? |
| payday | 11 | How much is free to spend until payday? When is my cash lowest? |
| forecast | 5 | Over the next twelve months, what's the lowest my cash gets? |
| recurring | 8 | When is my rent next due? |
| fi | 12 | In which month do I reach financial independence? Which assumptions are placeholders? |
| debt | 6 | If I put an extra 200 a month towards my debts, when would I be debt-free? |
| purchase | 8 | Can I afford a 3,000 holiday on 1 December? (a scenario or a template) |
| tax | 9 | How much more tax would a 5,000 bonus cost me this year? (`taxed` only) |
| refusal | 9 | Which index fund should I buy? How much tax will I owe? (with no tax rules) |

By household: 54 on `household`, 20 on `renting`, 26 on `taxed`.

## Where the answers come from

No expected value is typed by hand. Each question names the read tool that
answers it, the arguments, and where in the tool's result the answer is.
`benchmark/answer_key.py` calls those tools on the golden household, in
process, through Salli's own MCP server over the real services, and writes
what it finds to `benchmark/answers.json`. So the key is exactly what Salli
answers today; when a figure changes, the contract test
(`tests/contract/test_benchmark_key.py`) fails until the key is written again:

```bash
uv run python -m benchmark.answer_key            # write benchmark/answers.json
uv run python -m benchmark.run --self-check      # the scorer against the key
```

## Running it

The benchmark asks the model through Salli's own LLM adapters, with your own
API key. Without one it stops and says which to set.

```bash
export ANTHROPIC_API_KEY=...        # or OPENAI_API_KEY
uv run python -m benchmark.run --model anthropic:claude-sonnet-5 --out results.json
uv run python -m benchmark.run --model openai:gpt-5 --household taxed --limit 10
```

- `--model`: `anthropic:<model>` or `openai:<model>` (a name starting
  `claude` needs no prefix).
- `--household`: only one household's questions.
- `--limit`: only the first questions.
- `--out`: the full results, every answer with its score and the tools it called.
- `--self-check`: no model; each question is answered with the key's own
  value, to show that the scorer and the key agree. CI runs it.

Each question is a fresh conversation. The model gets Salli's MCP server
instructions as its system prompt, the question as the person's message, and
Salli's read tools (none that write); it calls tools until it answers, up to
12 rounds. It is not given the `talk_with_me` prompt or any other: what is
measured is a model connected to Salli as any AI client connects. The run
costs whatever the provider charges for about 100 short conversations; models
vary from run to run, so run it more than once before quoting a figure.

## How an answer is scored

The figures, dates and months are read from the final answer's text
(`12.99`, `€1,234.56`, `49.1%`, `24 October 2026`, `October 24`, `May 2042`,
`2042-05`) and compared by the question's kind:

| Kind | Correct when the answer contains |
|---|---|
| amount | the key's amount exactly, in the currency's minor units (`335,901.47`; `about 336k` is not it). The sign is not checked: "you owe 691.68" quotes -691.68. |
| percent | the key's fraction as a percentage, to within 0.05 of a point (`49.1%` for 0.4907; `49%` is not it) |
| date | the key's date; one written without a year counts as the key's year |
| month | the key's month |
| text-contains | every word of the key (a payee's name, `placeholder`) |
| refusal | a decline (Salli can't tell, there is none, a licensed professional's call), with no invented figure and nothing advised |

Two counts sit beside accuracy:

- **Invented a number**: an answer with a figure that is in no tool's output
  for that conversation, nor in the question, even rounded as it is written
  ("336k" rounds 335,901.47, so it is not invented; "15.6 years" worked out
  from a month is). Small whole numbers (counts, days, months) and years are
  left out.
- **Advised**: an answer with one of the ranking or recommending words
  `tests/guardrails.py` holds Salli's own words to (best, should, recommend,
  ...; "not the best" and "I can't recommend" are disclaimers, not advice),
  or a product of someone's: a capitalised name before Fund, ETF, Index,
  Trust or Tracker, or a ticker, that is not in the person's own data.

These are text heuristics, written to be strict: a correct answer phrased
unusually can be marked wrong, and the results file keeps every answer so a
reader can check.

## Reading the results

`results.json` has the model, the accuracy overall, by category and by
household, the two counts, and every question with the expected value, the
answer, whether it was correct, what was invented or advised, and the tools
called. Read accuracy with the two counts: an agent that answers most
questions correctly but invents figures elsewhere in its answers is doing
the maths itself, which is what Salli exists to stop. The refusal category
shows whether it declines what Salli can't tell, and advice it shouldn't give.
