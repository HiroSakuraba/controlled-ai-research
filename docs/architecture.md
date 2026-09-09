# Architecture

```mermaid
flowchart TD
  Actor["Actor adapter"] --> Runner["Episode runner"]
  Monitor["Monitor adapter"] --> Runner
  Runner --> Ledger["Signed episode ledger"]
  Runner --> Executor["Executor"]
  Issuer["Trusted permit issuer"] --> Executor
  Executor --> Effects["Idempotent effect receiver"]
  Worker["Discovery worker"] --> Custody["Evaluator custody process"]
  Custody --> Certificates["Signed acceptance certificates"]
```

The actor proposes JSON actions. The runner records every decision and monitor response before applying it. The executor accepts consequential actions only with a state-bound permit. The discovery worker receives signed public task manifests; the evaluator-custody process retains task generation and certification authority.

This diagram is an interface map, not a deployment claim. The concrete trust assumptions are in the [threat model](threat-model.md).
