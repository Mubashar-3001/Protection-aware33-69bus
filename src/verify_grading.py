"""verify_grading.py — checks the exact time-grading solver (tree DP).

 G1  with the one-designated-element convention, the dynamic programme returns
     the same TMS as the mixed-integer programme (HiGHS, zero gap) for every
     group designed in the study (fixed, per state, every union of load
     classes), on both feeders
 G2  on two-relay sub-trees with a coarse TMS grid, the dynamic programme
     matches brute-force enumeration of every setting combination, with
     clearing times taken straight from the relay model (fastest element)
 G3  from the fixed design and the best two-group design, no single TMS step
     lowers the mean clearing time while keeping every case selective
     with the margin met (necessary condition for optimality)
 G4  designs are scored by the evaluator; every own-group design is fully
     selective
 G5  fixed and per-state designs graded on one designated element (MILP) vs.
     exactly: mean clearing times and the apparent gain of adaptation
usage: python verify_grading.py -> results/verify_grading.json
"""
import os, sys, copy, json, pickle, itertools, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES
import numpy as np
import settings as S
import policies as P
from params import TMS_MIN

out = {}
t0 = time.time()


def class_groups(ds):
    C = int(ds['cls'].max()) + 1
    mem = {c: [s for s in range(len(ds['scen'])) if ds['cls'][s] == c] for c in range(C)}
    for r in range(1, C + 1):
        for sub in itertools.combinations(range(C), r):
            yield sum((mem[c] for c in sub), [])


# ---------------------------------------------------------------- G1, G4
for name in ('33', '69'):
    ds = pickle.load(open(RES + f'/ds_{name}_base.pkl', 'rb'))
    ct = S.fixed_hardware(ds); nS = len(ds['scen'])
    groups = list(class_groups(ds)) + [[s] for s in range(nS)]
    same = 0; worst = 0.0; n = 0; not_sel = 0
    for G in groups:
        st = S.group_settings(ds, G, ct)
        tm, nm, im = S.coordinate_milp(ds, G, st, ct)
        td, nd, idd = S.coordinate(ds, G, st, ct, designated=True)
        n += 1
        if im['feasible'] and idd['feasible']:
            same += bool(np.allclose(tm, td) and np.allclose(nm, nd))
            o1, t1, _ = S.evaluate(ds, G, lambda s: (st, tm, nm)); o2, t2, _ = S.evaluate(ds, G, lambda s: (st, td, nd))
            worst = max(worst, abs(t1[np.isfinite(t1)].sum() - t2[np.isfinite(t2)].sum()))
        else:
            same += (im['feasible'] == idd['feasible'])
        tf, nf, iff = S.coordinate(ds, G, st, ct)
        o, _, _ = S.evaluate(ds, G, lambda s: (st, tf, nf)); not_sel += int(not (o == 0).all())
    out[f'G1_{name}'] = dict(designs=n, identical_TMS=same, max_abs_diff_sum_t=worst)
    out[f'G4_{name}'] = dict(designs=n, not_fully_selective=not_sel)
    print('G1', name, out[f'G1_{name}'], ' G4', out[f'G4_{name}'], flush=True)

