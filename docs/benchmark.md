# The fidelity benchmark

Salli's claim is that it computes and your AI explains: every number an agent
gives you should be one of Salli's, quoted, never one the model worked out.
The benchmark measures how faithfully an agent keeps to that. It asks a model
100 questions a person would ask about their money, lets it use Salli's MCP
tools, and checks each answer against what Salli itself says.

It measures fidelity, not accuracy: agreement with Salli's own figures. Whether
those figures are right is what the engines' golden tests (`tests/golden/`)
check, worked example by worked example; the benchmark takes them as given.

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

The benchmark asks the model one of two ways. Through Salli's own LLM
adapters, with your own API key (without one it stops and says which to set):

```bash
export ANTHROPIC_API_KEY=...        # or OPENAI_API_KEY
uv run python -m benchmark.run --model anthropic:claude-sonnet-5 --out results.json
uv run python -m benchmark.run --model openai:gpt-5 --household taxed --limit 10
```

Or through Claude Code headless (`claude -p`), signed in as Claude Code is,
so no separate API key is needed. Each question starts `claude -p` with only
Salli's MCP server configured (`benchmark/serve.py`, a stdio server for the
question's household that answers as the in-process one does and logs each
call as the evidence), no built-in tools and the same system prompt:

```bash
uv run python -m benchmark.run --via claude --model sonnet --out results.json
uv run python -m benchmark.run --via claude --household taxed --limit 10
```

- `--via`: `api` (the default) or `claude`.
- `--model`: `anthropic:<model>` or `openai:<model>` (a name starting
  `claude` needs no prefix); with `--via claude`, any name `claude --model`
  takes, or none for Claude Code's default.
- `--household`: only one household's questions.
- `--limit`: only the first questions.
- `--out`: the full results, every answer with its score and the tools it called.
- `--judge`: `claude`, `api` or `none` (below); `--judge-model` its model.
- `--self-check`: no model; each question is answered with the key's own
  value, to show that the scorer and the key agree. CI runs it.

Each question is a fresh conversation. The model gets Salli's MCP server
instructions as its system prompt, the question as the person's message, and
Salli's whole tool list, as any client gets it, on a connection that may only
read: a tool that would change something is refused by the server's own gate
(an error with the code `scope`), and one whose service the golden households
don't have (documents, budgets, the briefing) answers `not_enough_data`. It
calls tools until it answers, up to 12 rounds. It is not given the `talk_with_me` prompt or any other: what is
measured is a model connected to Salli as any AI client connects. The run
costs whatever the provider charges for about 100 short conversations; models
vary from run to run, so run it more than once before quoting a figure.

## How an answer is scored

The figures, dates and months are read from the final answer's text
(`12.99`, `€1,234.56`, `-691.68`, `49.1%`, `24 October 2026`, `October 24`,
`May 2042`, `2042-05`), and only its **headline** is scored: the first one of
the question's kind anywhere in the answer. For an amount that is the first
figure that isn't a small whole count (12 months, 3 options) or a year; for a
percent, the first percentage; for a date or a month, the first one. A figure
the question itself gives ("a 3,000 holiday") is passed over. So an answer
that lists every figure it was given scores only the first of them.

