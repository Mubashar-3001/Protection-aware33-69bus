"""verify_convergence.py — converter fixed-point convergence over every hub
state x converter law x current limit x fault (33-bus, hosting-feasible hubs).
Writes results/verify_convergence.json"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES, FIGS, TEX, SRC
import sys, json, itertools, time, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grid import Network, FaultModel
from params import FAULT_SET, CONVERTER
H = json.load(open(RES + '/hosting_33.json'))
hubs = {int(b): v for b, v in H['P_MW'].items()}
net = Network('33', hubs=hubs)
bad = tot = 0; its = []; t0 = time.time()
for st in itertools.product(('off', 'chg', 'exp'), repeat=len(hubs)):
    hs = dict(zip(hubs, st))
    for mode in ('P', 'Q', 'MC'):
        for kf in (1.0, 1.2, 2.0):
            c = dict(CONVERTER); c.update(mode=mode, kf=kf)
            fm = FaultModel(net, 1.0, hs, conv=c); topo = fm.topology()
            for F in range(1, net.n):
                for ft, Rs in FAULT_SET.items():
                    for Rf in Rs:
                        r = fm.solve(topo, F, ft, Rf); tot += 1; its.append(r['iters'])
                        bad += (not r['converged'])
# how the case count arises: fault nodes (every bus except the source, plus each hub
# terminal; no mid-section faults) x fault variants x hub-state combinations (load
# scale 1.0) x control laws x current limits
n_hub = len(hubs); n_nodes = net.n - 1
design = dict(fault_nodes=n_nodes, bus_nodes=n_nodes - n_hub, hub_terminals=n_hub,
              fault_variants=sum(len(v) for v in FAULT_SET.values()), hub_state_combinations=3**n_hub,
              control_laws=3, current_limits=[1.0, 1.2, 2.0], load_scale=1.0)
assert tot == design['fault_nodes']*design['fault_variants']*design['hub_state_combinations']*3*3
out = dict(cases=tot, non_converged=bad, max_iter=int(max(its)), mean_iter=float(np.mean(its)),
           seconds=time.time() - t0, design=design)
json.dump(out, open(RES + '/verify_convergence.json', 'w'), indent=1)
print(out)
