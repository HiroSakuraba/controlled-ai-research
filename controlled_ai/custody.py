"""Process-separated evaluator custody for finite generated tasks.

The verifier process retains the generation seed, manifest signing key, and task
functions. Workers receive only signed public manifests and submit programs.
This is a local architectural prototype, not an operating-system sandbox.
"""
import hashlib, hmac, json, multiprocessing as mp, sqlite3
from dataclasses import asdict, dataclass
from .discovery import DOMAIN, MASK, WIDTH, IMMS, interpret, program_digest, SyntaxViolation, StepLimit

CHECKER_VERSION = 'custody-exhaustive-12bit-v1'
CHECKER_DIGEST = hashlib.sha256(CHECKER_VERSION.encode()).hexdigest()
PUBLIC_XS = (0,1,2,3,7,8,15,16,31,64,127,128,255,256,1023,4095)

class CustodyError(ValueError): pass

def _canon(x): return json.dumps(x, sort_keys=True, separators=(',', ':'))
def _sign(key, payload): return hmac.new(key, _canon(payload).encode(), hashlib.sha256).hexdigest()
def _op(name, k, x):
    if name == 'xor': return (x ^ k) & MASK
    if name == 'and': return x & k
    if name == 'or': return x | k
    if name == 'add': return (x + k) & MASK
    if name == 'shl': return (x << (k % WIDTH)) & MASK
    raise CustodyError('unknown generator operation')

def _spec(seed, index):
    raw=hashlib.sha256((seed + ':' + str(index)).encode()).digest()
    names=('xor','and','or','add','shl'); a,b=names[raw[0]%5],names[raw[1]%5]
    ka,kb=IMMS[raw[2] % len(IMMS)],IMMS[raw[3] % len(IMMS)]
    return a,ka,b,kb

def _target(seed,index,x):
    a,ka,b,kb=_spec(seed,index); return _op(b,kb,_op(a,ka,x))
def _task_id(seed,index): return 'task-' + hashlib.sha256((seed + ':' + str(index)).encode()).hexdigest()[:20]

def _manifest(seed,index):
    return {'task_id':_task_id(seed,index),'suite_commitment':hashlib.sha256(seed.encode()).hexdigest(),
            'index':index,'width':WIDTH,'domain':DOMAIN,'examples':[(x,_target(seed,index,x)) for x in PUBLIC_XS],
            'statement':'total 12-bit function; examples are not the specification','checker_version':CHECKER_VERSION,'checker_digest':CHECKER_DIGEST}

def _verify_program(seed, manifest, program, claimed):
    required={k:manifest[k] for k in ('task_id','width','domain','examples','statement','checker_version','checker_digest')}
    if claimed != required: return {'accepted':False,'reason':'statement_mismatch','digest':None}
    try: digest=program_digest(program)
    except (TypeError,ValueError): return {'accepted':False,'reason':'invalid_syntax','digest':None}
    try:
        for x in range(DOMAIN):
            y,n=interpret(program,x,8)
            if y != _target(seed,manifest['index'],x): return {'accepted':False,'reason':'incorrect','digest':digest,'witness':x}
    except SyntaxViolation: return {'accepted':False,'reason':'invalid_syntax','digest':digest}
    except StepLimit: return {'accepted':False,'reason':'step_limit','digest':digest}
    return {'accepted':True,'reason':'equivalent','digest':digest,'witness':None}

def _serve(conn, seed, signing_key, db_path):
    db=sqlite3.connect(db_path)
    db.execute('CREATE TABLE IF NOT EXISTS accepted (task_id TEXT NOT NULL, digest TEXT NOT NULL, certificate TEXT NOT NULL, PRIMARY KEY(task_id,digest))'); db.commit()
    while True:
        request=conn.recv()
        if request is None: db.close(); return
        kind=request['kind']
        if kind == 'publish':
            manifest=_manifest(seed,request['index']); conn.send({'manifest':manifest,'signature':_sign(signing_key,manifest)}); continue
        if kind == 'submit':
            envelope=request['envelope']; manifest=envelope.get('manifest')
            if not isinstance(manifest,dict) or envelope.get('signature') != _sign(signing_key,manifest): conn.send({'accepted':False,'reason':'invalid_manifest'}); continue
            if manifest != _manifest(seed,manifest.get('index')): conn.send({'accepted':False,'reason':'unknown_or_modified_task'}); continue
            result=_verify_program(seed,manifest,request['program'],request['claimed'])
            if result['accepted']:
                cert={'task_id':manifest['task_id'],'digest':result['digest'],'checker_version':CHECKER_VERSION,'checker_digest':CHECKER_DIGEST,'manifest_signature':envelope['signature']}
                cert['signature']=_sign(signing_key,cert)
                with db: db.execute('INSERT OR REPLACE INTO accepted VALUES (?,?,?)',(cert['task_id'],cert['digest'],_canon(cert)))
                result['certificate']=cert
            conn.send(result); continue
        if kind == 'release':
            task_id,digest=request['task_id'],request['digest']; row=db.execute('SELECT certificate FROM accepted WHERE task_id=? AND digest=?',(task_id,digest)).fetchone()
            conn.send({'released':row is not None,'certificate':None if row is None else json.loads(row[0])}); continue
        conn.send({'error':'unknown request'})

class CustodyService:
    def __init__(self, seed, signing_key, path=':memory:'):
        if len(signing_key)<16: raise CustodyError('signing key too short')
        parent, child=mp.Pipe(); self.conn=parent; self.proc=mp.Process(target=_serve,args=(child,seed,signing_key,path)); self.proc.start()
    def _call(self,request): self.conn.send(request); return self.conn.recv()
    def publish(self,index): return self._call({'kind':'publish','index':index})
    def submit(self,envelope,program,claimed): return self._call({'kind':'submit','envelope':envelope,'program':program,'claimed':claimed})
    def release(self,task_id,digest): return self._call({'kind':'release','task_id':task_id,'digest':digest})
    def close(self):
        if self.proc.is_alive(): self.conn.send(None); self.proc.join(5)
        if self.proc.is_alive(): self.proc.terminate()

def claim(manifest): return {k:manifest[k] for k in ('task_id','width','domain','examples','statement','checker_version','checker_digest')}