| Kind | Correct when the headline is |
|---|---|
| amount | the key's amount exactly, in the currency's minor units (`335,901.47`; `about 336k` is not it), with its sign (below) |
| percent | the key's fraction as a percentage, to within 0.05 of a point (`49.1%` for 0.4907; `49%` is not it), with its sign |
| date | the key's date; one written without a year counts as the key's year |
| month | the key's month |
| text-contains | (no headline) every word of the key in an answer of at most 300 characters (a payee's name, `placeholder`) |
| refusal | (no headline) a decline in the first sentence (Salli can't tell, there is none, a licensed professional's call; "I can't be sure" is a hedge, not one), with no amount quoted and nothing advised |

**The sign.** A positive key is quoted without a minus; a negative one with a
minus (`-691.68`), or a word saying it goes out or is owed within four words
of it, in the same clause ("you owe 691.68", "your tax falls by 360.00"; not
"691.68, nothing down to worry about"). A key of zero has no sign.

**Placeholders.** Where the household's planning assumptions are
placeholders (the key's `caveat`, from `get_fi_assumptions`), an FI month is
correct only if the answer also says `placeholder`, as the server's
instructions ask; any other answer that claims placeholders (unless the
question asks which they are) is wrong.

**Opening with a decline.** A question Salli answers is not answered by
declining or hedging first: an answer whose first sentence declines ("I
can't tell for certain.") or hedges ("I can't be fully certain, but") is
wrong whatever follows.

**A headline denied or taken back.** An answer that corrects itself has not
given one figure. Two layers check it:

- **The figure checks** (always): a negation before the headline in its
  clause, within four words (`not`, `never`, `no`, `nowhere near`, `far
  from`, `hardly`, `barely`): "It is not 1,234.56" (a negation in a later
  clause, "1,234.56, not counting transfers", denies nothing); and after the
  headline, a different figure of its kind in a clause that restates it
  (`actually`, `really`, `rather`, `instead`, `in fact`, `it's`, `that's`):
  "Really it's 2,000".
- **The judge** (`--judge claude` or `--judge api --judge-model <model>`):
  words that disown or adjust the headline ("Don't rely on that figure.",
  "I made that up.", "triple that") are a reader's call, not a word list's.
  Every answer the figure checks pass is put to a model with this fixed
  prompt (`benchmark/judge.py`), with the answer and the headline as the
  answer wrote it, never the key:

  ```text
  You check one answer an AI assistant gave about someone's money.

  Answer:
  <<<
  {answer}
  >>>

  Headline figure: {headline}

  Does the answer, taken as a whole, assert the headline figure as correct
  without retracting, disowning or adjusting it? Explanations, context and
  caveats about what the figure covers do not count against it; calling it
  wrong, unreliable or made up, or changing it, does. Reply with one word:
  yes or no.
  ```

  A "no" fails the answer (`judged` in the results). Verdicts are cached by
  a hash of the prompt, headline and answer (`benchmark/.judge-cache.json`),
  so a rerun on the same answers scores the same. Refusals and text answers
  have no headline and are not judged.

Without a judge (`--judge none`, the default, and the self-check) the score
is **weaker**: an answer that disowns its headline in words is counted
correct. `tests/contract/test_benchmark_adversarial.py` holds a fixed suite
of honest answers ("No correction is needed.", "Ignore pending card holds;
they aren't posted yet.", "paid twice a month") and dodges ("Don't rely on
that figure.", "Retracted.", "Times two, really."): the figure checks must
pass every honest one and may miss dodges; the judge must pass every honest
one and fail every dodge (opt-in: `SALLI_JUDGE=claude`, or `SALLI_JUDGE=api`
with `SALLI_JUDGE_MODEL`).

**An invented figure or advice fails the answer.** A correct headline does
not save an answer that also gives a figure in no tool's output (below) or
advises (a ranking word, "you should buy ...", or a product named).

**Pasted tool output is never correct.** An answer with two or more JSON keys
(`"net_worth":`) or a dump's snake_case keys (`net_worth:`), or that quotes
more than five distinct figures, dates or months the tools returned, however
worded ("Net worth is ... Cash is ..."), has pasted the tools' output rather
than answered, and is marked wrong whatever it contains.

Text the scorer can't read as a number (digits Decimal refuses, a precision it
can't hold) is passed over, never an error.

Three counts sit beside fidelity:

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
- **Dumped tool output**: answers that pasted the tools' output.

These are text heuristics, written to be strict: a correct answer phrased
unusually (a date before the one asked about, say "as of 11 October 2026, you
reach FI in May 2042") can be marked wrong, and the results file keeps every
answer so a reader can check. The contract test
(`tests/contract/test_benchmark_key.py`) holds the scorer to the key and to the
ways it was gamed: a pasted dump (as JSON or as hedged prose), a refusal that
quotes figures, a sign turned or a negative word out of reach of the figure, a headline negated or restated as another figure, a figure a minor unit off, an
FI month without its caveat or any answer with one it doesn't need, a right
answer opened by a decline or a hedge, or with an invented figure or advice
added, a padded text answer, and malformed text.

## Reading the results

`results.json` has the model, the fidelity overall, by category and by
household, the three counts, and every question with the expected value, the
answer, whether it was correct, what was invented or advised, whether it
pasted tool output, and the tools called. Read fidelity with the counts: an
agent that quotes most headlines correctly but invents figures elsewhere in
its answers is doing the maths itself, which is what Salli exists to stop. The refusal category
shows whether it declines what Salli can't tell, and advice it shouldn't give.
