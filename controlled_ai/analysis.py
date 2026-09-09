"""Dependency-free analysis for preregistered finite/model episode comparisons."""
import math

def wilson(successes, total, z=1.959963984540054):
    if total < 1 or not 0 <= successes <= total: raise ValueError('invalid count')
    p=successes/total; d=1+z*z/total; center=(p+z*z/(2*total))/d
    half=z*math.sqrt((p*(1-p)+z*z/(4*total))/total)/d
    return (0. if center-half < 1e-15 else center-half, 1. if center+half > 1-1e-15 else center+half)

def _choose(n,k): return math.comb(n,k)
def exact_sign_pvalue(positive, negative):
    """Two-sided exact paired sign test; ties are ignored."""
    n=positive+negative
    if n==0: return 1.0
    tail=sum(_choose(n,i) for i in range(0,min(positive,negative)+1))/2**n
    return min(1.0,2*tail)

def paired_summary(rows, baseline='untrusted', treatment='combined'):
    """Rows carry episode, system, harm, useful; paired by episode identity."""
    a={r['episode']:r for r in rows if r['system']==baseline}; b={r['episode']:r for r in rows if r['system']==treatment}
    shared=sorted(set(a)&set(b)); wins=losses=ties=0
    for e in shared:
        delta=a[e]['harm']-b[e]['harm']
        if delta>0: wins+=1
        elif delta<0: losses+=1
        else: ties+=1
    return {'pairs':len(shared),'harm_reduced':wins,'harm_increased':losses,'harm_tied':ties,'p_value':exact_sign_pvalue(wins,losses)}

def episode_summary(rows):
    n=len(rows); harm=sum(int(r['harm']) for r in rows); useful=sum(int(r['useful']) for r in rows)
    return {'episodes':n,'harm':harm,'harm_rate':harm/n if n else None,'harm_wilson95':wilson(harm,n) if n else None,'useful':useful,'useful_rate':useful/n if n else None,'useful_wilson95':wilson(useful,n) if n else None}

def stopping_rule(rows, max_episodes, dollar_cap, spent, target_harm_upper):
    s=episode_summary(rows)
    return {'stop':len(rows)>=max_episodes or spent>=dollar_cap or (s['harm_wilson95'] is not None and s['harm_wilson95'][1]<=target_harm_upper),'reason':'episode_cap' if len(rows)>=max_episodes else 'dollar_cap' if spent>=dollar_cap else 'target_met' if s['harm_wilson95'] and s['harm_wilson95'][1]<=target_harm_upper else 'continue','summary':s}
