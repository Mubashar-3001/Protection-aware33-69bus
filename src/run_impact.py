"""run_impact.py — how much do hub states change what feeder relays see?
For every fault case the primary- and backup-relay currents in each hub
state are compared with the same case with all hubs off (same load level).
Also: reverse currents at relays for upstream faults (why the elements
must be directional) and hub terminal voltages during faults.
usage: python run_impact.py 33 -> results/impact_<feeder>.json
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES, FIGS, TEX, SRC
import sys, json, pickle, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import policies as P

name = sys.argv[1] if len(sys.argv) > 1 else '33'
ds = pickle.load(open(RES + f'/ds_{name}_base.pkl', 'rb'))
lay = ds['lay']; owner = ds['owner']; fwd = ds['topo_fwd']
D = P.Designer(ds); rob = D.design(list(range(len(ds['scen']))))
off = {lvl: [s for s, (l, hs) in enumerate(ds['scen']) if l == lvl and all(v == 'off' for v in hs.values())][0]
       for lvl in ('peak', 'light')}
ftypes = ds['ftypes']; out = dict(feeder=name, by_type={})
GROUND = ('SLG', 'LLG')
for ft in ('3ph', 'LL', 'SLG', 'LLG'):
    tids = [t for t, (f, R) in enumerate(ftypes) if f == ft]
    dP, dB = [], []
    for s, (lvl, hs) in enumerate(ds['scen']):
        if all(v == 'off' for v in hs.values()): continue
        s0 = off[lvl]
        for l in range(len(ds['locs'])):
            p = owner[l]; bn = lay.backup[lay.names[p]]
            for t in tids:
                X = ds['I3o'] if ft in GROUND else ds['Iph']
                a, a0 = X[s, l, t, p], X[s0, l, t, p]
                if a0 > 1: dP.append(a/a0 - 1)
                if bn:
                    b = lay.names.index(bn); c, c0 = X[s, l, t, b], X[s0, l, t, b]
                    if c0 > 1: dB.append(c/c0 - 1)
    dP, dB = np.array(dP), np.array(dB)
    out['by_type'][ft] = dict(quantity='3I0' if ft in GROUND else 'max phase',
                              primary_max_increase=float(dP.max()), primary_max_decrease=float(dP.min()),
                              primary_p95_abs=float(np.percentile(np.abs(dP), 95)),
                              backup_max_increase=float(dB.max()), backup_max_decrease=float(dB.min()),
                              backup_p95_abs=float(np.percentile(np.abs(dB), 95)))
    print(ft, {k: round(v, 4) for k, v in out['by_type'][ft].items() if isinstance(v, float)})
# reverse currents at relays for faults upstream of them, relative to robust pickup
rev = {}
for r, nm in enumerate(lay.names):
    m = 0.0
    for s in range(len(ds['scen'])):
        mask = fwd[:, r] == -1
        if mask.any():
            m = max(m, float(ds['Iph'][s][mask][..., r].max()))
    rev[nm] = dict(max_reverse_A=m, ratio_to_pickup=m/rob['st']['IsP'][r])
out['reverse'] = rev
print('reverse/pickup:', {k: round(v['ratio_to_pickup'], 2) for k, v in rev.items()})
# directional decisions vs topology where the current exceeds the robust pickup
bad = tot = 0
for s in range(len(ds['scen'])):
    above = ds['Iph'][s] > rob['st']['IsP'][None, None, :]
    exp = np.broadcast_to(fwd[:, None, :], above.shape)
    tot += int(above.sum()); bad += int((above & (ds['dP'][s] != exp)).sum())
out['directional'] = dict(cases_above_pickup=tot, disagreements=bad)
print('directional disagreements above pickup:', bad, 'of', tot)
# hub terminal voltage during faults (exporting hubs)
vh = []
for s, (lvl, hs) in enumerate(ds['scen']):
    for j, b in enumerate(ds['hub_buses']):
        if hs[b] == 'exp': vh.append(ds['Vh'][s, :, :, j].ravel())
vh = np.concatenate(vh)
out['hub_voltage'] = dict(frac_below_0p5=float((vh < 0.5).mean()), frac_below_0p2=float((vh < 0.2).mean()),
                          median=float(np.median(vh)))
print('hub terminal V during faults:', out['hub_voltage'])
json.dump(out, open(RES + f'/impact_{name}.json', 'w'), indent=1, default=float)