# ---------------------------------------------------------------- G2 brute force
ds = pickle.load(open(RES + '/ds_33_base.pkl', 'rb'))
ct = S.fixed_hardware(ds); nS = len(ds['scen']); G = list(range(nS))
st = S.group_settings(ds, G, ct)
orig = dict(TMS_STEP=S.TMS_STEP, NSTEP=S.NSTEP, X_GRID=S.X_GRID, NG=S.NG, _TIE=S._TIE)
step = 0.05; ng = int(round((1.0 - TMS_MIN)/step)) + 1
S.TMS_STEP, S.NSTEP, S.X_GRID, S.NG = step, ng - 1, TMS_MIN + step*np.arange(ng), ng
S._TIE = 1e-9*(np.arange(ng)[:, None] + np.arange(ng)[None, :])
lay = ds['lay']; owner = ds['owner']
K = [S._elem_coeffs(ds, s, st) for s in G]
from params import T50
E, Cm = S.E_MARG, S.C_MARG
g2 = {}
for root, child in (('L3', 'H30'), ('L2', 'H25')):
    q, c = lay.names.index(root), lay.names.index(child)
    ds2 = dict(ds); ds2['lay'] = copy.deepcopy(lay); ds2['lay'].backup = dict(lay.backup); ds2['lay'].backup[root] = None
    tp, tn, info = S.coordinate(ds2, G, st, ct)
    X = S.X_GRID
    def times(r, xp, xn):          # primary clearing time of relay r for every case in its zone
        ts = []
        for s in range(nS):
            kP, kN, o50 = K[s]; L = owner == r
            t = np.minimum(kP[L, :, r]*xp, kN[L, :, r]*xn); t = np.where(o50[L, :, r], np.minimum(t, T50), t)
            ts.append(t.ravel())
        return np.concatenate(ts)
    kb = []
    for s in range(nS):
        kP, kN, o50 = K[s]; L = owner == c
        kb.append(np.stack([kP[L, :, q].ravel(), kN[L, :, q].ravel(), o50[L, :, q].ravel()], 1))
    kb = np.concatenate(kb)
    best = (np.inf, None)
    tq = {(i, j): times(q, X[i], X[j]) for i in range(ng) for j in range(ng)}
    Bq = {k: v[np.isfinite(v)].sum() for k, v in tq.items()}
    for i in range(ng):
        for j in range(ng):
            t_c = times(c, X[i], X[j]); fin = np.isfinite(t_c); A = t_c[fin].sum()
            req = (1 + E)*t_c[fin] + Cm
            for a in range(ng):
                okP = np.all(~np.isfinite(kb[fin, 0]) | (kb[fin, 0]*X[a] >= req - 1e-9))
                if not okP: continue
                for b in range(ng):
                    okN = np.all(~np.isfinite(kb[fin, 1]) | (kb[fin, 1]*X[b] >= req - 1e-9))
                    if okN and A + Bq[(a, b)] < best[0] - 1e-12: best = (A + Bq[(a, b)], (i, j, a, b))
    tdp = times(c, tp[c], tn[c]); tqd = times(q, tp[q], tn[q])
    dp_val = tdp[np.isfinite(tdp)].sum() + tqd[np.isfinite(tqd)].sum()
    g2[f'{child}->{root}'] = dict(combinations=ng**4, brute_force_sum_t=float(best[0]), dp_sum_t=float(dp_val),
                                 rel_diff=float(abs(dp_val - best[0])/best[0]))
    print('G2', child, '->', root, g2[f'{child}->{root}'], flush=True)
out['G2'] = g2
for k, v in orig.items(): setattr(S, k, v)

# ---------------------------------------------------------------- G3 local optimality
g3 = {}
for name in ('33', '69'):
    ds = pickle.load(open(RES + f'/ds_{name}_base.pkl', 'rb'))
    D = P.Designer(ds); nS = len(ds['scen']); nr = ds['lay'].nr
    pol = json.load(open(RES + f'/policies_{name}.json'))
    for label, Gs in (('fixed', [list(range(nS))]), ('best_K2', pol['exhaustive']['2']['groups'])):
        improved = 0; tried = 0
        for Gg in Gs:
            d = D.design(Gg); st = d['st']; x = np.concatenate([d['tp'], d['tn']])
            def score(y):
                o, tP, m = S.evaluate(ds, Gg, lambda s: (st, y[:nr], y[nr:]))
                return bool((o == 0).all()), float(tP[np.isfinite(tP)].sum())
            ok0, f0 = score(x)
            for j in range(2*nr):
                for dl in (-S.TMS_STEP, S.TMS_STEP):
                    y = x.copy(); y[j] = round(y[j] + dl, 2)
                    if y[j] < S.TMS_MIN - 1e-9 or y[j] > S.TMS_MAX + 1e-9: continue
                    tried += 1; ok, f = score(y)
                    improved += bool(ok and f < f0 - 1e-9)
        g3[f'{name}_{label}'] = dict(neighbours_tried=tried, improving=improved)
        print('G3', name, label, g3[f'{name}_{label}'], flush=True)
out['G3'] = g3

# ---------------------------------------------------------------- G5 why exact grading matters
g5 = {}
for name in ('33', '69'):
    ds = pickle.load(open(RES + f'/ds_{name}_base.pkl', 'rb'))
    ct = S.fixed_hardware(ds); nS = len(ds['scen'])
    res = {}
    for label, Gs in (('fixed', [list(range(nS))]), ('per_state', [[s] for s in range(nS)])):
        for meth in ('designated', 'exact'):
            tot = 0.0; n = 0
            for G in Gs:
                st = S.group_settings(ds, G, ct)
                tp, tn, _ = (S.coordinate_milp(ds, G, st, ct) if meth == 'designated' else S.coordinate(ds, G, st, ct))
                o, tP, _ = S.evaluate(ds, G, lambda s: (st, tp, tn)); fin = np.isfinite(tP)
                tot += tP[fin].sum(); n += fin.sum()
            res[f'{label}_{meth}_mean_t'] = tot/n
    res['per_state_gain_designated_pct'] = 100*(1 - res['per_state_designated_mean_t']/res['fixed_designated_mean_t'])
    res['per_state_gain_exact_pct'] = 100*(1 - res['per_state_exact_mean_t']/res['fixed_exact_mean_t'])
    g5[name] = res
    print('G5', name, {k: round(v, 4) for k, v in res.items()}, flush=True)
out['G5'] = g5
out['seconds'] = time.time() - t0
json.dump(out, open(RES + '/verify_grading.json', 'w'), indent=1, default=float)
print('saved results/verify_grading.json')
