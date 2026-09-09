# Project entry point

This repository is a finite, deterministic prototype for research on controlled
AI execution. It is not evidence about the behavior of a frontier model.

Start by reading, in order:

1. `README.md` for the scope and the claims the prototype does and does not make.
2. `docs/research-plan.html` for the broader research program.
3. `docs/threat-model.md` before changing any trust boundary.
4. `docs/model-experiment-protocol.md` before adding a provider or running a model.
5. `docs/HISTORICAL_NO_GO_LEDGER.md` and `docs/EXPLORATORY_MAP.md` before reviving an abandoned direction.

Run `make test` and `make verify` before and after a change. The latter
regenerates and checks `reports/finite-run.json`.

## Load-bearing invariants

- Consequential `release` and `queue` actions require a single-use permit.
- A permit binds the complete payload, destination, full state, and expiry.
- Dispatch state and nonce consumption share one SQLite transaction.
- A remote effect is only simulated here. Receiver-side nonce deduplication and
  reconciliation are necessary in a deployment.
- The evaluator, not the worker, resolves hidden tasks and issues acceptance
  certificates.
- A sampler menu is a complete exported choice, including payload and destination.
- Prompt files are versioned and hash-checked. Network access is disabled by default.

## Change rules

Do not weaken an invariant merely to make an experiment easier to run. Add a
new ablation or explicit unsafe fixture instead. Keep model providers, API keys,
and paid calls outside the repository. Any live-provider implementation needs a
recorded validation of its wire format, structured output, timeout path, and
usage accounting before it is enabled.
