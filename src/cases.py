"""cases.py — protection layout and the full fault-case dataset.

For a configuration (feeder, hubs, converter law, grid strength) this
enumerates every allowed hub-state scenario at both load levels and every
fault (location x type x resistance), solves it with grid.FaultModel and
stores what each relay measures:
    Iph   max phase-current magnitude through the relay branch (A)
    I3o   residual current |3 I0| (A)
    dP    phase directional decision (+1 forward, -1 reverse, 0 none)
    dN    earth directional decision
plus prefault load currents per relay (for pickups), LV through-fault
currents (for 50-element reach) and zone bookkeeping.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES, FIGS, TEX, SRC
import sys, itertools, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grid import Network, FaultModel, phase_currents
from params import (VPH, VLL, LOAD_LEVELS, ALLOWED_STATES, FAULT_SET, CONVERTER,
                    DT_STD_KVA, dt_impedance_pct)

# ------------------------------------------------------------ layouts
LAYOUTS = {
    # utility-style scheme: feeder breaker, two trunk reclosers, three lateral
    # reclosers (+ one breaker per hub, added automatically)               [A]
    '33': dict(relays={'R1': (1, 2), 'R2': (3, 4), 'R3': (6, 7),
                       'L1': (2, 19), 'L2': (3, 23), 'L3': (6, 26)}),
    '69': dict(relays={'R1': (1, 2), 'R2': (9, 10), 'R3': (12, 13),
                       'L1': (3, 28), 'L2': (3, 36), 'L3': (4, 47), 'L4': (9, 53)}),
}
RCA1, RCA2, RCA0 = np.deg2rad(45), np.deg2rad(60), np.deg2rad(60)   # [A] directional angles


class Layout:
    def __init__(self, net, name):
        self.net = net
        rel = dict(LAYOUTS[name]['relays'])
        self.names, self.branch = [], []
        for r, (f, t) in rel.items():
            k = [k for k in range(len(net.f)) if net.f[k] == f - 1 and net.t[k] == t - 1][0]
            self.names.append(r); self.branch.append(k)
        for b, h in net.hubs.items():                       # hub interface relays
            self.names.append(f'H{b}'); self.branch.append(h['branch'])
        self.branch = np.array(self.branch); self.nr = len(self.names)
        # zones: subtree of relay's to-node minus subtrees of downstream relays
        to = {r: net.t[k] for r, k in zip(self.names, self.branch)}
        self.zone = {}
        for r in self.names:
            sub = set(net.subtree(to[r]))
            for q in self.names:
                if q != r and to[q] in sub:
                    sub -= set(net.subtree(to[q]))
            self.zone[r] = sorted(sub)
        self.owner = {}
        for r, nodes in self.zone.items():
            for u in nodes: self.owner[u] = r
        # backup: nearest relay upstream of a relay's location
        self.backup = {}
        for r, k in zip(self.names, self.branch):
            u = net.f[k]
            self.backup[r] = self.owner.get(u)               # None for R1
        self.on_path = {}                                    # relays upstream of node u
        for u in range(net.n):
            path = set(net.path_to_root(u))
            self.on_path[u] = [i for i, k in enumerate(self.branch)
                               if net.t[k] in path]


def fault_locations(net):
    """(label, node, at_branch, x): every bus, every hub node, mid-point of
    every feeder branch (hub cables excluded)."""
    locs = [(str(net.labels[u]), u, None, None) for u in range(1, net.n)]
    hubbranches = {h['branch'] for h in net.hubs.values()}
    for k in range(len(net.f)):
        if k in hubbranches: continue
        locs.append((f'{net.labels[net.f[k]]}-{net.labels[net.t[k]]}m', net.t[k], k, 0.5))
    return locs


def scenarios(hub_buses):
    out = []
    for lvl in LOAD_LEVELS:
        for st in itertools.product(ALLOWED_STATES[lvl], repeat=len(hub_buses)):
            out.append((lvl, dict(zip(hub_buses, st))))
    return out


def _direction(I1, I2, V1pre, V1, V2, ftype):
    """phase directional: positive-sequence memory-polarised for 3ph faults,
    negative-sequence for unbalanced faults (fallback to positive)."""
    if ftype != '3ph' and abs(I2) > 1.0:
        z2 = V2/I2
        return 1 if (z2*np.exp(-1j*RCA2)).real < 0 else -1
    if abs(I1) < 1e-6: return 0
    return 1 if np.cos(np.angle(I1) - np.angle(V1pre) + RCA1) > 0 else -1


def build(name, hubs_MW, conv=None, ssc=None, xr=None, z0r=None, scen=None, lv=True, verbose=False):
    conv = dict(CONVERTER if conv is None else conv)
    net = Network(name, hubs=hubs_MW, ssc=ssc, xr=xr, z0r=z0r)
    lay = Layout(net, name)
    hub_buses = tuple(sorted(net.hubs))
    scen = scenarios(hub_buses) if scen is None else scen
    locs = fault_locations(net)
    ftypes = [(ft, Rf) for ft, Rs in FAULT_SET.items() for Rf in Rs]
    # distribution transformers for LV through-faults (one unit per load bus)
    dts = []
    for u in range(1, net.n):
        S = abs(net.SL[u])
        if S <= 0: continue
        kva = next(k for k in DT_STD_KVA if k*1e3 >= 1.25*S)
        z = dt_impedance_pct(kva)/100*VLL**2/(kva*1e3)
        dts.append((u, kva, complex(z/np.sqrt(1 + 25), z*5/np.sqrt(1 + 25))))     # X/R = 5 [A]
    for b, h in net.hubs.items():
        kva = next(k for k in DT_STD_KVA if k*1e3 >= h['P']/0.95)
        z = dt_impedance_pct(kva)/100*VLL**2/(kva*1e3)
        h['tx_kva'] = kva; h['Ztx'] = complex(z/np.sqrt(26), z*5/np.sqrt(26))
    nS, nL, nT, nR = len(scen), len(locs), len(ftypes), lay.nr
    Iph = np.zeros((nS, nL, nT, nR)); I3o = np.zeros_like(Iph)
    dP = np.zeros((nS, nL, nT, nR), np.int8); dN = np.zeros_like(dP)
    Vh = np.zeros((nS, nL, nT, max(1, len(hub_buses))))       # hub terminal |V1| pu
    Iload = np.zeros((nS, nR), complex)                       # prefault relay currents
    Pflow = np.zeros((nS, nR))                                # prefault real power f->t (W/ph)
    LV = np.zeros((nS, len(dts) + len(net.hubs), nR))         # LV through-fault |I|
    LVdir = np.zeros_like(LV, dtype=np.int8)
    conv_fail = 0
    Iload_g = np.zeros((nS, nR), complex); Pflow_g = np.zeros((nS, nR))   # gross load:
    cls_key = []                                    # exporting hubs counted as off
    for s, (lvl, hs) in enumerate(scen):
        fm = FaultModel(net, LOAD_LEVELS[lvl], hs, conv=conv)
        Iload[s] = fm.Ipre[lay.branch]
        Pflow[s] = (fm.Vpre[net.f[lay.branch]]*np.conj(fm.Ipre[lay.branch])).real
        gross = {b: ('off' if v == 'exp' else v) for b, v in hs.items()}
        lfg = net.load_flow(LOAD_LEVELS[lvl], gross)
        Iload_g[s] = lfg['Ibr'][lay.branch]
        Pflow_g[s] = (lfg['V'][net.f[lay.branch]]*np.conj(lfg['Ibr'][lay.branch])).real
        cls_key.append((lvl, tuple(sorted(gross.items()))))
        topo0 = fm.topology()
        Vpre_rel = fm.Vpre[net.f[lay.branch]]
        cache = {None: topo0}
        for l, (lab, node, kb, x) in enumerate(locs):
            if kb is None: topo, F = topo0, node
            else:
                topo = fm.topology(kb, x); F = net.n
            for ti, (ft, Rf) in enumerate(ftypes):
                r = fm.solve(topo, F, ft, Rf)
                conv_fail += (not r['converged'])
                # relay branch currents: relays sit at the from-end of their branch;
                # when the faulted branch is split, branch kb keeps the from-end segment
                I0b, I1b, I2b = r['I0b'][lay.branch], r['I1b'][lay.branch], r['I2b'][lay.branch]
                Ip = np.abs(phase_currents(I0b, I1b, I2b)).max(axis=0)
                Iph[s, l, ti] = Ip; I3o[s, l, ti] = np.abs(3*I0b)
                V1r = r['V1'][net.f[lay.branch]]; V2r = r['V2'][net.f[lay.branch]]
                V0r = r['V0'][net.f[lay.branch]]
                for i in range(nR):
                    dP[s, l, ti, i] = _direction(I1b[i], I2b[i], Vpre_rel[i], V1r[i], V2r[i], ft)
                    if abs(I0b[i]) > 1e-3:
                        z0 = V0r[i]/I0b[i]
                        dN[s, l, ti, i] = 1 if (z0*np.exp(-1j*RCA0)).real < 0 else -1
                for j, b in enumerate(hub_buses):
                    Vh[s, l, ti, j] = abs(r['V1'][net.hubs[b]['node']])/VPH
        if lv:   # LV-side three-phase through-faults (transformer impedance as fault impedance)
            items = [(u, Z) for (u, kva, Z) in dts] + [(h['node'], h['Ztx']) for h in net.hubs.values()]
            for j, (u, Z) in enumerate(items):
                r = fm.solve(topo0, u, '3ph', Z)
                I1b = r['I1b'][lay.branch]
                LV[s, j] = np.abs(I1b)
                LVdir[s, j] = [_direction(I1b[i], 0j, Vpre_rel[i], 0, 0, '3ph') for i in range(nR)]
        if verbose: print(f'  scenario {s+1}/{nS} {lvl} {hs}', flush=True)
    # expected (topological) direction and zone owner per location
    owner = np.array([lay.names.index(lay.owner[node]) for (_, node, _, _) in locs])
    topo_fwd = np.zeros((nL, nR), np.int8)
    for l, (_, node, kb, x) in enumerate(locs):
        on = set(lay.on_path[node])
        if kb is not None and kb in set(lay.branch):        # fault on a relay's own branch
            on.add(list(lay.branch).index(kb))
        topo_fwd[l] = [1 if i in on else -1 for i in range(nR)]
    lv_nodes = [u for (u, kva, Z) in dts] + [h['node'] for h in net.hubs.values()]
    LVfwd = np.zeros((len(lv_nodes), nR), bool)
    for j, u in enumerate(lv_nodes):
        on = set(lay.on_path[u])
        LVfwd[j] = [i in on for i in range(nR)]
    keys = sorted(set(cls_key), key=lambda k: (k[0] != 'peak', k))
    cls = np.array([keys.index(k) for k in cls_key])
    return dict(name=name, net=net, lay=lay, scen=scen, locs=locs, ftypes=ftypes,
                Iph=Iph, I3o=I3o, dP=dP, dN=dN, Vh=Vh, Iload=Iload, Pflow=Pflow,
                Iload_g=Iload_g, Pflow_g=Pflow_g, cls=cls, cls_keys=keys,
                LV=LV, LVdir=LVdir, LVfwd=LVfwd, lv_nodes=lv_nodes,
                owner=owner, topo_fwd=topo_fwd, hub_buses=hub_buses, conv=conv,
                conv_fail=conv_fail, dts=dts)
