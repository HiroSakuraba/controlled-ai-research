"""Local process boundary for the canonical evaluator fixture.

This is an interface boundary, not a hardened sandbox. Production requires OS
credentials, a dedicated key, and an evaluator deployment the worker cannot alter.
"""
import multiprocessing as mp

def _serve(conn):
    from .evaluator import verify
    while True:
        request = conn.recv()
        if request is None: return
        task_id, program, claimed = request
        conn.send(verify(task_id, program, claimed))

class VerifierProcess:
    def __init__(self):
        parent, child = mp.Pipe(); self.conn = parent; self.proc = mp.Process(target=_serve, args=(child,))
        self.proc.start()
    def verify(self, task_id, program, claimed):
        self.conn.send((task_id, program, claimed)); return self.conn.recv()
    def close(self):
        if self.proc.is_alive(): self.conn.send(None); self.proc.join(5)
        if self.proc.is_alive(): self.proc.terminate()
