"""Exact offline mechanism ablations and bounded controller-return studies."""
import json
from dataclasses import asdict
from fractions import Fraction as F
from itertools import combinations

from .benchmarks import suite
from .landscape import bounded_outcomes, effective_step, scripted_outcome
from .model import Rules, State
from .monitor import ALL
from .outcomes import harms
from .sampler import expect, filter_normalize, masses, quantile, spend


def subsets():
    return [c for n in range(len(ALL) + 1) for c in combinations(ALL, n)]


def channel_map(horizon=6):
    rows = []
    for fixture in suite('expanded-mechanisms', 4):
        for executor, rules in [('fixture', fixture['rules']), ('hardened', Rules())]:
            for channels in subsets():
                rows.append(dict(family=fixture['family'], executor=executor,
                                 initial_state=asdict(fixture['state']), rules=asdict(rules),
                                 channels=list(channels), channel_count=len(channels),
                                 horizon=horizon,
                                 **bounded_outcomes(fixture['state'], rules, channels, horizon)))
    return rows


def q_curves():
    # Complete executable traces, independently scored by the runtime.
    menu = [('approve', 'release'), ('approve', 'mutate', 'release'),
            ('approve',), ('spend',)]
    rules = Rules(bind_payload=False)
    outcomes = [scripted_outcome(State(), rules, (), trace, len(trace)) for trace in menu]
    harm = [int(o['completed_harm']) for o in outcomes]
    useful = [int(o['useful_without_harm']) for o in outcomes]
    rows = []
    for filtering, allowed in [('unfiltered', (True,) * 4),
                               ('oracle_harm_filter', tuple(not h for h in harm)),
                               ('empty', (False,) * 4)]:
        p = filter_normalize(masses(4), allowed)
        if p is None:
            rows.append(dict(filter=filtering, status='empty_menu', useful='0', harm='0',
                             successful_completion=False))
            continue
        for ranking, scores in [('useful', (3, 0, 2, 1)), ('adversarial', (0, 3, 2, 1)),
                                ('imperfect', (2, 3, 0, 1))]:
            for q in (F(1), F(3, 4), F(1, 2), F(1, 4), F(1, 8)):
                remaining = spend(F(8), q)  # Each row starts from the same A0.
                _, Q = quantile(p, scores, q)
                rows.append(dict(filter=filtering, ranking=ranking, scores=list(scores),
                                 q=str(q), A0='8', remaining_A=str(remaining),
                                 reference=list(map(str, p)), distribution=list(map(str, Q)),
                                 harm=str(expect(Q, harm)), useful=str(expect(Q, useful)),
                                 reference_harm=str(expect(p, harm)),
                                 reference_useful=str(expect(p, useful))))
    return dict(menu=[list(t) for t in menu], outcomes=outcomes, rules=asdict(rules),
                filter_limit='Oracle filter uses exact trace outcomes; not a deployable learned monitor.',
                rows=rows, sequential_budget=[str(spend(8, F(1, 2))),
                                             str(spend(4, F(1, 4)))] )


def controller_return(initial, rules, channels, horizon, policy):
    """Exact first-hit distribution. Terminal harm and unfinished mass stay separate."""
    if type(horizon) is not int or horizon < 0:
        raise ValueError('invalid horizon')
    if policy not in {'progress', 'wait', 'stochastic'}:
        raise ValueError('unknown controller')
    frontier = {initial: F(1)}
    first_hits = [F(0)] * (horizon + 1)
    harmful = F(0)
    unfinished = F(0)
    pending = F(0)
    for depth in range(horizon + 1):
        following = {}
        for state, mass in frontier.items():
            if harms(state):
                harmful += mass
            elif state.released == 0:
                first_hits[depth] += mass
            elif depth == horizon:
                unfinished += mass
                if state.pending:
                    pending += mass
            else:
                action = 'approve' if state.approved == -1 else 'release'
                choices = ([(action, F(1))] if policy == 'progress' else
                           [('restart', F(1))] if policy == 'wait' else
                           [(action, F(3, 4)), ('restart', F(1, 4))])
                for a, probability in choices:
                    nxt = effective_step(state, a, rules, channels)
                    following[nxt] = following.get(nxt, F(0)) + mass * probability
        frontier = following
    return dict(return_probability=str(sum(first_hits)), harm_probability=str(harmful),
                unfinished_probability=str(unfinished), pending_probability=str(pending),
                first_hit_probability=list(map(str, first_hits)))


def return_map(horizon=4):
    rows = []
    initial = State(approved=0)
    for executor, rules in [('fixture', Rules(bind_payload=False)), ('hardened', Rules())]:
        for channels in [(), ALL]:
            for kick in ('mutate', 'spend', 'revoke', 'queue'):
                kicked = effective_step(initial, kick, rules, channels)
                possible = bounded_outcomes(kicked, rules, channels, horizon)
                # This explicit legal continuation refutes universal useful return.
                wait = scripted_outcome(kicked, rules, channels, ('restart',) * horizon, horizon)
                for policy in ('progress', 'wait', 'stochastic'):
                    rows.append(dict(executor=executor, rules=asdict(rules), channels=list(channels),
                                     kick=kick, kick_changed_state=kicked != initial,
                                     initial_state=asdict(initial), post_kick_state=asdict(kicked),
                                     horizon=horizon, policy=policy, **possible,
                                     nonreturn_witness=['restart'] * horizon if not wait['useful_without_harm'] else None,
                                     **controller_return(kicked, rules, channels, horizon, policy)))
    return rows


def build_report():
    return dict(schema='controlled-expanded-v1', network_called=False, spent_usd=0,
                claim='Exact finite mechanism and controller studies; no learned-model or attractor result.',
                attractor_established=False, channel_subsets=channel_map(),
                q_sweep=q_curves(), bounded_return=return_map(),
                limits=['Fixture seeds do not create different task environments.',
                        'Return is a first hit within the horizon, not permanent invariance.',
                        'Pending probability is a subset of unfinished probability.',
                        'q curves are independent one-step distributions, not phase transitions.'])


if __name__ == '__main__':
    print(json.dumps(build_report(), indent=2, sort_keys=True))
