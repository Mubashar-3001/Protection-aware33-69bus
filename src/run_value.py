"""run_value.py — annual value of adaptation (expected unserved energy).

For a policy, every fault case is weighted by
    w = pi(scenario) * lambda(section) * share(fault type) * share(R_f)
and mapped to unserved energy (kWh) through the device that actually
clears it:
    selective           P_down(primary) * r_rep
    backup/upstream     + (P_down(first) - P_down(primary)) * r_sw
    false trip (off-path relay q)   + P_down(q) * r_sw
    nothing trips       + (P_total - P_down(primary)) * r_sw
Margin shortfalls (outcome 1) are converted to a probability of selectivity
loss by Monte Carlo over the same error bounds the grading margin assumes.
Adaptive policies also pay for wrong-group operation. A mismatch event (the
active group is not the one designed for the actual state, uniform over the
other groups) lasts episode_h hours; n_mis events per year put the feeder in
the wrong group for a share p_wg = n_mis*episode_h/8760 of the time. Fault
outcomes in that time are evaluated with the wrong settings, and any relay
whose load exceeds its pickup trips on load once per event.
Value(policy) = (EUE_robust - EUE_policy) * VCR.
EUE depends only on which device clears a fault, not on how fast. Two
speed-sensitive measures are therefore computed as well, over each policy's
own states and with the same weights w: the expected annual fault duration
(operating time of the first relay plus breaker interruption; the voltage
sag a fault causes lasts as long) and the expected annual I^2 t let-through
of the clearing device (thermal stress on the faulted section).
usage: python run_value.py 33 -> results/value_<feeder>.json
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES, FIGS, TEX, SRC
import sys, json, pickle, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings as S
import policies as P
from params import LOAD_LEVELS, MARGIN, FAULT_TYPE_SHARE

# ---------------------------------------------------------- parameters
PAR = dict(
    lam_per_km=0.065,      # [S] allan1991 (RBTS 11 kV overhead line), faults/(km yr)
    ohm_per_km=0.40,       # [A] length proxy |Z_k| / 0.40 ohm/km (benchmark gives no lengths)
    r_rep=5.0,             # [S] allan1991 repair time (h)
    r_sw=1.0,              # [S] allan1991 switching time (h)
    p_peak=0.30,           # [A] share of hours at the peak level
    p_state={'peak': {'off': 0.6, 'exp': 0.4},
             'light': {'off': 0.5, 'chg': 0.4, 'exp': 0.1}},   # [A] per hub, independent
    vcr=(34.39, 41.48),    # [S] aer2024vcr: commercial overall / residential, A$/kWh ($2024)
    episode_h=(0.25, 1.0, 4.0),   # [A] duration of one mismatch event (h), varied
    mc=4000,               # Monte Carlo draws for margin-shortfall cases
)


def scenario_prob(ds):
    pr = []
    for lvl, hs in ds['scen']:
        p = PAR['p_peak'] if lvl == 'peak' else 1 - PAR['p_peak']
        for v in hs.values(): p *= PAR['p_state'][lvl][v]
        pr.append(p)
    pr = np.array(pr); return pr/pr.sum()


def section_rates(ds):
    """fault rate (1/yr) carried by each mid-branch location; buses/hubs 0."""
    net = ds['net']; lam = np.zeros(len(ds['locs']))
    for l, (lab, node, kb, x) in enumerate(ds['locs']):
        if kb is not None:
            lam[l] = PAR['lam_per_km']*abs(net.z1[kb])/PAR['ohm_per_km']
    return lam


def type_weights(ds):
    w = np.zeros(len(ds['ftypes']))
    for t, (ft, Rf) in enumerate(ds['ftypes']):
        n = sum(1 for (f2, _) in ds['ftypes'] if f2 == ft)
        w[t] = FAULT_TYPE_SHARE[ft]/n
    return w


def downstream_load(ds):
    """gross demand (kW) downstream of each relay, per scenario."""
    net, lay = ds['net'], ds['lay']; out = np.zeros((len(ds['scen']), lay.nr))
    for s, (lvl, hs) in enumerate(ds['scen']):
        gross = {b: ('off' if v == 'exp' else v) for b, v in hs.items()}
        Sn = net.injections(LOAD_LEVELS[lvl], gross).real/1e3
        for r, k in enumerate(lay.branch):
            out[s, r] = Sn[net.subtree(net.t[k])].sum()
    tot = np.array([net.injections(LOAD_LEVELS[l], {b: ('off' if v == 'exp' else v) for b, v in h.items()}).real.sum()/1e3
                    for (l, h) in ds['scen']])
    return out, tot


MC_CASES = [0]            # number of margin-short cases converted by Monte Carlo


def p_loss(tp, tb, rng, n):
    """probability that the backup clears first, sampling relay errors
    (+-E_R each), CT-induced error on the backup (+-E_CT) and breaker time."""
    m = MARGIN; MC_CASES[0] += 1
    dP = rng.uniform(-m['ER'], m['ER'], n)/100; dB = rng.uniform(-m['ER'], m['ER'], n)/100
    dC = rng.uniform(-m['ECT'], m['ECT'], n)/100
    return float(np.mean(tb*(1 + dB + dC) < tp*(1 + dP) + m['tCB'] + m['to']))


def ens_cases(ds, scen_ids, settings_of, Pd, Ptot, rng):
    """expected unserved energy per case (kWh) for scenarios scen_ids."""
    lay = ds['lay']; owner = ds['owner']; fwd = ds['topo_fwd']
    out = {}
    for s in scen_ids:
        st, tp_, tn_ = settings_of(s)
        T = S.operate_times(ds, s, st, tp_, tn_)
        nL, nT, nR = T.shape; E = np.zeros((nL, nT))
        for l in range(nL):
            if ds['locs'][l][2] is None: continue                      # only mid-section faults carry rate
            p = owner[l]; bn = lay.backup[lay.names[p]]
            b = lay.names.index(bn) if bn else None
            base = Pd[s, p]*PAR['r_rep']
            for t in range(nT):
                row = T[l, t]; q = int(np.argmin(row)); tq = row[q]
                if not np.isfinite(tq):
                    E[l, t] = base + (Ptot[s] - Pd[s, p])*PAR['r_sw']; continue
                if fwd[l, q] != 1:
                    E[l, t] = base + Pd[s, q]*PAR['r_sw']; continue
                if q != p and row[p] > tq + 1e-12:
                    E[l, t] = base + (Pd[s, q] - Pd[s, p])*PAR['r_sw']; continue
                E[l, t] = base
                if b is not None and np.isfinite(row[b]) and \
                        row[b] < (1 + S.E_MARG)*row[p] + S.C_MARG - 1e-9:      # margin short
                    pl = p_loss(row[p], row[b], rng, PAR['mc'])
                    E[l, t] = base + pl*(Pd[s, b] - Pd[s, p])*PAR['r_sw']
        out[s] = E
    return out


def speed(ds, designs, gof, pi, lam, wt):
    """expected annual fault duration (s/yr) and I^2 t let-through of the clearing
    device (kA^2 s/yr) over the policy's own states, with the weights of the EUE."""
    dur = i2t = top = wsum = 0.0; on = lam > 0
    for s in range(len(ds['scen'])):
        dg = designs[gof[s]]
        T = S.operate_times(ds, s, dg['st'], dg['tp'], dg['tn'])
        q = T.argmin(axis=2); tau = T.min(axis=2)[on] + MARGIN['tCB']
        assert np.isfinite(tau).all(), 'a rate-carrying fault is not cleared'
        I = np.take_along_axis(ds['Iph'][s], q[..., None], axis=2)[..., 0][on]/1e3
        W = pi[s]*lam[on][:, None]*wt[None, :]
        dur += float((W*tau).sum()); i2t += float((W*I**2*tau).sum())
        top += float((W*(tau - MARGIN['tCB'])).sum()); wsum += float(W.sum())
    # rate-weighted mean relay operating time (no breaker time), to compare with the unweighted mean
    return dict(fault_duration_s_per_yr=dur, i2t_kA2s_per_yr=i2t, rate_weighted_mean_top_s=top/wsum)


