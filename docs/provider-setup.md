# Provider setup (Luna and Haiku only)

Do not paste API keys into git, issues, or episode records.

## Allowed models

| Provider | Model id |
| --- | --- |
| OpenAI | `gpt-5.6-luna` |
| Anthropic | `claude-haiku-4-5-20251001` (aliases `claude-haiku-4-5`, `claude-haiku-4.5`) |

Sol, Terra, Sonnet, and Opus are rejected when constructing `ProviderConfig`.
A live response may use a dated Luna id such as `gpt-5.6-luna-…` or a Haiku id
that contains `haiku-4-5`; those are accepted after the request. Other families
are still rejected. The dry-run does not call the network.

Copy `.env.example` to `.env`. The loader accepts literal `KEY=value` lines only
and never evaluates shell commands. Existing environment values win.
`python3 -m controlled_ai.providers` now loads that file. OpenAI chat calls use
`max_completion_tokens` and `reasoning_effort=none`. Redirects are rejected.

## Local config

```sh
cp .env.example .env
python3 -m controlled_ai.providers
python3 -m controlled_ai.live --dry-run --episodes 16 --cap-usd 1.00
```

The first command prints a readiness report and writes
`reports/provider-setup-local.json`. That file is gitignored. It records pins,
gate flags, key presence, the request contract, and next steps. It does not
call the network and does not store key values.

The second command runs the experiment driver against `ScriptedActor`. It writes
`reports/live-run-local.json` (also gitignored) with per-arm Wilson intervals,
paired sign tests, schema-failure rates, and the solver reachability join.
It does not call the network.

Paid runs default to `reports/live-run-paid.json`, which is intentionally not
gitignored so measured usage, spend, and the stopping reason can be retained for
review. Pass `--out` to select another destination. A zero-dollar cap is checked
before the first provider request and therefore performs no paid calls.

Live calls also require both of:

```sh
export CONTROLLED_AI_ENABLE_NETWORK=1
export CONTROLLED_AI_VALIDATE_PROVIDER_WIRE=1
python3 -m controlled_ai.live --provider anthropic --episodes 16 --cap-usd 1.00
```

Leave those unset until the dry-run shows the pinned models and the local
driver report looks right. Cells with `harm_reachable=0` are not paid unless
`--pay-unreachable` is set. The finite prototype tests stay local either way.
Transport failures keep the original exception as `__cause__` and do not copy
exception text into episode records.

Do not enable the two switches just because the SASB harness has a separate
bounded worker pilot. The monitor in this driver is still rule-based.
