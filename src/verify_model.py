"""verify_model.py — checks the network/fault model before any study uses it.

 V1  load flow reproduces the published IEEE 33/69-bus benchmarks
 V2  linearised fault network reproduces the prefault state exactly
     (study hub ratings, exporting and charging hubs)
 V3  phase-domain fault boundary conditions hold for every fault type
 V4  KCL holds at every node in all three sequence networks during faults
 V5  grid-only cross-check against pandapower (IEC 60909) on both feeders:
     3ph/2ph/1ph fault currents at every bus and 3ph branch currents
 V6  independent re-solve of the converter fixed point (own nodal model,
     own load flow, scipy fsolve) for faults with exporting hubs
Writes results/verify_model.json.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES, FIGS, TEX, SRC
import json, sys, numpy as np, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from params import VPH, VLL, LINE_Z0_OVER_Z1, SOURCE
from grid import Network, FaultModel, phase_currents, SEQ2PH

out = {}
# ---------------------------------------------------------------- V1
for name in ('33', '69'):
    net = Network(name)
    lf = net.load_flow(1.0, {})
    vpu = np.abs(lf['V'])/VPH
    i = int(np.argmin(vpu))
    out[f'V1_{name}'] = dict(loss_kW=round(lf['loss']/1e3, 2), vmin=round(float(vpu[i]), 4),
                             vmin_bus=net.labels[i], bench=net.bench,
                             ok=bool(abs(lf['loss']/1e3 - net.bench['loss_kW']) < 0.5 and
                                     net.labels[i] == net.bench['vmin_bus'] and
                                     abs(vpu[i] - net.bench['vmin']) < 5e-4))
    print('V1', name, out[f'V1_{name}'])

# ---------------------------------------------------------------- V2..V4
H = json.load(open(RES + '/hosting_33.json')); HUBS = {int(b): v for b, v in H['P_MW'].items()}
HS = {14: 'exp', 25: 'chg', 30: 'exp'}
net = Network('33', hubs=HUBS)
fm = FaultModel(net, 1.0, HS)
topo = fm.topology()
r = fm.solve(topo, F=5, ftype='none')
out['V2_prefault_mismatch_pu'] = float(np.max(np.abs(r['V1'] - fm.Vpre))/VPH)
print('V2 max |V(no-fault) - Vprefault| (pu):', out['V2_prefault_mismatch_pu'])

worst_bc, worst_kcl = 0.0, {'pos': 0.0, 'neg': 0.0, 'zero': 0.0}
for ftype, Rf in (('3ph', 0), ('3ph', 5), ('LL', 0), ('LL', 5), ('SLG', 0), ('SLG', 40), ('LLG', 0), ('LLG', 10)):
    for F in (2, 12, 17, 24, 29, net.hubs[14]['node'], net.hubs[30]['node']):
        r = fm.solve(topo, F, ftype, Rf)
        I0, I1, I2 = r['IF']; Ia, Ib_, Ic = SEQ2PH @ np.array([I0, I1, I2])
        Va, Vb, Vc = SEQ2PH @ np.array([r['V0'][F], r['V1'][F], r['V2'][F]])
        if ftype == '3ph': res = [Va - Rf*Ia, Vb - Rf*Ib_, Vc - Rf*Ic]
        if ftype == 'LL':  res = [Ia, Ib_ + Ic, (Vb - Vc) - Rf*Ib_]
        if ftype == 'SLG': res = [Ib_, Ic, Va - Rf*Ia]
        if ftype == 'LLG': res = [Ia, Vb - Vc, Vb - Rf*(Ib_ + Ic)]
        worst_bc = max(worst_bc, max(abs(x) for x in res)/VPH)
        # KCL at every node of each sequence network with explicit shunts and sources
        n = topo['n']; f, t = topo['f'], topo['t']
        for seq, Vn, Ibr, sh, Is, Ifl in (('pos', r['V1'], r['I1b'], fm.yL + fm.yH, net.Zs1, I1),
                                          ('neg', r['V2'], r['I2b'], fm.yL, net.Zs1, I2),
                                          ('zero', r['V0'], r['I0b'], 0*fm.yL, net.Zs0, I0)):
            bal = np.zeros(n, complex)
            np.add.at(bal, f, Ibr); np.add.at(bal, t, -Ibr)
            bal += sh*Vn; bal[0] += Vn[0]/Is; bal[F] += Ifl
            if seq == 'pos':
                bal[0] -= fm.E/net.Zs1
                for b, h in fm.src.items(): bal[h['node']] -= r['Ih'][b]
            worst_kcl[seq] = max(worst_kcl[seq], float(np.max(np.abs(bal))))
out['V3_boundary_residual_pu'] = worst_bc
out['V4_kcl_residual_A'] = worst_kcl
print('V3 worst boundary-condition residual (pu):', worst_bc)
print('V4 worst KCL residual per sequence network (A):', worst_kcl)

# ---------------------------------------------------------------- V5 pandapower
import pandapower as pp
import pandapower.shortcircuit as sc
from grid import feeder_data
warnings.filterwarnings('ignore')
C = 1.1
ssc, xr = SOURCE['Ssc_MVA'], SOURCE['XR']

def pp_net(name):
    BR, PL, QL, _ = feeder_data(name); nb = max(max(f, t) for f, t, _, _ in BR)
    pn = pp.create_empty_network(sn_mva=1.0)
    for b in range(1, nb + 1):
        pp.create_bus(pn, vn_kv=VLL/1e3, index=b - 1)
    pp.create_ext_grid(pn, 0, vm_pu=1.0, s_sc_max_mva=ssc, rx_max=1/xr, s_sc_min_mva=ssc, rx_min=1/xr,
                       x0x_max=SOURCE['Z0_over_Z1'], r0x0_max=1/xr, x0x_min=SOURCE['Z0_over_Z1'], r0x0_min=1/xr)
    for (f, t, r_, x_) in BR:
        pp.create_line_from_parameters(pn, f - 1, t - 1, length_km=1.0, r_ohm_per_km=r_, x_ohm_per_km=x_,
                                       c_nf_per_km=0.0, max_i_ka=1.0, r0_ohm_per_km=LINE_Z0_OVER_Z1*r_,
                                       x0_ohm_per_km=LINE_Z0_OVER_Z1*x_, c0_nf_per_km=0.0, endtemp_degree=80)
    return pn, nb

res = {}
for name, far in (('33', 18), ('69', 27)):
    # our IEC-mode model: |Zs| = c*VLL^2/Ssc, flat prefault c*VPH, no loads
    iec = Network(name, ssc=ssc/C)
    iec.SL[:] = 0
    fmi = FaultModel(iec, 0.0, {})
    fmi.E = C*VPH                                   # flat prefault
    topo_i = fmi.topology()
    for fault, ftype in (('3ph', '3ph'), ('2ph', 'LL'), ('1ph', 'SLG')):
        pn, nb = pp_net(name)
        sc.calc_sc(pn, fault=fault, case='max', branch_results=False, ip=False)
        errs = []
        for b in range(2, nb + 1):
            F = b - 1
            r = fmi.solve(topo_i, F, ftype, 0.0)
            Iph = np.abs(SEQ2PH @ r['IF'])
            ours = Iph.max() if ftype != 'SLG' else abs(3*r['IF'][0])
            theirs = pn.res_bus_sc.ikss_ka.iloc[F]*1e3
            errs.append(abs(ours - theirs)/theirs)
        res[f'{name}_{fault}'] = float(max(errs))
    pn, nb = pp_net(name)
    sc.calc_sc(pn, bus=far - 1, fault='3ph', case='max', branch_results=True)
    r = fmi.solve(topo_i, far - 1, '3ph', 0.0)
    nbr = len(pn.line)
    ours = np.abs(r['I1b'][:nbr]); theirs = pn.res_line_sc.ikss_ka.values*1e3
    on_path = theirs > 1.0
    res[f'{name}_3ph_branch'] = float(np.max(np.abs(ours[on_path] - theirs[on_path])/theirs[on_path]))
print('V5 pandapower grid-only max relative error:', res)
out['V5_pandapower_max_rel_err'] = res
out['pandapower_version'] = pp.__version__

# ---------------------------------------------------------------- V6 independent converter re-solve
from scipy.optimize import fsolve
from params import CONVERTER, HUB_CABLE_OHM
BR, PL, QL, _ = feeder_data('33'); A3 = np.exp(2j*np.pi/3)
hb = sorted(HUBS); n0 = 33 + len(hb)
def build_br(split=None, x=0.5):
    br = [(f - 1, t - 1, complex(r_, x_)) for f, t, r_, x_ in BR]
    hn = {b: 33 + j for j, b in enumerate(hb)}
    for b in hb: br.append((b - 1, hn[b], HUB_CABLE_OHM))
    n = n0
    if split is not None:
        f, t, z = br[split]; br[split] = (f, n, x*z); br.append((n, t, (1 - x)*z)); n += 1
    return br, hn, n
br0, hn, _ = build_br()
Sd = np.zeros(n0, complex)                           # own load flow: constant-power injections
for b, p in PL.items(): Sd[b - 1] = (p + 1j*QL[b])*1e3
for b, stt in HS.items():
    Sd[hn[b]] += HUBS[b]*1e6*(1 if stt == 'chg' else (-1 if stt == 'exp' else 0))
Yt = np.zeros((n0, n0), complex)
for f, t, z in br0: y = 1/z; Yt[f, f] += y; Yt[t, t] += y; Yt[f, t] -= y; Yt[t, f] -= y
Vlf = np.full(n0, VPH, complex)
for _ in range(300):
    Vlf[1:] = np.linalg.solve(Yt[1:, 1:], -np.conj(Sd/3/Vlf)[1:] - Yt[1:, 0]*VPH)
Isrc = Yt[0] @ Vlf
Zs1 = VLL**2/(ssc*1e6)*np.exp(1j*np.arctan(xr)); Zs0 = SOURCE['Z0_over_Z1']*Zs1
Eth = VPH + Zs1*Isrc
kf = CONVERTER['kf']
exp_nodes = [hn[b] for b in hb if HS[b] == 'exp']
Irat = {hn[b]: HUBS[b]*1e6/(np.sqrt(3)*VLL) for b in hb}
def indep(Fbus=None, split=None, ftype='3ph', Rf=0.0):
    br, _, n = build_br(split)
    yL = np.zeros(n, complex)
    for i in range(33):
        if (i + 1) in PL: yL[i] = np.conj((PL[i + 1] + 1j*QL[i + 1])*1e3/3)/abs(Vlf[i])**2
    yH = np.zeros(n, complex)
    for b in hb:
        if HS[b] == 'chg': yH[hn[b]] = HUBS[b]*1e6/3/abs(Vlf[hn[b]])**2
    Y1 = np.zeros((n, n), complex); Y0 = np.zeros((n, n), complex)
    for f, t, z in br:
        for Y, zz in ((Y1, z), (Y0, LINE_Z0_OVER_Z1*z)):
            y = 1/zz; Y[f, f] += y; Y[t, t] += y; Y[f, t] -= y; Y[t, f] -= y
    Y2 = Y1 + np.diag(yL); Y1 = Y1 + np.diag(yL + yH)
    Y1[0, 0] += 1/Zs1; Y2[0, 0] += 1/Zs1; Y0[0, 0] += 1/Zs0
    Z1, Z2, Z0 = np.linalg.inv(Y1), np.linalg.inv(Y2), np.linalg.inv(Y0)
    F = (Fbus - 1) if split is None else n - 1
    def net_solve(Ih):
        J = np.zeros(n, complex); J[0] = Eth/Zs1
        for k, i in enumerate(exp_nodes): J[i] += Ih[k]
        Voc = Z1 @ J; vf = Voc[F]; z1, z2, z0 = Z1[F, F], Z2[F, F], Z0[F, F]
        if ftype == '3ph': I1 = vf/(z1 + Rf); I2 = I0 = 0
        elif ftype == 'SLG': I1 = I2 = I0 = vf/(z1 + z2 + z0 + 3*Rf)
        elif ftype == 'LL': I1 = vf/(z1 + z2 + Rf); I2 = -I1; I0 = 0
        return Voc - Z1[:, F]*I1, -Z2[:, F]*I2, -Z0[:, F]*I0
    def resid(xv):
        Ih = xv[0::2] + 1j*xv[1::2]; V1 = net_solve(Ih)[0]; o = []
        for k, i in enumerate(exp_nodes):      # law P: active current 1/v, limited to kf
            v = abs(V1[i])/VPH; tgt = min(1/v, kf)*Irat[i]*np.exp(1j*np.angle(V1[i]))
            o += [(Ih[k] - tgt).real, (Ih[k] - tgt).imag]
        return o
    x0 = sum(([Irat[i], 0.0] for i in exp_nodes), [])
    xs = fsolve(resid, x0, xtol=1e-12); Ih = xs[0::2] + 1j*xs[1::2]
    V1, V2, V0 = net_solve(Ih)
    I1b = np.array([(V1[f] - V1[t])/z for f, t, z in br]); I2b = np.array([(V2[f] - V2[t])/z for f, t, z in br])
    I0b = np.array([(V0[f] - V0[t])/(LINE_Z0_OVER_Z1*z) for f, t, z in br])
    Iph = np.abs(SEQ2PH @ np.vstack([I0b, I1b, I2b])).max(axis=0)
    return Iph, np.abs(3*I0b)
worst_I = worst_3I0 = 0.0; ncase = nskip = 0
cases = [(b, None, ft, Rf) for b in range(2, 34) for ft, Rf in (('3ph', 0.0), ('SLG', 10.0), ('LL', 0.0))]
cases += [(None, k, ft, 0.0) for k in (0, 12, 24, 28) for ft in ('3ph', 'SLG')]
for Fb, split, ft, Rf in cases:
    if split is None: rr = fm.solve(topo, Fb - 1, ft, Rf)
    else: rr = fm.solve(fm.topology(split, 0.5), net.n, ft, Rf)
    if any(v.get('pll') for v in rr['latch'].values()): nskip += 1; continue   # indep model has no PLL hold
    mine, mine3 = indep(Fb, split, ft, Rf)
    theirs = np.abs(phase_currents(rr['I0b'], rr['I1b'], rr['I2b'])).max(axis=0)
    m = min(len(mine), len(theirs)); big = theirs[:m] > 1.0
    worst_I = max(worst_I, float(np.max(np.abs(mine[:m][big] - theirs[:m][big])/theirs[:m][big])))
    worst_3I0 = max(worst_3I0, float(np.max(np.abs(mine3[:m] - np.abs(3*rr['I0b'])[:m]))))
    ncase += 1
out['V6_independent_converter_resolve'] = dict(cases=ncase, skipped_pll_hold=nskip,
                                               max_rel_err_branch_phase_current=worst_I, max_abs_err_3I0_A=worst_3I0)
print('V6 independent converter re-solve:', out['V6_independent_converter_resolve'])
json.dump(out, open(RES + '/verify_model.json', 'w'), indent=1, default=str)
print('saved results/verify_model.json')
