"""run_policies.py — base-case policy comparison on one feeder.
usage: python run_policies.py 33
Writes results/policies_<feeder>.json and results/ds_<feeder>_base.pkl
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES, FIGS, TEX, SRC
import sys, json, pickle, time, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cases import build
import settings as S
import policies as P

name = sys.argv[1] if len(sys.argv) > 1 else '33'
H = json.load(open(RES + f'/hosting_{name}.json'))
hubs = {int(b): v for b, v in H['P_MW'].items()}
t0 = time.time()
ds = build(name, hubs)
print(f'dataset: {len(ds["scen"])} scenarios x {len(ds["locs"])} locations x {len(ds["ftypes"])} '
      f'fault variants = {len(ds["scen"])*len(ds["locs"])*len(ds["ftypes"])} cases '
      f'({time.time()-t0:.1f}s, converter non-convergence {ds["conv_fail"]})', flush=True)
pickle.dump(ds, open(RES + f'/ds_{name}_base.pkl', 'wb'))
D = P.Designer(ds); lay = ds['lay']; out = dict(feeder=name, hubs=hubs, relays=lay.names,
                                                 backup=lay.backup, ct=dict(zip(lay.names, D.ct.tolist())))
nS = len(ds['scen'])
out['n_cases'] = nS*len(ds['locs'])*len(ds['ftypes'])
out['classes'] = [str(k) for k in ds['cls_keys']]

# ---- robust (fixed) and its settings table
rob = P.policy_robust(ds); out['robust'] = P.assess(D, rob, 'robust')
d = D.design(rob[0])
out['robust_settings'] = {r: dict(CT=float(D.ct[i]), IsP=float(d['st']['IsP'][i]), TMSP=float(d['tp'][i]),
                                  I50P=(None if d['st']['I50P'][i] > 1e11 else float(d['st']['I50P'][i])),
                                  IsN=float(d['st']['IsN'][i]), TMSN=float(d['tn'][i]),
                                  I50N=(None if d['st']['I50N'][i] > 1e11 else float(d['st']['I50N'][i])))
                          for i, r in enumerate(lay.names)}
out['robust_grading'] = {k: (v if not isinstance(v, np.generic) else float(v)) for k, v in d['info'].items()
                         if k in ('nrows', 'nrows_kept', 'struct_viol', 'sens_fail', 'ncase', 'gap', 'status', 'objective', 'method')}
print('robust:', {k: out['robust'][k] for k in ('feasible', 'all_selective', 'mean_t', 'max_t', 'min_margin')}, flush=True)

# ---- anatomy of the fixed design: slowest clearances, element that clears, slack of
#      relays that are neither primary nor designated backup, backups that never operate
owner = ds['owner']; fwd = ds['topo_fwd']; slow = []; minslack = np.inf; nob = 0; nbk = 0
elem = {'51P': 0, '51N': 0, '50': 0}; mincase = None
from params import CURVE
def _elem(row, kP, kN, o50, s, l, t, r):
    """operating element of relay r and its current as a multiple of pickup"""
    if o50[l, t, r] and row[r] <= S.T50 + 1e-12: return '50', None
    if kP[l, t, r]*d['tp'][r] <= kN[l, t, r]*d['tn'][r]: return '51P', float(ds['Iph'][s, l, t, r]/d['st']['IsP'][r])
    return '51N', float(ds['I3o'][s, l, t, r]/d['st']['IsN'][r])
for s in range(nS):
    T = S.operate_times(ds, s, d['st'], d['tp'], d['tn'])
    kP, kN, o50 = S._elem_coeffs(ds, s, d['st'])
    for l in range(len(ds['locs'])):
        p = owner[l]; bn = lay.backup[lay.names[p]]; b = lay.names.index(bn) if bn else None
        for t in range(len(ds['ftypes'])):
            row = T[l, t]; tp = row[p]
            if not np.isfinite(tp): continue
            e = '50' if (o50[l, t, p] and tp <= S.T50 + 1e-12) else ('51P' if kP[l, t, p]*d['tp'][p] <= kN[l, t, p]*d['tn'][p] else '51N')
            elem[e] += 1
            slow.append((float(tp), s, l, t, p, e))
            if b is not None:
                nbk += 1; nob += not np.isfinite(row[b])
            for q in range(lay.nr):
                if q in (p, b) or not np.isfinite(row[q]) or fwd[l, q] != 1: continue
                sl = row[q] - ((1 + S.E_MARG)*tp + S.C_MARG)
                if sl < minslack - 1e-12:
                    minslack = sl; mincase = (s, l, t, p, q, row.copy(), kP, kN, o50)
# the case that sets the smallest slack of an off-path relay: which relays, which elements,
# and whether both operate on the definite-time part of the curve (M >= Mmax)
s, l, t, p, q, row, kP, kN, o50 = mincase
ep, Mp = _elem(row, kP, kN, o50, s, l, t, p); eq, Mq = _elem(row, kP, kN, o50, s, l, t, q)
tms = lambda r, e: None if e == '50' else float(d['tp'][r] if e == '51P' else d['tn'][r])
minslack_case = dict(level=ds['scen'][s][0], loc=str(ds['locs'][l][0]), ftype=ds['ftypes'][t][0],
                     Rf=float(ds['ftypes'][t][1]), primary=lay.names[p], primary_element=ep, primary_M=Mp,
                     primary_t=float(row[p]), primary_TMS=tms(p, ep), other=lay.names[q], other_element=eq,
                     other_M=Mq, other_t=float(row[q]), other_TMS=tms(q, eq),
                     definite_time_both=bool(Mp is not None and Mq is not None and Mp >= CURVE['Mmax'] and Mq >= CURVE['Mmax']))
slow.sort(reverse=True)
out['robust_anatomy'] = dict(
    clearing_element=elem, other_onpath_min_slack_s=float(minslack), other_onpath_min_slack_case=minslack_case,
    cases_with_backup=nbk, backup_never_operates=nob,
    slowest=[dict(t=x[0], level=ds['scen'][x[1]][0], loc=str(ds['locs'][x[2]][0]), ftype=ds['ftypes'][x[3]][0],
                  Rf=float(ds['ftypes'][x[3]][1]), relay=lay.names[x[4]], element=x[5],
                  TMS=float(d['tp'][x[4]] if x[5] == '51P' else d['tn'][x[4]])) for x in slow[:3]])
print('fixed-design anatomy:', out['robust_anatomy'], flush=True)

# ---- legacy: designed ignoring hubs, evaluated with hubs
leg = D.design(P.policy_legacy_ids(ds))
o, tP, m = S.evaluate(ds, list(range(nS)), lambda s: (leg['st'], leg['tp'], leg['tn']))
from collections import Counter
out['legacy'] = dict(outcomes={int(k): int(v) for k, v in Counter(o.ravel().tolist()).items()},
                     load_encroach=P.load_encroachment(ds, leg['st'], range(nS)))
who = Counter()
for s in range(nS):
    T = S.operate_times(ds, s, leg['st'], leg['tp'], leg['tn']); q = T.argmin(axis=2); tf = T.min(axis=2)
    for l in range(T.shape[0]):
        for t in range(T.shape[1]):
            if np.isfinite(tf[l, t]) and fwd[l, q[l, t]] != 1: who[lay.names[q[l, t]]] += 1
out['legacy']['false_trip_relays'] = dict(who)
out['legacy']['false_trip_relays_at_pickup_floor'] = all(
    abs(leg['st']['IsP'][lay.names.index(r)] - 0.10*D.ct[lay.names.index(r)]) < 1e-6 for r in who)
print('legacy:', out['legacy'], flush=True)

# ---- per-state bound
out['per_state'] = P.assess(D, P.policy_per_state(ds), 'per_state')
print('per-state:', {k: out['per_state'].get(k) for k in ('feasible', 'all_selective', 'mean_t')}, flush=True)

# ---- rule-based policies
hb = ds['hub_buses']; big = max(hb, key=lambda b: hubs[b])
rules = {
    'TOD': lambda lvl, hs: lvl,
    'CHG': lambda lvl, hs: any(v == 'chg' for v in hs.values()),
    f'CHG{big}': lambda lvl, hs: hs[big] == 'chg',
    'TOD+CHG': lambda lvl, hs: (lvl, any(v == 'chg' for v in hs.values())),
    'EXP': lambda lvl, hs: any(v == 'exp' for v in hs.values()),
}
out['rules'] = {}
for k, f in rules.items():
    pol = P.policy_by(ds, f); a = P.assess(D, pol, k); a['wrong_group'] = P.wrong_group(D, pol)
    out['rules'][k] = a
    print('rule', k, {x: a.get(x) for x in ('K', 'all_selective', 'mean_t')}, 'wrong-group', a['wrong_group']['total'],
          'enc', a['wrong_group']['encroach_total'], flush=True)

# ---- clustering
X = P.signatures(ds)
scan = P.cluster_scan(X)
out['cluster_scan'] = {f'{m}_K{K}': {k: v for k, v in r.items()} for (m, K), r in scan.items()}
best_key = max(scan, key=lambda k: scan[k]['silhouette'])
out['cluster'] = {}
for key in sorted(set([best_key, ('kmeans', 2), ('ward', 2), ('kmeans', 3), ('kmeans', 4)])):
    lab = scan[key]['labels']; pol = P.labels_to_groups(lab)
    a = P.assess(D, pol, f'{key[0]}_K{key[1]}')
    a['silhouette'] = scan[key]['silhouette']; a['db'] = scan[key]['db']; a['ch'] = scan[key]['ch']
    a['stability_ari_mean'], a['stability_ari_p5'] = P.cluster_stability(X, lab, key[1], key[0])
    a['wrong_group'] = P.wrong_group(D, pol)
    # does the cluster partition coincide with a simple physical rule?
    a['matches_rules'] = [k for k, f in rules.items()
                          if P.adjusted_rand_score(lab, [str(f(l, h)) for (l, h) in ds['scen']]) > 0.999]
    out['cluster'][f'{key[0]}_K{key[1]}'] = a
    print('cluster', key, 'sil %.3f' % a['silhouette'], 'ARI %.2f' % a['stability_ari_mean'],
          'mean_t', a.get('mean_t'), 'matches', a['matches_rules'], flush=True)
out['cluster_best_by_silhouette'] = f'{best_key[0]}_K{best_key[1]}'

# ---- exhaustive certified best policy for each K (partitions of load classes)
t1 = time.time()
best, members = P.exhaustive_classes(D)
out['exhaustive'] = {}
for K, bk in best.items():
    if bk is None: out['exhaustive'][K] = None; continue
    a = P.assess(D, bk[2], f'best_K{K}')
    a['class_blocks'] = bk[1]
    if K > 1: a['wrong_group'] = P.wrong_group(D, bk[2])
    out['exhaustive'][K] = a
    print(f'best K={K}: mean_t {a.get("mean_t"):.4f}  blocks {bk[1]}', flush=True)
out['exhaustive_designs'] = len(D.cache); out['exhaustive_time_s'] = time.time() - t1
out['class_members'] = {int(c): v for c, v in members.items()}
json.dump(out, open(RES + f'/policies_{name}.json', 'w'), indent=1, default=float)
print('saved results/policies_%s.json  (%.0fs total)' % (name, time.time() - t0))
