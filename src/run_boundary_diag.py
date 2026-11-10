"""run_boundary_diag.py — which faults does the fixed design miss beyond the
hosting limit, and could any setting change catch them?
For hub multiples m (100 MVA, k_f = 1.2): missed cases by fault type,
resistance, location and hub state; and whether each missed case would be
detected by the most sensitive pickup that the load of its own state allows.
usage: python run_boundary_diag.py -> results/boundary_diag.json"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES
import json, numpy as np
from collections import Counter
from cases import build
import settings as S
import policies as P
from params import CONVERTER

H = json.load(open(RES + '/hosting_33.json')); hubs0 = {int(b): v for b, v in H['P_MW'].items()}
out = {}
for m in (1.0, 2.0, 2.5, 3.0):
    hubs = {b: v*m for b, v in hubs0.items()}
    ds = build('33', hubs, conv=dict(CONVERTER), ssc=100.0)
    D = P.Designer(ds); nS = len(ds['scen']); rob = D.design(list(range(nS)))
    o, tP, mg = S.evaluate(ds, list(range(nS)), lambda s: (rob['st'], rob['tp'], rob['tn']))
    miss = np.argwhere(o == 4)
    by = Counter(); loc = Counter(); st = Counter(); own = 0; rel = Counter(); i3o = []
    lay = ds['lay']
    for s, l, t in miss:
        ft, Rf = ds['ftypes'][t]; by[f'{ft} {Rf:g} ohm'] += 1; loc[str(ds['locs'][l][0])] += 1
        p = ds['owner'][l]; rel[lay.names[p]] += 1
        if ft in ('SLG', 'LLG'): i3o.append(float(ds['I3o'][s, l, t, p]))
        lvl, hs = ds['scen'][s]; st[f"{lvl} " + ','.join(f'{b}:{v}' for b, v in hs.items())] += 1
        # most sensitive pickups this state's own load allows
        sto = S.group_settings(ds, [int(s)], D.ct)
        p = ds['owner'][l]
        seen = ds['Iph'][s, l, t, p] > sto['IsP'][p] or ds['I3o'][s, l, t, p] > sto['IsN'][p]
        own += bool(seen)
    ct = {r: float(D.ct[i]) for i, r in enumerate(lay.names)}
    out[str(m)] = dict(n_cases=int(o.size), missed=int(len(miss)), by_type=dict(by), by_location=dict(loc.most_common(8)),
                       by_state=dict(st.most_common(6)), detectable_with_own_state_pickups=int(own),
                       states_with_misses=len(st), by_relay=dict(rel), ct=ct,
                       earth_pickup={r: float(rob['st']['IsN'][i]) for i, r in enumerate(lay.names)},
                       max_3I0_missed=(max(i3o) if i3o else None))
    print(m, out[str(m)], flush=True)
json.dump(out, open(RES + '/boundary_diag.json', 'w'), indent=1)
