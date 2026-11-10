"""hosting.py — hub hosting capacity and the feasible hub configuration.
Feasibility: every allowed hub-state combination at both load levels keeps
V >= VMIN_PU, V <= VMAX_PU and branch current <= AMPACITY_A.
Outputs results/hosting_<feeder>.json (single-hub limits, joint optimum,
hub ratings, rated and limited fault currents, local grid fault level)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES, FIGS, TEX, SRC
import sys, json, itertools, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grid import Network, FaultModel
from params import (VPH, VLL, VMIN_PU, VMAX_PU, AMPACITY_A, LOAD_LEVELS, CHARGER_KW,
                    ALLOWED_STATES, HUB_BUSES, CONVERTER)

def worst(name, P, regime):
    net = Network(name, hubs=P); w = dict(vmin=9.0, vmax=0.0, imax=0.0)
    nb = len(net.bench) and sum(1 for l in net.labels if isinstance(l, int))
    for lvl, sc in LOAD_LEVELS.items():
        for st in itertools.product(regime[lvl], repeat=len(P)):
            lf = net.load_flow(sc, dict(zip(P, st)))
            v = np.abs(lf['V'][:nb])/VPH
            w['vmin'] = min(w['vmin'], float(v.min())); w['vmax'] = max(w['vmax'], float(v.max()))
            w['imax'] = max(w['imax'], float(np.abs(lf['Ibr']).max()))
    w['ok'] = w['vmin'] >= VMIN_PU and w['vmax'] <= VMAX_PU and w['imax'] <= AMPACITY_A
    return w

def single_limit(name, b, regime, nmax=60):
    n = 0
    while n < nmax and worst(name, {b: (n + 1)*CHARGER_KW/1e3}, regime)['ok']: n += 1
    return n

def run(name, buses):
    unmanaged = {'peak': ('off', 'chg', 'exp'), 'light': ('off', 'chg', 'exp')}
    nbus = len(Network(name).labels)
    single = {b: dict(unmanaged=single_limit(name, b, unmanaged),
                      managed=single_limit(name, b, ALLOWED_STATES)) for b in range(2, nbus + 1)}
    rng = [range(1, single[b]['managed'] + 1) for b in buses]
    best = None
    for ns in itertools.product(*rng):
        w = worst(name, {b: n*CHARGER_KW/1e3 for b, n in zip(buses, ns)}, ALLOWED_STATES)
        if w['ok'] and (best is None or sum(ns) > best[0] or (sum(ns) == best[0] and min(ns) > min(best[1]))):
            best = (sum(ns), ns, w)
    ns = best[1]; P = {b: n*CHARGER_KW/1e3 for b, n in zip(buses, ns)}
    # local grid fault level (bolted 3ph, hubs off, peak) and hub contribution ratio
    net = Network(name, hubs=P); fm = FaultModel(net, 1.0, {}); topo = fm.topology()
    hubinfo = {}
    for b in buses:
        F = net.idx(b); r = fm.solve(topo, F, '3ph', 0.0)
        Isc = abs(r['IF'][1]); Ir = net.hubs[b]['Irated']
        # first-order check of eq. (rho): the hub's own voltage effect (alone, light load,
        # off -> charging) and the angle of the Thevenin impedance at its bus (unity pf)
        v0 = abs(net.load_flow(LOAD_LEVELS['light'], {})['V'][F])
        v1 = abs(net.load_flow(LOAD_LEVELS['light'], {b: 'chg'})['V'][F])
        dv = (v0 - v1)/v0; cth = float(np.cos(np.angle(topo['Z1'][F, F])))
        hubinfo[b] = dict(chargers=int(dict(zip(buses, ns))[b]), P_MW=P[b], Irated_A=Ir,
                          Ilim_A=CONVERTER['kf']*Ir, Isc_local_A=Isc,
                          ratio=CONVERTER['kf']*Ir/Isc, S_over_Ssc=P[b]*1e6/(np.sqrt(3)*VLL*Isc),
                          dv=float(dv), cos_theta=cth, rho_pred=float(CONVERTER['kf']*dv/cth))
    return dict(feeder=name, criteria=dict(VMIN=VMIN_PU, VMAX=VMAX_PU, AMP=AMPACITY_A,
                                           regime={k: list(v) for k, v in ALLOWED_STATES.items()}),
                single=single, buses=list(buses), chargers=list(ns), P_MW=P,
                total_MW=sum(P.values()), worst=best[2], hubs=hubinfo)

if __name__ == '__main__':
    name = sys.argv[1] if len(sys.argv) > 1 else '33'
    buses = tuple(int(x) for x in sys.argv[2].split(',')) if len(sys.argv) > 2 else HUB_BUSES[name]
    res = run(name, buses)
    json.dump(res, open(RES + f'/hosting_{name}.json', 'w'), indent=1, default=float)
    print(json.dumps({k: res[k] for k in ('buses', 'chargers', 'P_MW', 'total_MW', 'worst')}, default=float))
    for b, h in res['hubs'].items():
        print(f"  hub {b}: {h['P_MW']:.2f} MW, Ir {h['Irated_A']:.1f} A, kf*Ir {h['Ilim_A']:.1f} A, "
              f"local Isc {h['Isc_local_A']:.0f} A -> contribution {100*h['ratio']:.1f}% ; S/Ssc {100*h['S_over_Ssc']:.2f}%")
