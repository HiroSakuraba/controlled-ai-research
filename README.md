# Controlling Advanced AI

A research program for obtaining reliable work from advanced AI through controlled execution, independent verification, and adversarial testing.

**Author:** Benjamin John Schulz

Read the [detailed research plan](docs/research-plan.html). Download the HTML and open it in a browser to view its formatting and navigation.

## Approach

A capable model investigates problems and proposes solutions. An independent execution service controls credentials, permissions, resource budgets, and consequential operations. Exact checkers verify outputs where possible; monitors and adversarial experiments evaluate tasks that resist complete verification.

The program studies state-bound single-use permissions, evidence provenance, constrained sampling across complete episodes, and trusted recovery after access is revoked. Progress certificates provide independently checkable bounds on unfinished work under specified transition models.

## Experiments

| Experiment | Question |
| --- | --- |
| A — Authority | Do execution controls enforce their specified properties? |
| B — Residual harm | Does monitoring reduce independently demonstrated failures? |
| C — Optimization | Does executed sampling satisfy its probability bound? |
| D — Discovery | Does stronger generation produce more independently verified work? |
| E — Computational exhaustion | Can an attacker exhaust actor, monitor, checker, or recovery resources? |
| F — Recovery | Can a trusted replacement take over and complete outstanding work? |

## Implementation sequence

1. Define the finite interpreter, task contracts, independent evaluator, and resource limits.
2. Implement the executor, a tiny exact attacker benchmark, and a rational progress-certificate checker.
3. Run independently checked discovery experiments.
4. Evaluate model attackers, monitoring, evidence provenance, computational exhaustion, and takeover.
5. Implement the shared probability budget and evaluate its reference process.
6. Freeze configurations and perform held-out comparisons.
7. Expand one dimension at a time and repeat the retained comparisons.

This repository contains the research design and an initial finite prototype. Implementation and experimental results will be added as the work proceeds.

## Related work

The plan draws on AI control research, David Dalrymple’s Safeguarded AI programme, quantilization, and the author's [Certified Cognitive Glue / Freehold Commons project](https://github.com/HiroSakuraba/Multi-agent-certificate-framework.). The document includes source references and mathematical derivations.


## Run the prototype

Python 3.10 or later; standard library only. From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 -m controlled_ai
```

The first command tests the controls. The second prints a JSON report with exact
finite-horizon harm bounds, attack traces, explored state counts, and runtime.
A recorded run is in [reports/finite-run.json](reports/finite-run.json).

The environment has eight actions, two fixed artifact truth tables, a single
approval, ordinary resources, a recovery reserve, and a pending effect. Search
covers all action sequences through six decisions, with a 100,000 state-time
ceiling. The attacker fully observes the state. These deterministic results are
0/1 reachability bounds, not measured attack probabilities against AI models.
Pending effects at truncation receive an upper harm bound of one. The delayed
effect fixture deliberately starts with a pending job after revocation; it tests
continued evaluation rather than reachability from the clean initial state.

The hardened configuration permits an honest release and has no harmful trace
within this search. Disabling payload binding, replay protection, or reserve
protection produces a concrete harmful trace. The evaluator checks released
truth tables independently of approval and returns a failing input. This tiny
public truth table is not the planned held-out level-two evaluator.

`PermitStore` separately demonstrates authenticated payload/state binding and
SQLite-backed single-use nonces across restart. The caller supplies a trusted
state identifier and complete payload digest. It is not yet connected to the
finite executor or a real tool gateway. Its database transaction records permit
consumption, not atomic completion of an external effect. Protecting keys,
authoritative state, and database integrity remains the host's responsibility.

The certificate checker uses exact fractions and a trusted finite transition
kernel. It checks nonnegative potential and positive drift at every unfinished
state, yielding an expected time-to-completion bound. The example gives four
steps. Stalling, incomplete distributions, unknown successors, and floating
point probabilities are rejected.

Next work: connect durable permits to the executor, add crash/recovery tests,
and implement the checked-discovery experiment with a held-out evaluator.

## Usage record

This prototype uses no external model API calls, paid services, new dependencies,
or delegated agents. Twelve tests passed in the initial run (0.013 seconds).
The report records experiment runtime and state counts. These measurements cover
local execution only. ChatGPT token use, Plus allowance consumption, remaining
quota, and account charges are unavailable to this process and are not estimated.
