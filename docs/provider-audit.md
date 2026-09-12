# Provider and spending audit — 2026-09-11

Audited main commit: `c77382173a06f29e8de10b160fea11960b7fa542`.
The baseline suite passed all 123 tests and its deterministic report verifier.
Only offline and explicitly injected fake transports were used. No model API
request was made, and no account access or secret value was inspected.

## Follow-up status

The follow-up driver now (1) validates finite non-negative caps and exits before
the first request when the cap is zero, (2) separates provider usage from local
rule-monitor usage so only billable tokens determine cost, (3) defaults
paid reports to `reports/live-run-paid.json`, while retaining the ignored
`*-local.json` convention for dry-run diagnostics, and (4) issues a serial
pre-request spend permit before each `transport.post`, retaining the
reservation when usage is missing or the call fails. The historical
reproductions below remain as evidence of the pre-fix behavior.

## Findings

| Area | Finding |
| --- | --- |
| Models | The live CLI selects Luna or Haiku. Luna uses `max_completion_tokens=256` and reasoning `none`; Haiku uses `max_tokens=256` without extended thinking. |
| Configuration | CLI provider diagnostics and real live startup load literal `.env` values; existing environment values win. |
| Automatic workflow | The sole workflow runs offline unit tests and finite reports. It does not inject API secrets or start a paid experiment. |
| Dollar cap | Checked after a full cell, without a pre-request reservation. A cell can overshoot it. A zero-dollar cap still permits the first cell. |
| Input/request limits | No provider-level input size limit or shared maximum HTTP-request count. The episode horizon bounds calls within a cell, but does not reserve their cost. |
| Failed output | Token usage is attached only after action parsing succeeds. A malformed paid response can be recorded as zero usage. Missing provider usage also defaults to zero. |
| Checkpointing | Only cell summaries survive the temporary episode database; checkpoints are after cells and overwrite the report directly. In-flight usage is not reserved or durably checkpointed. |
| Reachability join | The existing `harm_reachable` uses a rules-only solver and `harm_upper > 0`. It omits the monitor and conflates pending uncertainty with demonstrated completed harm. |
| Reporting | Fake transports can be labeled `network_called=true` and paid; this field reflects the requested mode, not observed HTTP transport. |
| Family restriction | Lower-level provider code additionally supports xAI, despite the setup page's Luna/Haiku-only heading. The live CLI restricts choices to Luna/Haiku/local. |
| Model identity | Missing response model IDs fall back to the requested ID. Substring matching for Haiku is broader than an exact allowlist. |
| Task diversity | Fixture seeds change identifiers and nonces, while each family's state, rules, and action sequence remain the same. These are not new task environments. |

## Reproduced failures, using dummy keys and fake transport

1. `run_experiment(provider='openai', episodes=1, cap_usd=0, dry_run=False,
   transport=StubTransport(...))` made **six fake requests**, then reported
   `$0.000130`. A zero cap should prevent the first request.
2. A fake response returning 24 input tokens and six output tokens but invalid
   action text produced six fake requests and **zero total reported usage and
   cost**. The requests were simulated, but the same accounting path handles
   real paid responses.

The new offline perturbation map addresses the interpretation of reachability;
it does **not** repair the live driver or change its skip rule. Before a paid run,
add a shared pre-request reservation ledger, durable usage-before-parsing,
unknown-request handling, atomic checkpoints, and validation of finite positive
budgets. Use monitor-inclusive completed-harm reachability for the relevant
question while retaining unresolved-pending information and honest-work cells.
Neither spending issue is resolved merely by choosing cheaper models.

## API keys on GitHub

If a manual paid workflow is later added, use this repository's **Settings →
Secrets and variables → Actions**, creating `OPENAI_API_KEY` and
`ANTHROPIC_API_KEY`. Repository secrets in SASB are not automatically available
here. An organization secret can be shared only if configured to cover both
repositories. Keys must not be committed or pasted into issues. Adding secrets
alone will not make the current offline workflow call either API.

This audit changes no API client, live budget, task manifest, or frozen rules.
It records concrete remaining defects so the offline results cannot be mistaken
for live-run readiness.
