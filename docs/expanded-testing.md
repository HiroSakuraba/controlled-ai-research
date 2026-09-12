# Exact expanded mechanism studies

`controlled_ai.expanded` separates three questions: which mechanisms remove a harmful path, how a declared sampler allocates probability, and whether a declared controller returns to useful completion after a perturbation. These are offline finite-model experiments, not measurements of an LLM.

## Monitor subsets

The report covers all 16 subsets of four monitor channels, four mechanism families, and fixture versus hardened executor rules: 128 rows at horizon six. Channel identity is retained, because two subsets of equal size need not protect against the same mechanism. Each row records completed-harm reachability, useful-without-harm reachability, unresolved pending work, and executable witnesses. Tests replay each witness using the recorded state and rules. Absence of harm alone does not imply useful work is possible.

## Exact q curves

Four complete executable choices are scored by the runtime: an authorized release, a payload-substitution violation, an approval without release, and an incomplete spending action. From a uniform reference measure, the experiment sweeps q = 1, 3/4, 1/2, 1/4, 1/8 under useful, adversarial, and imperfect rankings. Every probability and expectation is an exact rational.

Each row begins with amplification budget A = 8. Smaller q concentrates probability on the ranking's preferred choices; it need not reduce harm. Tests verify normalization, the pointwise reference/q bound, q=1 agreement, hand-calculated harm and usefulness, and shared-budget exhaustion. Independent curve rows are not repeated free draws from a single budget.

An oracle harm filter illustrates renormalization after excluding harmful choices; it knows exact outcomes and is not a deployable learned monitor. The empty-menu control records no successful completion. A sharp change in this finite menu can reflect discrete ranking cutoffs, not a phase transition or collective dynamics.

## Bounded return after a kick

An approved state is perturbed through the actual executor and monitor with mutation, spending, revocation, or queueing. The report distinguishes a blocked kick from a changed state. Across fixture/hardened rules, no/all monitor channels, and three explicit controllers, 48 rows calculate exact first-hit distributions through four steps.

The progress controller tries approval or release; the waiting controller restarts; the stochastic controller takes progress with probability 3/4 and restart with probability 1/4. Probability is partitioned into useful first return, completed harm, and unfinished work. Pending probability is a subset of unfinished work, not an extra disjoint outcome. First return is not permanent recovery: this experiment terminates scoring at the first useful hit.

Existential reachability is reported alongside controller probability. A replayable restart continuation provides a counterexample to universal useful return. No fairness assumption silently excludes that continuation. Waiting forever cannot be counted as useful recovery.

## Reproduction and limits

Run `make expanded-report` to write `reports/expanded-testing.json`. Focused checks: `python -m unittest discover -s tests -p test_expanded.py -v`. No network or paid model calls are needed.

The finite grammar cannot discover new action types. Fixture seeds do not create environment diversity. These results establish neither attractors nor hysteresis. The next step is a declared continuing-work state set, explicit fairness assumptions if appropriate, and invariance/return checks over that extended state, followed by separately budgeted model propensity trials. The SASB repeated-work experiment supplies complementary memory-sensitive behavior, not an interchangeable proof for this executor.
