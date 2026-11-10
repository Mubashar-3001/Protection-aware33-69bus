"""run_sweep.py — where does a single robust setting group stop working?
Sweeps hub size (multiple m of the hosting-feasible ratings), converter
current limit k_f and upstream fault level S_sc. For each point: voltage
feasibility of the hub operating envelope, robust design (certified),
per-state bound, certified best 2- and 4-group policies, and why the
robust design fails when it does.
usage: python run_sweep.py 33   -> results/sweep_<feeder>.json (incremental)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES, FIGS, TEX, SRC
import sys, json, itertools, time, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cases import build
from grid import Network
import settings as S
import policies as P
from params import CONVERTER, LOAD_LEVELS, ALLOWED_STATES, VPH

name = sys.argv[1] if len(sys.argv) > 1 else '33'
M = [float(x) for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else '0.5,1,1.5,2,2.5,3'.split(','))]
KF = (1.2, 2.0); SSC = (50.0, 100.0, 250.0)
H = json.load(open(RES + f'/hosting_{name}.json'))
hubs0 = {int(b): v for b, v in H['P_MW'].items()}
path = RES + f'/sweep_{name}.json'
done = json.load(open(path)) if os.path.exists(path) else {}

def vfeas(hubs, ssc):
    net = Network(name, hubs=hubs, ssc=ssc); vmin, vmax, ok = 9, 0, True
    nb = sum(1 for l in net.labels if isinstance(l, int))
    for lvl, sc in LOAD_LEVELS.items():
        for st in itertools.product(ALLOWED_STATES[lvl], repeat=len(hubs)):
            lf = net.load_flow(sc, dict(zip(hubs, st)), itmax=3000)
            v = np.abs(lf['V'][:nb])/VPH; ok &= bool(lf['converged'])
            vmin = min(vmin, float(v.min())); vmax = max(vmax, float(v.max()))
    return dict(converged=ok, vmin=vmin, vmax=vmax)

for m, kf, ssc in itertools.product(M, KF, SSC):
    key = f'm={m}|kf={kf}|ssc={ssc}'
    if key in done: continue
    t0 = time.time()
    hubs = {b: v*m for b, v in hubs0.items()}
    rec = dict(m=m, kf=kf, ssc=ssc, volt=vfeas(hubs, ssc))
    if not rec['volt']['converged']:
        rec['note'] = 'no load-flow solution'; done[key] = rec
        json.dump(done, open(path, 'w'), indent=1, default=float); continue
    c = dict(CONVERTER); c['kf'] = kf
    ds = build(name, hubs, conv=c, ssc=ssc)
    D = P.Designer(ds); nS = len(ds['scen'])
    # contribution ratio per hub: kf*Irated / local bolted 3ph grid fault current
    from grid import FaultModel
    fm0 = FaultModel(ds['net'], 1.0, {}); topo0 = fm0.topology()
    rec['rho'] = {b: kf*ds['net'].hubs[b]['Irated']/abs(fm0.solve(topo0, ds['net'].idx(b), '3ph', 0.0)['IF'][1])
                  for b in hubs}
    rob = P.assess(D, P.policy_robust(ds), 'robust')
    d = D.design(list(range(nS)))
    rec['robust'] = {k: rob.get(k) for k in ('feasible', 'all_selective', 'mean_t', 'max_t', 'outcomes',
                                               'sens_primary_P', 'sens_backup_P', 'sens_primary_N', 'sens_backup_N')}
    rec['robust']['grading'] = {k: d['info'].get(k) for k in ('feasible', 'struct_viol', 'sens_fail', 'nrows', 'nrows_kept')}
    ps = P.assess(D, P.policy_per_state(ds), 'per_state')
    rec['per_state'] = {k: ps.get(k) for k in ('feasible', 'all_selective', 'mean_t', 'infeasible_groups')}
    best, _ = P.exhaustive_classes(D, Kmax=4)
    rec['best'] = {K: (None if bk is None else dict(mean_t=P.assess(D, bk[2]).get('mean_t'), blocks=bk[1]))
                   for K, bk in best.items()}
    # why does robust fail?  sensitivity (primary does not see fault) vs grading
    rec['robust_diag'] = dict(sens_fail=d['info'].get('sens_fail'), struct_viol=d['info'].get('struct_viol'))
    rec['time_s'] = time.time() - t0
    done[key] = rec
    json.dump(done, open(path, 'w'), indent=1, default=float)
    print(key, 'V[%.3f,%.3f]' % (rec['volt']['vmin'], rec['volt']['vmax']),
          'robust', rob.get('feasible'), rob.get('all_selective'), 'mean_t', rob.get('mean_t'),
          '| per-state', ps.get('feasible'), ps.get('mean_t'),
          '| best2', rec['best'].get(2) and rec['best'][2]['mean_t'], '(%.0fs)' % rec['time_s'], flush=True)
print('sweep complete')
