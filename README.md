# Controlling Advanced AI

A research program for obtaining reliable work from advanced AI through controlled execution, independent verification, and adversarial testing.

**Author:** Benjamin John Schulz

Read the [detailed research plan](docs/research-plan.html). Download the HTML and open it in a browser to view its formatting and navigation.

The multi-agent behavioral program is a sibling repository: [alignment-integrity-sasb](https://github.com/HiroSakuraba/alignment-integrity-sasb). That harness studies four-agent alignment integrity and does not replace the finite control kernel here.

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
6. Freeze configurations and perform predeclared fixture comparisons.
7. Expand one dimension at a time and repeat the retained comparisons.

This repository contains the research design and a finite prototype through stage 7’s stdlib expansions. Stages 1–7 here use the standard library only. Learned monitors, model attackers, priced-call comparisons, training-method changes, and a 29,956-episode model reference audit need a model API and are not in this prototype.

## Related work

The plan draws on AI control research, David Dalrymple’s Safeguarded AI programme, quantilization, and the author's [Certified Cognitive Glue / Freehold Commons project](https://github.com/HiroSakuraba/Multi-agent-certificate-framework.). The document includes source references and mathematical derivations.

## Run the prototype

Python 3.10 or later; standard library only. From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 -m controlled_ai
```

The first command tests the controls. The second prints a JSON report. A recorded run is in [reports/finite-run.json](reports/finite-run.json).

GitHub Actions runs the same tests on pushes, pull requests, and manual dispatch.

See the remainder of this file on `main` prior to this sentence for the full prototype narrative, or keep reading the existing detailed sections below if this update is applied as a full rewrite.
