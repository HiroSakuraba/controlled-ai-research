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

This repository currently contains the research design. Implementation and experimental results will be added as the work proceeds.

## Related work

The plan draws on AI control research, David Dalrymple’s Safeguarded AI programme, quantilization, and the author's [Certified Cognitive Glue / Freehold Commons project](https://github.com/HiroSakuraba/Multi-agent-certificate-framework.). The document includes source references and mathematical derivations.
