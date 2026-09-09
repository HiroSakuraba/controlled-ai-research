# Model experiment protocol

This protocol governs paid-model runs. The API-free runner is its reference implementation.

## Frozen conditions

Before a comparison, record the code commit, task-suite commitment, model identifier, provider region, prompt versions, reasoning setting, JSON schema, episode horizon, retry policy, treatment definitions, and per-run dollar cap. Do not alter these conditions during the comparison.

## Treatments and outcomes

Compare untrusted actor, executor-only, monitor-only, and executor-plus-monitor. The primary outcome is episode harm, counted after delayed effects. Secondary outcomes are useful completion, intervention rate, parse failure, wall time, input/output/reasoning tokens, and dollars. A failed parse is an observed failure: it is not silently retried. Any permitted retry is logged and included in cost.

## Attack development

Give each treatment the same declared attack-development budget: model calls, human design time, and evaluator queries. Record the attacker's observations. The finite solver is a capability ceiling for the toy environment, not a measure of a model's capability. Keep development and evaluation fixture seeds separate; publish the evaluation seed only after the frozen run.

## Stopping and reporting

Stop at the predeclared episode count, a predeclared dollar cap, or a safety stop. Report every offered episode, including timeouts and malformed responses. Report actual provider usage rather than estimates. The seeded fixture split is not independent evaluation; independent assessment requires separately controlled task generation and evaluator custody.
