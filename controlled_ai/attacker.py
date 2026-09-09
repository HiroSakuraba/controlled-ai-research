"""Budgeted local attack development and exact finite-game capability ceiling."""
from .model import State
from .solver import solve
class AttackBudget:
    def __init__(self, calls): self.remaining=calls; self.tried=[]
    def propose(self, actions):
        if self.remaining <= 0: raise RuntimeError('attack-development budget exhausted')
        self.remaining -= 1; self.tried.append(tuple(actions)); return tuple(actions)
def exact_ceiling(rules, horizon=6): return solve(State(), rules, horizon=horizon)['harm_upper']
def scripted_attack(budget, actions): return budget.propose(actions)
