# Contributing

This repository makes narrow claims about a deterministic finite prototype. Keep an implementation claim separate from a claim about learned models, real systems, or external effects.

Before opening a change:

1. Run the test suite and report verifier.
2. Add a regression test for every fixed safety or integrity defect.
3. Update `reports/finite-run.json` if deterministic results change.
4. State whether the change alters the threat model, experimental protocol, task manifest, or frozen configuration.
5. Do not add API keys, credentials, or provider-specific client code to the repository.

Use exact fractions for mathematical controls. Treat malformed model output, timeout, and retry behavior as measured outcomes rather than invisible cleanup.