def eue(ds, D, groups, Pd, Ptot, pi, lam, wt, rng):
    designs = [D.design(G) for G in groups]
    gof = {s: g for g, G in enumerate(groups) for s in G}
    nS = len(ds['scen'])
    mc0 = MC_CASES[0]
    own = ens_cases(ds, range(nS), lambda s: (designs[gof[s]]['st'], designs[gof[s]]['tp'], designs[gof[s]]['tn']),
                    Pd, Ptot, rng)
    def agg(Emap):
        return sum(pi[s]*(lam[:, None]*wt[None, :]*Emap[s]).sum() for s in Emap)
    E_own = agg(own); res = dict(EUE_own=E_own, mc_cases_own=MC_CASES[0] - mc0)
    res.update(speed(ds, designs, gof, pi, lam, wt))
    if len(groups) == 1:
        res.update(EUE=E_own, EUE_wrong=0.0, EUE_encroach=0.0); return res
    K = len(groups); E_wrong = 0.0; q = 0.0; eE = 0.0; mc1 = MC_CASES[0]
    for g, dg in enumerate(designs):
        for s in range(nS):
            if gof[s] == g: continue
            Ew = ens_cases(ds, [s], lambda x: (dg['st'], dg['tp'], dg['tn']), Pd, Ptot, rng)[s]
            E_wrong += pi[s]/(K - 1)*(lam[:, None]*wt[None, :]*Ew).sum()
            fl = np.maximum(S.forward_load(ds, s, True), S.forward_load(ds, s, False))
            trip = np.where(fl > dg['st']['IsP'])[0]
            if len(trip):                       # a relay trips on load: its downstream load is lost
                q += pi[s]/(K - 1)
                eE += pi[s]/(K - 1)*max(Pd[s, r] for r in trip)*PAR['r_sw']
    # per mismatch event: probability of a load trip and expected unserved energy;
    # per unit share of time in the wrong group: extra fault-driven unserved energy
    res.update(EUE_wrong=E_wrong, dEUE_fault_per_unit_pwg=E_wrong - E_own,
               trip_prob_per_mismatch=q, ens_per_mismatch=eE, mc_cases_wrong=MC_CASES[0] - mc1)
    return res


