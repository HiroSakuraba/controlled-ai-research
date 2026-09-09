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

This repository contains the research design and a finite prototype through stage 4. Stages 1–4 use the standard library only. Learned monitors, model attackers, and priced-call comparisons belong to later stages.

## Related work

The plan draws on AI control research, David Dalrymple’s Safeguarded AI programme, quantilization, and the author's [Certified Cognitive Glue / Freehold Commons project](https://github.com/HiroSakuraba/Multi-agent-certificate-framework.). The document includes source references and mathematical derivations.


## Run the prototype

Python 3.10 or later; standard library only. From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 -m controlled_ai
```

The first command tests the controls. The second prints a JSON report with exact
finite-horizon harm bounds, executor crash recovery, the checked-discovery
ledger, and runtime. A recorded run is in
[reports/finite-run.json](reports/finite-run.json).

GitHub Actions runs the same tests on pushes, pull requests, and manual dispatch. Each run publishes its generated JSON report as a downloadable artifact for 30 days; it does not modify the source tree.

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
protection produces a concrete harmful trace. Experiment A’s evaluator checks
released truth tables independently of approval and returns a failing input.

The executor issues HMAC permits bound to the action, artifact, destination,
full state, and rule set, with an expiry in executor steps. Consume, the local
snapshot, and the dispatch record share one SQLite transaction. A later
transaction records a simulated remote effect. A crash between those
transactions resumes the same nonce and writes the effect once. Restart cannot
replay a consumed nonce. Changed payloads, destinations, states, policies, and
expired permits are rejected. The database still cannot atomically commit a
real remote effect. Protecting keys, authoritative state, and database
integrity remains the host's responsibility.

The discovery experiment synthesizes straight-line 12-bit programs. Generators
receive sixteen public input/output examples and a frozen statement; they do
not import the held-out evaluator. The checker compares every candidate against
the total function on all 4,096 inputs, with a step limit and a checker budget,
and records the accepted digest. Release is allowed only for that digest.
Six public tasks are single-opcode; three held-out families need two opcodes.
A length-1 enumerative search verifies all six public tasks and none of the
held-out tasks. A one-shot symbolic fit from the first example misses the
public `and` mask (the first public input is zero) and all held-out families.
A length-2 enumerative search verifies all nine tasks under the same checker
and permissions. Negative controls cover invalid syntax, a weakened statement,
an incorrect program, a step-limit violation, and a mismatched release digest.

The certificate checker uses exact fractions and a trusted finite transition
kernel. It checks nonnegative potential and positive drift at every unfinished
state, yielding an expected time-to-completion bound. The example gives four
steps. Stalling, incomplete distributions, unknown successors, and floating
point probabilities are rejected.

Specified monitors (not learned models) flag corrupt artifacts, delayed
effects, replayed authority, and reserve spends. Removing the matching channel
lets each of the four ablation attacks through; the full set blocks them and
still permits the honest release. A trusted edit recovers a useful release
from the unbound-payload attack; an audit denies it. An overbroad release
flag blocks honest work. A monitor timeout withholds; it does not authorize.
Actor and checker ceilings stop floods; the same padded honest workload still
completes. Cap violations are not observed when the ceiling is enforced.
Disabling the actor cap lets the flood-then-release attack succeed.

The evidence store counts a shared evaluator root once, keeps unverified
origin unknown after laundering, and detects a circular citation. Review
authorizes an honest proposal, blocks a correct minority objection, records
dissent when that objection is overruled, rejects a material change after
freeze, and exhausts a two-objection budget.

A replacement with its own key completes an ordinary approved release after
revocation. The actor’s leftover token is rejected under an independent key
and accepted when the signing key is shared. Trusting a stale export loses
the approval and misses a pending job; copying live state completes the
release and cancels the pending job under cancel-on-revoke. Wiping a shared
database drops both paths. Spending the recovery reserve makes takeover
unavailable.

Next work: implement the shared probability budget and evaluate its reference
process. Model attackers and learned monitors remain out of this stdlib
prototype.

## Usage record

This prototype uses no external model API calls, paid services, new dependencies,
or delegated agents. Thirty-eight tests passed in the recorded run. The report
records experiment runtime, state counts, recovery of one in-flight release,
the discovery ledger, monitor complementarity, exhaustion caps, provenance
review, and takeover fixtures. These measurements cover local execution only.
ChatGPT token use, Plus allowance consumption, remaining quota, and account
charges are unavailable to this process and are not estimated.
