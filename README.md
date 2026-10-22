# ai-visibility-audit

[![CI](https://github.com/stefan-white/ai-visibility-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/stefan-white/ai-visibility-audit/actions/workflows/ci.yml)

An agent skill that checks **whether AI answer engines recommend your brand** —
ChatGPT, Gemini, Google AI Mode, Perplexity — and pairs it with classic Google
keyword rankings and competitor domains. The output is an evidence-based report
plus a fix list that a coding agent can act on.

> Status: v0.2.0, early. Feedback and PRs welcome.

## Why

Buyers increasingly ask AI assistants "who makes the best X?" instead of
searching. Traditional SEO tools don't tell you whether you appear in those
answers, which sources the engines trust, or which competitors they name. This
skill turns that into a repeatable, budget-capped measurement.

## Who it's for

- Small and mid-size companies (especially B2B / manufacturers) checking their
  "AI visibility".
- Marketers and SEO consultants who want a reproducible audit procedure.
- Developers who run coding agents and want them to perform the audit end-to-end.

## What it does

1. **Target definition** — brand names, aliases, domains; free checks for
   `robots.txt` AI-crawler rules, `llms.txt`, sitemap, JSON-LD.
2. **AI answer visibility** — 5–6 buying-intent questions + 1 brand question
   across 4 engines; records mention, rank, cited URLs, competitors, and third-party
   sources. Failed calls are tracked separately, never counted as "not mentioned".
3. **SEO visibility** — ranked keywords and competing domains per market.
4. **Report** — per-question table, hit rates, competitors, keyword findings,
   [Measured] vs [Inferred] labels, an executable improvement list, and a cost
   ledger. Optional comparison with a previous audit.

## Data providers (pluggable)

The skill is provider-agnostic. You need something that can:

| Capability | Examples | Manual fallback |
|---|---|---|
| Ask an AI engine and get answer + citations | an MCP connector such as Monid (wraps answer-engine scraping APIs like cloro), or any similar API | Private browser session per engine, copy answer and citations |
| Keyword rankings / competitor domains | DataForSEO (directly or via an MCP connector), other SEO APIs | Google Search Console export, manual SERP check |

To add another provider, map its output to the fields in
[`schema/results.schema.json`](schema/results.schema.json), illustrated by
`examples/acme-widgets.results.json`. Paid calls are always budget-capped (see SKILL.md §0).

## Install

Copy the folder (or just `SKILL.md`) to where your agent loads skills, for example:

- **Claude Code**: `~/.claude/skills/ai-visibility-audit/` (or `.claude/skills/` in a project)
- **Codex**: reference `SKILL.md` from your `AGENTS.md`, or paste it as instructions
- **Cursor**: add it as a project rule / agent skill, or `@`-mention `SKILL.md` in chat
- Any other agent: give it `SKILL.md` as the task procedure

## Usage

For a workflow without paid data sources, use the
[manual worksheet](templates/manual-worksheet.md). It covers evidence capture,
failed attempts, missing coverage, and mapping observations into results JSON.

Example prompt (see `examples/prompt.md`):

```text
Run the ai-visibility-audit skill for "Acme Widgets" (domain acme-widgets.example).
Market: US. Product scope: industrial widgets, custom sizes. Budget: USD 1.
Write the report in English to ./audit-2026-01/.
```

Render the scorecard from structured results:

```bash
python3 scripts/scorecard.py examples/acme-widgets.results.json > scorecard.md
# compare with a previous run
python3 scripts/scorecard.py results.json previous/results.json > scorecard.md
```

Inputs are validated before any report is printed, including the previous audit
when comparing. Missing fields and wrong types report a field path such as
`$.results[0].mentioned`; invalid input exits with code 2. Keep the bundled
`schema/` directory alongside `scripts/`. The standard-library checker supports
the keywords used by this schema, not arbitrary JSON Schema documents. It also
rejects duplicate question IDs, unknown question references, duplicate
engine/question pairs, invalid calendar dates, and non-finite JSON numbers.
Extensions are allowed; successful observations require a boolean `mentioned`,
and failed observations require an `error`. An empty results list means no
observations and produces an `n/a` hit rate.

Run tests (standard library only; CI verifies Python 3.10–3.12):

```bash
python3 -m unittest discover -s tests
```

## Example output

Start with the [industrial equipment and SaaS question sets](examples/question-sets/).
Each contains five intent prompts and one brand prompt, with no collected answers.

All examples use **Acme Widgets, a fictional brand. The numbers are FAKE** and
exist only to show the format:

- `examples/acme-widgets.results.json` — structured results
- `examples/acme-widgets.scorecard.md` — generated scorecard
- `examples/acme-widgets.report.md` — abbreviated full report

Excerpt:

| Question | chatgpt | perplexity |
|---|---|---|
| Q1 (intent): Best industrial widget manufacturers for small factories? | ❌ | ❌ |
| Q2 (intent): Which widget suppliers offer custom sizes with short lead times? | ✅ #3 | FAILED |
| Q3 (brand): Is Acme Widgets a reliable supplier? | ✅ #1 | ✅ #1 |

## Maintenance roadmap

Completed in v0.2.0: [results schema and validation](https://github.com/stefan-white/ai-visibility-audit/issues/1),
[manual worksheet](https://github.com/stefan-white/ai-visibility-audit/issues/2), and
[industry questions](https://github.com/stefan-white/ai-visibility-audit/issues/5).

Planned work remains open:

- [Direct DataForSEO and manual provider documentation](https://github.com/stefan-white/ai-visibility-audit/issues/3)
- [Synthetic Gemini and Google AI Mode examples](https://github.com/stefan-white/ai-visibility-audit/issues/4)
- [Comparison presentation and comparability](https://github.com/stefan-white/ai-visibility-audit/issues/6)
- [Week 3: optional OpenAI parsing](https://github.com/stefan-white/ai-visibility-audit/issues/7), subject to explicit budget approval; CI stays offline.

See [CHANGELOG.md](CHANGELOG.md) for release details and
[SECURITY.md](SECURITY.md) for reporting guidance.

## Limitations

- AI answers are non-deterministic and vary by locale, login state, and time;
  treat one run as a sample, not a ranking guarantee.
- Third-party scraping APIs change prices and coverage; always check prices first.
- The skill analyzes only. It does not modify the audited site.

## 中文简介

一个给 AI 编码代理用的技能：检查某个品牌在 ChatGPT、Gemini、Google AI Mode、
Perplexity 的回答里有没有被推荐、被引用，再结合 Google 关键词排名和竞品域名，
产出一份带证据的体检报告和可执行的改进清单。数据源可插拔（任意 MCP 连接器或 API，
也可手动检查），付费调用有预算上限。示例中的 "Acme Widgets" 为虚构品牌，数据均为假数据。

## License

MIT — see [LICENSE](LICENSE).
