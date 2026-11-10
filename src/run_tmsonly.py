"""run_tmsonly.py — how much of the adaptation bound comes from time
multipliers alone?  Per-state certified time multipliers with the fixed
design's pickups and instantaneous settings.
usage: python run_tmsonly.py 33 -> results/tmsonly_<feeder>.json"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES, FIGS, TEX, SRC
import sys, json, pickle, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings as S
import policies as P
name = sys.argv[1] if len(sys.argv) > 1 else '33'
ds = pickle.load(open(RES + f'/ds_{name}_base.pkl', 'rb'))
D = P.Designer(ds); nS = len(ds['scen']); rob = D.design(list(range(nS)))
tot_r = tot_t = n = 0.0; feas = 0
for s in range(nS):
    tp, tn, info = S.coordinate(ds, [s], rob['st'], D.ct)
    feas += info['feasible']
    _, t0, _ = S.evaluate(ds, [s], lambda q: (rob['st'], rob['tp'], rob['tn']))
    _, t1, _ = S.evaluate(ds, [s], lambda q: (rob['st'], tp, tn))
    f0, f1 = np.isfinite(t0), np.isfinite(t1)
    tot_r += t0[f0].sum(); tot_t += t1[f1].sum(); n += f0.sum()
out = dict(feasible=int(feas), n=nS, mean_t_fixed=tot_r/n, mean_t_tms_only=tot_t/n,
           gain_pct=100*(1 - tot_t/tot_r))
json.dump(out, open(RES + f'/tmsonly_{name}.json', 'w'), indent=1)
print(out)
