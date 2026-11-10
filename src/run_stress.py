"""run_stress.py — is the robust fixed design robust to what it was not
designed for?  The base-case robust settings are frozen and re-evaluated on
fault datasets rebuilt under different converter laws, current limits, grid
strength, source X/R and line zero-sequence ratio; each variant is also
redesigned to see whether a robust design remains possible there.
usage: python run_stress.py 33   -> results/stress_<feeder>.json
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES, FIGS, TEX, SRC
import sys, json, pickle, numpy as np
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cases import build
import settings as S
import policies as P
from params import CONVERTER, CT_ALF

name = sys.argv[1] if len(sys.argv) > 1 else '33'
ds0 = pickle.load(open(RES + f'/ds_{name}_base.pkl', 'rb'))
H = json.load(open(RES + f'/hosting_{name}.json'))
hubs = {int(b): v for b, v in H['P_MW'].items()}
D0 = P.Designer(ds0); rob0 = D0.design(list(range(len(ds0['scen']))))
nS = len(ds0['scen'])
def conv(**kw):
    c = dict(CONVERTER); c.update(kw); return c
variants = {
    'mode Q (reactive priority)': dict(conv=conv(mode='Q')),
    'mode MC (momentary cessation)': dict(conv=conv(mode='MC')),
    'k_f = 1.0': dict(conv=conv(kf=1.0)),
    'k_f = 1.5': dict(conv=conv(kf=1.5)),
    'k_f = 2.0': dict(conv=conv(kf=2.0)),
    'k_f = 2.0, mode Q': dict(conv=conv(kf=2.0, mode='Q')),
    'S_sc = 50 MVA': dict(ssc=50.0),
    'S_sc = 250 MVA': dict(ssc=250.0),
    'source X/R = 5': dict(xr=5.0),
    'line Z0/Z1 = 2': dict(z0r=2.0),
    'line Z0/Z1 = 4': dict(z0r=4.0),
}
def plateau_share(ds, st):
    """share of fault cases in which the primary relay's phase or earth current is
    on the definite-time part of the curve (at least Mmax times its pickup)"""
    from params import CURVE
    own = np.asarray(ds['owner']); L = np.arange(len(own))
    MP = ds['Iph'][:, L, :, own]/st['IsP'][own][:, None, None]     # advanced index -> (nL, nS, nT)
    MN = ds['I3o'][:, L, :, own]/st['IsN'][own][:, None, None]
    return float(((MP >= CURVE['Mmax']) | (MN >= CURVE['Mmax'])).mean())

out = dict(feeder=name, variants={}, base_plateau_share=plateau_share(ds0, rob0['st']),
           base_ct=dict(zip(ds0['lay'].names, D0.ct.tolist())), base_IsN=dict(zip(ds0['lay'].names, rob0['st']['IsN'].tolist())))
for vname, kw in variants.items():
    ds = build(name, hubs, **kw)
    o, tP, m = S.evaluate(ds, list(range(nS)), lambda s: (rob0['st'], rob0['tp'], rob0['tn']))
    fin = np.isfinite(tP)
    frozen = dict(outcomes={int(k): int(v) for k, v in Counter(o.ravel().tolist()).items()},
                  all_selective=bool((o == 0).all()), mean_t=float(tP[fin].mean()),
                  short_margin=int((o == 1).sum()), min_margin=float(np.min(m[np.isfinite(m)])))
    D = P.Designer(ds)
    red = P.assess(D, P.policy_robust(ds), 'robust_redesigned')
    ps = P.assess(D, P.policy_per_state(ds), 'per_state')
    # frozen CTs driven beyond their accuracy-limit factor by the variant's largest fault current
    over = ds['Iph'].max(axis=(0, 1, 2))/D0.ct
    frozen['ct_beyond_alf'] = [r for r, x in zip(ds['lay'].names, over) if x > CT_ALF + 1e-9]
    frozen['max_current_over_ct'] = float(over.max())
    out['variants'][vname] = dict(frozen=frozen, redesigned={k: red.get(k) for k in
                                  ('feasible', 'all_selective', 'mean_t', 'max_t')},
                                  redesigned_plateau_share=plateau_share(ds, D.design(list(range(nS)))['st']),
                                  redesigned_ct=dict(zip(ds['lay'].names, D.ct.tolist())),
                                  redesigned_IsN=dict(zip(ds['lay'].names, D.design(list(range(nS)))['st']['IsN'].tolist())),
                                  per_state_mean_t=ps.get('mean_t'), per_state_feasible=ps.get('feasible'),
                                  per_state_all_selective=ps.get('all_selective'), conv_fail=ds['conv_fail'])
    print(f'{vname:32s} frozen: {frozen["outcomes"]}  mean_t {frozen["mean_t"]:.4f} | '
          f'redesign feasible {red.get("feasible")} mean_t {red.get("mean_t")} | per-state {ps.get("mean_t")}', flush=True)
json.dump(out, open(RES + f'/stress_{name}.json', 'w'), indent=1, default=float)
print('saved')