def value(r, R, n_mis, p_wg, vcr):
    """A$/yr relative to robust: own-group gain minus wrong-group losses."""
    if 'trip_prob_per_mismatch' not in r:
        return (R - r['EUE_own'])*vcr
    loss = n_mis*r['ens_per_mismatch'] + p_wg*r['dEUE_fault_per_unit_pwg']
    return (R - r['EUE_own'] - loss)*vcr


if __name__ == '__main__':
    name = sys.argv[1] if len(sys.argv) > 1 else '33'
    ds = pickle.load(open(RES + f'/ds_{name}_base.pkl', 'rb'))
    pol = json.load(open(RES + f'/policies_{name}.json'))
    D = P.Designer(ds); rng = np.random.default_rng(7)
    pi, lam, wt = scenario_prob(ds), section_rates(ds), type_weights(ds)
    Pd, Ptot = downstream_load(ds)
    ex = {int(k): v for k, v in pol['exhaustive'].items() if v}
    kbest = min(ex, key=lambda k: ex[k]['mean_t'])
    big = [k for k in pol['rules'] if k.startswith('CHG') and k != 'CHG'][0]
    cl = pol['cluster'][pol['cluster_best_by_silhouette']]
    cands = {'robust': pol['robust']['groups'], 'per_state': pol['per_state']['groups'],
             'best_K2': ex[2]['groups'], 'best_K4': ex[4]['groups'], f'best_K{kbest}': ex[kbest]['groups'],
             'TOD': pol['rules']['TOD']['groups'], 'CHG': pol['rules']['CHG']['groups'],
             'CHGL': pol['rules'][big]['groups'], 'TOD+CHG': pol['rules']['TOD+CHG']['groups'],
             'EXP': pol['rules']['EXP']['groups'], 'CL': cl['groups']}
    out = dict(params=PAR, total_fault_rate=float(lam.sum()), policies={})
    for k, groups in cands.items():
        r = eue(ds, D, groups, Pd, Ptot, pi, lam, wt, rng)
        out['policies'][k] = r
        print(k, {a: (round(b, 4) if isinstance(b, float) else b) for a, b in r.items()}, flush=True)
    R = out['policies']['robust']['EUE_own']
    grid = {}
    for n_mis in (0, 1, 10, 100):
        for h in PAR['episode_h']:
            p_wg = n_mis*h/8760.0
            grid[f'n={n_mis}|h={h}'] = {k: [value(r, R, n_mis, p_wg, v) for v in PAR['vcr']]
                                       for k, r in out['policies'].items()}
    out['value_grid'] = grid
    json.dump(out, open(RES + f'/value_{name}.json', 'w'), indent=1, default=float)
    print('total fault rate %.2f /yr; robust EUE %.1f kWh/yr' % (lam.sum(), R))
    for k, r in out['policies'].items():
        print('%-10s fault duration %.4f s/yr  I2t %.4f kA2s/yr' % (k, r['fault_duration_s_per_yr'], r['i2t_kA2s_per_yr']))
    for key in ('n=0|h=1.0', 'n=1|h=1.0', 'n=10|h=4.0'):
        print(key, {k: [round(x) for x in v] for k, v in grid[key].items()})
