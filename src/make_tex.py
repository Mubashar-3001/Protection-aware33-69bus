"""make_tex.py — writes tex/numbers.tex (macros for every number quoted in
the text), tex/tab_*.tex (tables) and tex/boundary.tex (the boundary-sweep
paragraphs), from results/*.json only. Statements whose truth depends on the
results are generated here, so that the text cannot drift from the data."""
import os, sys, ast, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES, TEX
import json, numpy as np
from cases import scenarios
from params import FAULT_SET, CURVE, MARGIN, CT_ALF
from settings import E_MARG, C_MARG
R = RES + '/'; T = TEX + '/'
FEED = (('33', 'A'), ('69', 'B'))
NFT = sum(len(v) for v in FAULT_SET.values())


def J(n): return json.load(open(R + n))
def f(x, d=1):
    if abs(x) < 0.5*10**(-d): x = 0.0
    s = f'{x:,.{d}f}'.replace(',', '\\,')
    return '$-$' + s[1:] if s.startswith('-') else s
def i(x): return f'{int(round(x)):,}'.replace(',', '\\,')
def p10(x): return '10^{%d}' % int(np.ceil(np.log10(x))) if x > 0 else '0'
def words(lst, conj='and'):
    lst = [str(x) for x in lst]
    if not lst: return ''
    return lst[0] if len(lst) == 1 else ', '.join(lst[:-1]) + f' {conj} ' + lst[-1]
NUMW = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten',
        11: 'eleven', 12: 'twelve'}
def nw(n): return NUMW.get(int(n), str(int(n)))
def role(r):
    if r == 'R1': return 'feeder breaker R1'
    return {'R': 'trunk recloser', 'L': 'lateral recloser', 'H': 'hub breaker'}[r[0]] + ' ' + r
def loc_txt(lbl):
    lbl = str(lbl)
    if lbl.startswith('H'): return f'the terminal of hub {lbl[1:]}'
    if lbl.endswith('m'): a, b = lbl[:-1].split('-'); return f'the middle of section {a}--{b}'
    return f'bus {lbl}'

M = {}
def m(name, val):
    assert name.isalpha(), name
    M[name] = val

# ================================================================ verification
V = J('verify_model.json'); VC = J('verify_convergence.json'); VG = J('verify_grading.json')
m('LossA', f(V['V1_33']['loss_kW'], 2)); m('VminA', f(V['V1_33']['vmin'], 4))
m('LossB', f(V['V1_69']['loss_kW'], 2)); m('VminB', f(V['V1_69']['vmin'], 4))
m('PPerr', p10(max(V['V5_pandapower_max_rel_err'].values())))
m('PrefRes', p10(V['V2_prefault_mismatch_pu']))
m('KCLres', f(max(V['V4_kcl_residual_A'].values())*1e6, 1))
v6 = V['V6_independent_converter_resolve']
m('IndepCases', i(v6['cases'])); m('IndepSkip', i(v6['skipped_pll_hold']))
m('IndepErr', p10(v6['max_rel_err_branch_phase_current']))
m('ConvCases', i(VC['cases'])); m('ConvMaxIt', i(VC['max_iter']))
dz = VC['design']
assert VC['cases'] == dz['fault_nodes']*dz['fault_variants']*dz['hub_state_combinations']*dz['control_laws']*len(dz['current_limits'])
assert VC['non_converged'] == 0, 'converter iteration failed to converge: revise the text'
m('ConvNodes', i(dz['fault_nodes'])); m('ConvBus', i(dz['bus_nodes'])); m('ConvHub', i(dz['hub_terminals']))
m('ConvVariants', i(dz['fault_variants'])); m('ConvStates', i(dz['hub_state_combinations']))
m('ConvLaws', i(dz['control_laws'])); m('ConvKf', i(len(dz['current_limits'])))
m('ConvKfSet', ','.join(f(x, 1) for x in dz['current_limits']))
for fd, tag in FEED:
    m('GoneDes' + tag, i(VG[f'G1_{fd}']['designs'])); m('GoneSame' + tag, i(VG[f'G1_{fd}']['identical_TMS']))
    assert VG[f'G1_{fd}']['designs'] == VG[f'G1_{fd}']['identical_TMS'], 'DP and MILP differ: revise the text'
    m('GfourBad' + tag, i(VG[f'G4_{fd}']['not_fully_selective']))
g2 = VG['G2']
m('GtwoCombos', i(list(g2.values())[0]['combinations']))
m('GtwoN', i(len(g2))); assert len(g2) == 2
m('GtwoErr', p10(max(v['rel_diff'] for v in g2.values())) if max(v['rel_diff'] for v in g2.values()) > 1e-12 else '0')
assert max(v['rel_diff'] for v in g2.values()) < 1e-9, 'DP differs from brute force'
g5 = VG['G5']
for fd, tag in FEED:
    m('DesigFixed' + tag, f(g5[fd]['fixed_designated_mean_t']*1e3, 1))
    m('DesigGain' + tag, f(g5[fd]['per_state_gain_designated_pct'], 1))
    assert abs(g5[fd]['fixed_exact_mean_t'] - J(f'policies_{fd}.json')['robust']['mean_t']) < 1e-9
g3 = VG['G3']
m('GthreeTried', i(sum(v['neighbours_tried'] for v in g3.values())))
m('GthreeImp', i(sum(v['improving'] for v in g3.values())))

# ================================================================ hosting
rho_all, dv_all, cos_all, rp_all = [], [], [], []
env = []
for fd, tag in FEED:
    H = J(f'hosting_{fd}.json')
    m('Total' + tag, f(H['total_MW'], 2)); m('Vmin' + tag + 'hub', f(H['worst']['vmin'], 3))
    m('Vmax' + tag + 'hub', f(H['worst']['vmax'], 3)); m('Imax' + tag + 'hub', i(H['worst']['imax']))
    m('Hubs' + tag, f"{words(H['chargers'])} chargers at buses {words(H['buses'])}")
    for h in H['hubs'].values():
        rho_all.append(h['ratio']); dv_all.append(h['dv']); cos_all.append(h['cos_theta']); rp_all.append(h['rho_pred'])
    ratios = [h['ratio'] for h in H['hubs'].values()]
    m('RhoMin' + tag, f(100*min(ratios), 1)); m('RhoMax' + tag, f(100*max(ratios), 1))
    zero = [b for b in H['buses'] if H['single'][str(b)]['unmanaged'] == 0]
    if zero: env.append(f"{words(['bus ' + str(b) for b in zero])} of the {fd}-bus feeder")
m('RhoLo', f(100*min(rho_all), 1)); m('RhoHi', f(100*max(rho_all), 1))
m('DvLo', f(100*min(dv_all), 1)); m('DvHi', f(100*max(dv_all), 1))
m('CosLo', f(min(cos_all), 2)); m('CosHi', f(max(cos_all), 2))
m('RhoPredLo', f(100*min(rp_all), 1)); m('RhoPredHi', f(100*max(rp_all), 1))
hub_rows = [(fd, b, h) for fd, _ in FEED for b, h in J(f'hosting_{fd}.json')['hubs'].items()]
err = sorted(hub_rows, key=lambda x: -abs(x[2]['rho_pred'] - x[2]['ratio']))
fd_w, b_w, h_w = err[0]; rest = max(abs(x[2]['rho_pred'] - x[2]['ratio']) for x in err[1:])
m('RhoWorstSentence', (f"The estimate is within {f(100*rest, 1)} percentage points everywhere except at bus {b_w} of the {fd_w}-bus feeder, "
                       f"where the Thevenin impedance is mostly reactive ($\\cos\\theta_j={f(h_w['cos_theta'], 2)}$) and the hub moves the voltage by only "
                       f"{f(100*h_w['dv'], 1)}\\,\\%.") if h_w['cos_theta'] < 0.5 else '')
m('EnvSentence', (r'With charging allowed at any time, ' + words(env) +
                  (' cannot host a single charger.' if True else '')) if env else '')

# ================================================================ policies
POLNAME = {'TOD': 'time of day', 'CHG': 'any hub charging', 'TOD+CHG': 'time of day with charging',
           'EXP': 'any hub exporting'}
def polname(kind, k):
    if kind == 'rule':
        return POLNAME.get(k, f'hub {k[3:]} charging')
    if kind == 'cl':
        meth, K = k.split('_K'); return f"{K}-means" if meth == 'kmeans' else f'{K}-group Ward'
    return f'best {k}-group'

def info_needed(groups, scen):
    gof = {s: g for g, G in enumerate(groups) for s in G}
    if len(groups) == 1: return 'none'
    by_lvl = {}
    for s, (lvl, hs) in enumerate(scen): by_lvl.setdefault(lvl, set()).add(gof[s])
    if all(len(v) == 1 for v in by_lvl.values()): return 'clock'
    key = {}
    hub_only = True
    for s, (lvl, hs) in enumerate(scen):
        k = tuple(sorted(hs.items()))
        if k in key and key[k] != gof[s]: hub_only = False
        key[k] = gof[s]
    return 'hub status' if hub_only else 'clock, hub status'

def describe2(blocks, class_keys):
    """shortest conjunction of literals (light load, hub b charging) defining one block"""
    cls = [ast.literal_eval(k) for k in class_keys]
    hubs = [b for b, _ in cls[0][1]]
    lits = [('L', None)] + [('C', b) for b in hubs]
    def holds(lit, pol, c):
        lvl, hs = c; v = (lvl == 'light') if lit[0] == 'L' else (dict(hs)[lit[1]] == 'chg')
        return v == pol
    for n in (1, 2, 3, 4):
        for combo in itertools.combinations(lits, n):
            for pols in itertools.product((True, False), repeat=n):
                S = {c for c in range(len(cls)) if all(holds(l, p, cls[c]) for l, p in zip(combo, pols))}
                for blk in blocks:
                    if S == set(blk):
                        lvl = [p for (l, _), p in zip(combo, pols) if l == 'L']
                        pos = [l[1] for l, p in zip(combo, pols) if l[0] == 'C' and p]
                        neg = [l[1] for l, p in zip(combo, pols) if l[0] == 'C' and not p]
                        parts = []
                        if pos: parts.append(f"hub{'s' if len(pos) > 1 else ''} {words(pos)} charging")
                        if neg:
                            parts.append(f'hub {neg[0]} not charging' if len(neg) == 1 else
                                         f"neither hub {neg[0]} nor hub {neg[1]} charging" if len(neg) == 2 else
                                         f"none of hubs {words(neg)} charging")
                        lt = ('light load' if lvl[0] else 'peak load') if lvl else None
                        pt = ' and '.join(parts)
                        if lt and pt: return f'{lt} with {pt}'
                        return lt if lt else 'states with ' + pt
    return None

gains_rule_all = []; zero_ft = {}; fts = []; clus_never_better = True; psfast = {}; kbest = {}
for fd, tag in FEED:
    P = J(f'policies_{fd}.json'); TO = J(f'tmsonly_{fd}.json')
    hub_buses = sorted(int(b) for b in P['hubs'])
    scen = scenarios(tuple(hub_buses)); assert len(scen) == len(P['robust']['groups'][0])
    rb = P['robust']; r0 = rb['mean_t']; g = lambda a: 100*(1 - a['mean_t']/r0)
    m('Cases' + tag, i(P['n_cases'])); m('Scen' + tag, i(len(scen)))
    m('Locs' + tag, i(P['n_cases']/(len(scen)*NFT)))
    m('Trob' + tag, f(r0*1e3, 1)); m('TrobMax' + tag, f(rb['max_t'], 2)); m('TrobPf' + tag, f(rb['p95_t']*1e3, 0))
    m('MinMarg' + tag, f(rb['min_margin']*1e3, 1))
    m('SensP' + tag, f(rb['sens_primary_P'], 1)); m('SensB' + tag, f(rb['sens_backup_P'], 1))
    m('SensN' + tag, f(rb['sens_primary_N'], 1)); m('SensBN' + tag, f(rb['sens_backup_N'], 1))
    an = P['robust_anatomy']; ce = an['clearing_element']; nce = sum(ce.values())
    m('ElemFifty' + tag, f(100*ce['50']/nce, 0)); m('ElemP' + tag, f(100*ce['51P']/nce, 0))
    m('ElemN' + tag, f(100*ce['51N']/nce, 0))
    m('SlackOther' + tag, f(an['other_onpath_min_slack_s']*1e3, 1))
    assert an['backup_never_operates'] == 0 and rb['load_encroach'] == 0 and rb['all_selective']
    sl = an['slowest'][0]
    m('SlowLoc' + tag, loc_txt(sl['loc'])); m('SlowRelay' + tag, sl['relay']); m('SlowTMS' + tag, f(sl['TMS'], 2))
    m('SlowRf' + tag, i(sl['Rf'])); m('SlowElem' + tag, 'earth' if sl['element'] == '51N' else 'phase')
    m('SlowType' + tag, {'SLG': 'single-line-to-ground', 'LLG': 'double-line-to-ground', 'LL': 'line-to-line',
                         '3ph': 'three-phase'}[sl['ftype']])
    gr = P['robust_grading']; m('Rows' + tag, i(gr['nrows'])); m('RowsKept' + tag, i(gr['nrows_kept']))
    leg = P['legacy']; nl = sum(leg['outcomes'].values())
    m('LegFalse' + tag, i(leg['outcomes'].get('3', 0))); m('LegFalsePct' + tag, f(100*leg['outcomes'].get('3', 0)/nl, 1))
    m('LegEnc' + tag, i(leg['load_encroach'][0])); m('LegRelays' + tag, words(sorted(leg['false_trip_relays'])))
    assert leg['false_trip_relays_at_pickup_floor'] and all(r.startswith('H') for r in leg['false_trip_relays'])
    ps = P['per_state']; m('Tps' + tag, f(ps['mean_t']*1e3, 1)); m('Gps' + tag, f(g(ps), 1))
    ex = {int(k): v for k, v in P['exhaustive'].items() if v}
    for K, w in ((2, 'Two'), (3, 'Three'), (4, 'Four'), (9, 'Nine')):
        m(f'Tbest{w}' + tag, f(ex[K]['mean_t']*1e3, 1)); m(f'Gbest{w}' + tag, f(g(ex[K]), 1))
    kb = min(ex, key=lambda k: ex[k]['mean_t']); kbest[fd] = kb
    m('Kbest' + tag, str(kb)); m('GbestAll' + tag, f(g(ex[kb]), 1)); m('TbestAll' + tag, f(ex[kb]['mean_t']*1e3, 1))
    gball = max(gball, g(ex[kb])) if 'gball' in dir() else g(ex[kb]); m('GbestAllHi', f(gball, 1))
    allpol = [ps] + list(ex.values()) + list(P['rules'].values()) + list(P['cluster'].values())
    psfast[fd] = ps['mean_t'] <= min(a['mean_t'] for a in allpol) + 1e-12
    m('DescTwo' + tag, describe2(ex[2]['class_blocks'], P['classes']) or 'a two-way split of the load classes')
    m('InfoTwo' + tag, info_needed(ex[2]['groups'], scen))
    rg = {k: g(a) for k, a in P['rules'].items()}; gains_rule_all += list(rg.values())
    m('GruleMin' + tag, f(min(rg.values()), 1)); m('GruleMax' + tag, f(max(rg.values()), 1))
    m('Gexp' + tag, f(rg['EXP'], 1))
    cl = P['cluster']; sil = [a['silhouette'] for a in cl.values()]
    m('SilMin' + tag, f(min(sil), 2)); m('SilMax' + tag, f(max(sil), 2))
    gcl = [g(a) for a in cl.values()]; m('GclMin' + tag, f(min(gcl), 1)); m('GclMax' + tag, f(max(gcl), 1))
    m('AriMin' + tag, f(min(a['stability_ari_mean'] for a in cl.values()), 2))
    for a in cl.values():
        if a['K'] in ex and a['mean_t'] < ex[a['K']]['mean_t'] - 1e-12: clus_never_better = False
    m('TmsOnly' + tag, f(TO['gain_pct'], 1)); m('ExhTime' + tag, i(P['exhaustive_time_s']))
    m('ExhDes' + tag, i(P['exhaustive_designs']))
    pols = [('rule', k, a) for k, a in P['rules'].items()] + [('cl', k, a) for k, a in cl.items()] + \
           [('best', k, a) for k, a in P['exhaustive'].items() if a and int(k) > 1]
    for kind, k, a in pols:
        wg = a.get('wrong_group')
        if not wg: continue
        ft = wg['total'].get('3', 0)/sum(wg['total'].values())
        if ft > 0: fts.append(100*ft)
        else: zero_ft.setdefault(fd, []).append(polname(kind, k))
m('FtMin', f(min(fts), 0)); m('FtMax', f(max(fts), 0))
DB = [a['db'] for fd, _ in FEED for a in J(f'policies_{fd}.json')['cluster'].values()]
m('DBmin', f(min(DB), 2))
m('ZeroFt', words([f"{words(v)} ({fd}-bus)" for fd, v in zero_ft.items()]) if zero_ft else 'none')
gnd = [max(abs(J(f'impact_{fd}.json')['by_type'][t]['primary_max_increase']),
           abs(J(f'impact_{fd}.json')['by_type'][t]['primary_max_decrease'])) for fd, _ in FEED for t in ('SLG', 'LLG')]
m('dNmax', f(100*max(gnd), 1))

# ================================================================ impact and value
same_eue = True
for fd, tag in FEED:
    I = J(f'impact_{fd}.json'); VV = J(f'value_{fd}.json')
    m('DirCases' + tag, i(I['directional']['cases_above_pickup'])); m('DirBad' + tag, i(I['directional']['disagreements']))
    m('RevMax' + tag, f(max(v['ratio_to_pickup'] for v in I['reverse'].values()), 2))
    bt = I['by_type']
    m('dPmax' + tag, f(100*max(max(abs(v['primary_max_increase']), abs(v['primary_max_decrease'])) for v in bt.values()), 0))
    m('dBmax' + tag, f(100*max(max(abs(v['backup_max_increase']), abs(v['backup_max_decrease'])) for v in bt.values()), 0))
    m('dPpf' + tag, f(100*max(v['primary_p95_abs'] for v in bt.values()), 1))
    m('dBpf' + tag, f(100*max(v['backup_p95_abs'] for v in bt.values()), 1))
    m('HubVlow' + tag, f(100*I['hub_voltage']['frac_below_0p5'], 1))
    pol = VV['policies']; R0 = pol['robust']['EUE_own']
    m('EUErob' + tag, i(R0)); m('Lam' + tag, f(VV['total_fault_rate'], 2))
    same_eue &= all(abs(pol[k]['EUE_own'] - R0) < 1e-6*max(R0, 1) for k in pol)
    adap = [k for k in pol if pol[k].get('trip_prob_per_mismatch', 0) > 0]
    m('TripPMin' + tag, f(100*min(pol[k]['trip_prob_per_mismatch'] for k in adap), 0))
    m('TripPMax' + tag, f(100*max(pol[k]['trip_prob_per_mismatch'] for k in adap), 0))
    m('EnsMisMin' + tag, f(min(pol[k]['ens_per_mismatch'] for k in adap)/1e3, 2))
    m('EnsMisMax' + tag, f(max(pol[k]['ens_per_mismatch'] for k in adap)/1e3, 2))
    vg = VV['value_grid']['n=1|h=1.0']
    m('ValMisLo' + tag, i(-max(vg[k][0] for k in adap)/1e3)); m('ValMisHi' + tag, i(-min(vg[k][1] for k in adap)/1e3))
assert same_eue, 'policies differ in own-group EUE: revise the annual-value text'
mcd = {VJ_['params']['mc'] for VJ_ in (J('value_33.json'), J('value_69.json'))}; assert len(mcd) == 1
m('MCdraws', i(mcd.pop()))
mc_own = sum(r.get('mc_cases_own', 0) for fd, _ in FEED for r in J(f'value_{fd}.json')['policies'].values())
mc_wrong = sum(r.get('mc_cases_wrong', 0) for fd, _ in FEED for r in J(f'value_{fd}.json')['policies'].values())
m('MCSentence', (r"Every policy meets the margin in its own states, so this conversion is needed only under the wrong group." if mc_own == 0 and mc_wrong > 0
                 else r"Every policy meets the margin in every case it is evaluated on, so this conversion is never needed here." if mc_own == 0 and mc_wrong == 0 else ''))
m('Rsw', f(J('value_33.json')['params']['r_sw'], 0)); m('Rrep', f(J('value_33.json')['params']['r_rep'], 0))
VNAMEs = {'robust': 'fixed design', 'TOD': 'time-of-day rule', 'CHG': 'any-hub-charging rule', 'CHGL': 'largest-hub-charging rule',
          'TOD+CHG': 'time-of-day-with-charging rule', 'EXP': 'export-keyed rule', 'CL': 'clustered policy',
          'per_state': 'own settings per state'}
spd = {}
for fd, tag in FEED:
    pol = J(f'value_{fd}.json')['policies']; R0d = pol['robust']['fault_duration_s_per_yr']; R0i = pol['robust']['i2t_kA2s_per_yr']
    gd = {k: 100*(1 - r['fault_duration_s_per_yr']/R0d) for k, r in pol.items()}
    gi = {k: 100*(1 - r['i2t_kA2s_per_yr']/R0i) for k, r in pol.items()}
    kd = max(gd, key=gd.get); ki = max(gi, key=gi.get); spd[fd] = (gd, gi, kd, ki)
    m('DurRob' + tag, f(R0d, 2)); m('ItRob' + tag, f(R0i, 2))
    m('DurGain' + tag, f(gd[kd], 1)); m('ItGain' + tag, f(gi[ki], 1))
    m('DurGainPol' + tag, VNAMEs.get(kd, f"best {kd.split('K')[-1]}-group policy"))
    m('ItGainPol' + tag, VNAMEs.get(ki, f"best {ki.split('K')[-1]}-group policy"))
    m('DurMin' + tag, f(min(gd.values()), 1)); m('ItMin' + tag, f(min(gi.values()), 1))
m('DurGainHi', f(max(max(spd[fd][0].values()) for fd in spd), 1)); m('ItGainHi', f(max(max(spd[fd][1].values()) for fd in spd), 1))
# the fastest policy (best K*): unweighted mean -> rate-weighted operating time -> fault duration (with breaker time)
for fd, tag in FEED:
    pol = J(f'value_{fd}.json')['policies']; kb = f'best_K{kbest[fd]}'
    rw = 100*(1 - pol[kb]['rate_weighted_mean_top_s']/pol['robust']['rate_weighted_mean_top_s'])
    du = 100*(1 - pol[kb]['fault_duration_s_per_yr']/pol['robust']['fault_duration_s_per_yr'])
    m('RateGain' + tag, f(rw, 1)); m('DurGainBest' + tag, f(du, 1))
    assert du <= rw + 1e-9 and rw < 100*(1 - J(f'policies_{fd}.json')['exhaustive'][str(kbest[fd])]['mean_t']/J(f'policies_{fd}.json')['robust']['mean_t'])
# policies that raise the I2t let-through on some feeder, with the change on each feeder
VN2 = dict(VNAMEs); VN2['robust'] = 'fixed design'
up = {}
for fd, tag in FEED:
    for k, g in spd[fd][1].items():
        if g < -0.05: up.setdefault(k, {})[fd] = -g
def _vn(k): return VN2.get(k, f"best {k.split('K')[-1]}-group policy")
order = sorted(up, key=lambda k: -max(up[k].values()))
if up:
    kmax = order[0]; fdmax = max(up[kmax], key=up[kmax].get)
    m('ItUpSentence', (nw(len(up)).capitalize() + ' of the ' + nw(len(spd['33'][1]) - 1) + ' adaptive policies raise it on at least one feeder (Table~\\ref{tab:speed}), '
                       + _vn(kmax) + ' by as much as ' + f(up[kmax][fdmax], 1) + '\\,\\% on the ' + fdmax + '-bus feeder.'))
else:
    m('ItUpSentence', 'No policy raises it.')
m('ItUpMax', f(max(max(v.values()) for v in up.values()), 1) if up else '0')

# ================================================================ stress (both feeders)
sel, short, lost, red_ok, nvar, where = [], [], 0, True, 0, {}
for fd, tag in FEED:
    S = J(f'stress_{fd}.json')['variants']; nvar = len(S)
    for k, v in S.items():
        o = v['frozen']['outcomes']; n = sum(o.values())
        sel.append(100*o.get('0', 0)/n); short.append(v['frozen']['short_margin'])
        lost += sum(c for kk, c in o.items() if kk in ('2', '3', '4'))
        red_ok &= bool(v['redesigned']['all_selective'])
        if v['frozen']['short_margin'] > 0: where.setdefault(k, []).append(fd)
m('StressN', i(nvar)); m('StressSelMin', f(min(sel), 2)); m('StressShortMax', i(max(short))); m('StressLost', i(lost))
LAB = lambda k: (k.replace('k_f', '$k_f$').replace('S_sc', '$S_\\mathrm{sc}$').replace('line Z0/Z1', 'line $Z_0/Z_1$')
                 .replace('source X/R', 'source $X/R$').replace('mode Q (reactive priority)', 'law Q')
                 .replace('mode MC (momentary cessation)', 'law MC').replace(', mode Q', ' with law Q').replace('mode Q', 'law Q'))
m('StressWhere', words([LAB(k) for k in where]) if where else 'none')
m('StressRedOK', 'is again fully selective' if red_ok else 'is not always fully selective')

# ================================================================ tables
def tab_hubs():
    rows = []
    for fd, _ in FEED:
        H = J(f'hosting_{fd}.json')
        rows.append(f'\\multicolumn{{10}}{{l}}{{\\emph{{IEEE {fd}-bus}}}} \\\\')
        for b, h in H['hubs'].items():
            rows.append(f"\\quad {b} & {h['chargers']} & {f(h['P_MW'],2)} & {f(h['Irated_A'],1)} & "
                        f"{f(h['Ilim_A'],1)} & {i(h['Isc_local_A'])} & {f(100*h['ratio'],1)} & {f(100*h['dv'],1)} & "
                        f"{f(h['cos_theta'],2)} & {f(100*h['rho_pred'],1)} \\\\")
        rows.append('\\midrule' if fd == '33' else '')
    open(T + 'tab_hubs.tex', 'w').write('\n'.join(r for r in rows if r) + '\n')

def tab_settings(fd='33'):
    P = J(f'policies_{fd}.json'); rows = []
    for r, s in P['robust_settings'].items():
        i50 = '--' if s['I50P'] is None else i(s['I50P']); i50n = '--' if s['I50N'] is None else i(s['I50N'])
        rows.append(f"{r} & {P['backup'][r] or '--'} & {i(s['CT'])}/1 & {f(s['IsP'],1)} & {f(s['TMSP'],2)} & {i50} & "
                    f"{f(s['IsN'],1)} & {f(s['TMSN'],2)} & {i50n} \\\\")
    open(T + f'tab_settings_{fd}.tex', 'w').write('\n'.join(rows) + '\n')

def tab_policies():
    names = [('Fixed (one group)', 'robust'), ('Time of day', 'TOD'), ('Any hub charging', 'CHG'),
             ('Largest hub charging', 'CHGL'), ('Any hub exporting', 'EXP'), ('Time of day + charging', 'TOD+CHG'),
             ('Clustering (best silhouette)', 'CL'), ('Best 2 groups', 'B2'), ('Best 4 groups', 'B4'),
             ('Best overall ($K^{*}$ groups)', 'BK'), ('Own settings per state', 'PS')]
    data = {}
    for fd, _ in FEED:
        P = J(f'policies_{fd}.json'); VV = J(f'value_{fd}.json')['policies']; r0 = P['robust']['mean_t']
        scen = scenarios(tuple(sorted(int(b) for b in P['hubs'])))
        big = [k for k in P['rules'] if k.startswith('CHG') and k != 'CHG'][0]
        kb = kbest[fd]
        look = {'robust': P['robust'], 'TOD': P['rules']['TOD'], 'CHG': P['rules']['CHG'], 'CHGL': P['rules'][big],
                'EXP': P['rules']['EXP'], 'TOD+CHG': P['rules']['TOD+CHG'],
                'CL': P['cluster'][P['cluster_best_by_silhouette']], 'B2': P['exhaustive']['2'],
                'B4': P['exhaustive']['4'], 'BK': P['exhaustive'][str(kb)], 'PS': P['per_state']}
        vkey = {'robust': 'robust', 'TOD': 'TOD', 'CHG': 'CHG', 'CHGL': 'CHGL', 'EXP': 'EXP', 'TOD+CHG': 'TOD+CHG',
                'CL': 'CL', 'B2': 'best_K2', 'B4': 'best_K4', 'BK': f'best_K{kb}', 'PS': 'per_state'}
        for _, k in names:
            a = look[k]; wg = a.get('wrong_group')
            ft = None if not wg else 100*wg['total'].get('3', 0)/sum(wg['total'].values())
            ens = VV[vkey[k]].get('ens_per_mismatch')
            data[(fd, k)] = dict(t=a['mean_t']*1e3, g=100*(1 - a['mean_t']/r0), ft=ft, ens=ens, K=a['K'],
                                 info=info_needed(a['groups'], scen))
    best = {}
    for fd, _ in FEED:
        vals = [data[(fd, k)] for _, k in names]
        best[(fd, 't')] = min(v['t'] for v in vals); best[(fd, 'g')] = max(v['g'] for v in vals)
        best[(fd, 'ft')] = min(v['ft'] for v in vals if v['ft'] is not None)
        best[(fd, 'ens')] = min(v['ens'] for v in vals if v['ens'] is not None)
    def cell(fd, k, key, txt):
        v = data[(fd, k)][key]
        if v is None: return '--'
        rnd = {'t': 1, 'g': 1, 'ft': 1, 'ens': 2}[key]
        scale = 1e-3 if key == 'ens' else 1.0
        hit = round(v*scale, rnd) == round(best[(fd, key)]*scale, rnd)
        return ('\\best ' if hit else '') + txt
    rows = []
    for lab, k in names:
        a, b = data[('33', k)], data[('69', k)]
        Ks = str(a['K']) if a['K'] == b['K'] else f"{a['K']}/{b['K']}"
        info = a['info'] if a['info'] == b['info'] else f"{a['info']} / {b['info']}"
        cells = []
        for key in ('t', 'g', 'ft', 'ens'):
            for fd in ('33', '69'):
                v = data[(fd, k)][key]
                txt = '--' if v is None else (f(v/1e3, 2) if key == 'ens' else f(v, 1))
                if key == 'g' and k == 'robust': txt = '0'
                cells.append(cell(fd, k, key, txt) if v is not None else '--')
        rows.append(f"{lab} & {Ks} & {info} & " + ' & '.join(cells) + ' \\\\')
    open(T + 'tab_policies.tex', 'w').write('\n'.join(rows) + '\n')

def tab_speed():
    names = [('Time of day', 'TOD'), ('Any hub charging', 'CHG'), ('Largest hub charging', 'CHGL'), ('Any hub exporting', 'EXP'),
             ('Time of day + charging', 'TOD+CHG'), ('Clustering (best silhouette)', 'CL'), ('Best 2 groups', 'best_K2'),
             ('Best 4 groups', 'best_K4'), ('Best overall ($K^{*}$ groups)', 'BK'), ('Own settings per state', 'per_state')]
    val = {}
    for fd, _ in FEED:
        pol = J(f'value_{fd}.json')['policies']; R = pol['robust']
        for _, k in names:
            kk = f'best_K{kbest[fd]}' if k == 'BK' else k
            val[(fd, k)] = (100*(1 - pol[kk]['fault_duration_s_per_yr']/R['fault_duration_s_per_yr']),
                            100*(1 - pol[kk]['i2t_kA2s_per_yr']/R['i2t_kA2s_per_yr']))
    best = {(fd, j): max(round(val[(fd, k)][j], 1) for _, k in names) for fd, _ in FEED for j in (0, 1)}
    rows = []
    for lab, k in names:
        cells = []
        for j in (0, 1):
            for fd in ('33', '69'):
                v = round(val[(fd, k)][j], 1)
                cells.append(('\\best ' if v == best[(fd, j)] else '') + f(v, 1))
        rows.append(f"{lab} & " + ' & '.join(cells) + ' \\\\')
    open(T + 'tab_speed.tex', 'w').write('\n'.join(rows) + '\n')

def LABt(k):
    """compact variant label for the single-column stress table"""
    if k.startswith('mode Q'): return 'law Q'
    if k.startswith('mode MC'): return 'law MC'
    if k.startswith('k_f'):
        x = k.split('= ')[1]; return f'$k_f={x.split(",")[0]}$' + (', law Q' if 'mode Q' in x else '')
    if k.startswith('S_sc'): return '$S_\\mathrm{sc}=' + k.split('= ')[1].replace(' MVA', '$~MVA')
    if k.startswith('source X/R'): return 'source $X/R=' + k.split('= ')[1] + '$'
    if k.startswith('line Z0/Z1'): return 'line $Z_0/Z_1=' + k.split('= ')[1] + '$'
    return LAB(k)

def tab_stress():
    rows = []
    for fd, _ in FEED:
        S = J(f'stress_{fd}.json')['variants']
        rows.append(f'\\multicolumn{{7}}{{l}}{{\\emph{{IEEE {fd}-bus}}}} \\\\')
        for k, v in S.items():
            o = v['frozen']['outcomes']; n = sum(o.values())
            lost = sum(c for kk, c in o.items() if kk in ('2', '3', '4'))
            red = v['redesigned']
            rows.append(f"\\quad {LABt(k)} & {f(100*o.get('0',0)/n,2)} & {i(v['frozen']['short_margin'])} & {i(lost)} & "
                        f"{f(v['frozen']['mean_t']*1e3,1)} & {'yes' if red['all_selective'] else 'no'} & "
                        f"{f(red['mean_t']*1e3,1) if red['mean_t'] else '--'} \\\\")
        rows.append('\\midrule' if fd == '33' else '')
    open(T + 'tab_stress.tex', 'w').write('\n'.join(r for r in rows if r) + '\n')

# ================================================================ boundary sweep text
def boundary():
    S = J('sweep_33.json'); D = J('boundary_diag.json'); P33 = J('policies_33.json')
    pts = [v for v in S.values() if 'robust' in v]
    nolf = sorted(v['m'] for v in S.values() if 'robust' not in v)
    def get(ssc, kf, mm): return next((v for v in pts if v['ssc'] == ssc and v['kf'] == kf and v['m'] == mm), None)
    base = sorted((v['m'], v) for v in pts if v['ssc'] == 100.0 and v['kf'] == 1.2)
    ms = [x[0] for x in base]; sens = [x[1]['robust']['sens_backup_P'] for x in base]
    cross = None
    for (m0, s0), (m1, s1) in zip(zip(ms, sens), zip(ms[1:], sens[1:])):
        if s0 >= 1.2 > s1: cross = m0 + (s0 - 1.2)*(m1 - m0)/(s0 - s1)
    v1, v2 = get(100.0, 1.2, 1.0), get(100.0, 1.2, 2.0)
    vmin = {v['m']: v['volt']['vmin'] for v in pts if v['ssc'] == 100.0 and v['kf'] == 1.2}
    mvmax = max(vmin)
    rhomax = max(max(v['rho'].values()) for v in pts)
    sel_m = sorted({v['m'] for v in pts})
    ok_upto = max([mm for mm in sel_m if all(v['robust'].get('all_selective') for v in pts if v['m'] <= mm)], default=None)
    fail = [v for v in pts if not v['robust'].get('all_selective')]
    mfail = min((v['m'] for v in fail), default=None)
    def fm(x): return f(x, 0) if float(x).is_integer() else f(x, 1)
    txt = []
    txt.append(r"Figure~\ref{fig:boundary} scales all three hubs of the 33-bus feeder beyond the hosting limit, as if their voltage effect were compensated. Without such compensation the feeder leaves the $[0.90,1.05]$~pu band beyond one times the limit (minimum " +
               f(vmin[1.5], 3) + r"~pu at 1.5 times and " + f(vmin[mvmax], 3) + r"~pu at " + fm(mvmax) + r" times)" +
               (r", and beyond " + fm(max(vmin)) + r" times the power flow has no solution" if nolf else '') +
               r". Hub contributions then reach " + f(100*rhomax, 0) + r"\,\% of the local fault current.")
    t2 = []
    if ok_upto is not None:
        t2.append(r"The fixed design remains selective in every case up to " + fm(ok_upto) +
                  r" times the hosting limit, for every source strength and current limit.")
    t2.append(r"With a 100~MVA source and $k_f=1.2$, its mean clearing time rises from " + f(v1['robust']['mean_t']*1e3, 0) +
              r"~ms at the hosting limit to " + f(v2['robust']['mean_t']*1e3, 0) +
              r"~ms at twice the limit, because its phase pickups must ride through the larger charging load and its earth pickups rise with the larger CTs that load needs. Its smallest remote-backup sensitivity factor falls from " +
              f(v1['robust']['sens_backup_P'], 2) + r" to " + f(v2['robust']['sens_backup_P'], 2) +
              (r" and crosses the 1.2 requirement at about " + f(cross, 1) + r" times the limit." if cross else '.'))
    if mfail is not None:
        d = D.get(str(mfail), {}); bt = d.get('by_type', {})
        types = sorted(bt.items(), key=lambda kv: -kv[1])
        def tname(k):
            ft, R_, _ = k.split(' '); return {'SLG': 'single-line-to-ground', '3ph': 'three-phase', 'LL': 'line-to-line',
                                             'LLG': 'double-line-to-ground'}[ft] + f' faults through {R_}~$\\Omega$'
        rel = sorted(d.get('by_relay', {}).items(), key=lambda kv: -kv[1])
        r_main = rel[0][0] if rel else None
        ct0 = P33['ct'].get(r_main) if r_main else None; ct1 = d.get('ct', {}).get(r_main)
        allearth = all(k.startswith(('SLG', 'LLG')) for k in bt)
        t2.append(r"From " + fm(mfail) + r" times the limit the fixed design fails to trip: " + i(d.get('missed', 0)) +
                  r" of " + i(d.get('n_cases', 0)) + r" cases at " + fm(mfail) + r" times, " +
                  ('all of them ' if len(types) == 1 else '') + words([tname(k) for k, _ in types]) +
                  (r" in the zone of " + r_main if len(rel) == 1 else '') + '.')
        if allearth and ct0 and ct1 and ct1 > ct0:
            t2.append(r"Carrying the larger charging load raises the CT rating of " + r_main + r" from " + i(ct0) + r" to " +
                      i(ct1) + r"~A, and the earth pickup, tied to the CT rating, rises with it to " +
                      i(d['earth_pickup'][r_main]) + r"~A, above the residual current of these faults (at most " +
                      i(d['max_3I0_missed']) + r"~A).")
        d3 = D.get('3.0', {}); b3 = d3.get('by_type', {})
        other3 = {k: v for k, v in b3.items() if k not in bt}
        if other3:
            t2.append(r"At 3 times the limit " + words([f"{i(v)} {tname(k)}" for k, v in other3.items()]) +
                      r" are also missed, because the phase pickups must carry the charging load.")
    txt.append(' '.join(t2))
    t3 = []
    def gains(mm, key):
        out = []
        for v in pts:
            if v['m'] != mm or not v['robust'].get('all_selective'): continue
            if key == 'ps':
                if v['per_state'].get('all_selective'): out.append(100*(1 - v['per_state']['mean_t']/v['robust']['mean_t']))
            elif v['best'].get(key):
                out.append(100*(1 - v['best'][key]['mean_t']/v['robust']['mean_t']))
        return out
    W = {1.0: 'One', 1.5: 'Onefive', 2.0: 'Two'}
    anyone = gains(1.0, 'ps') + gains(1.0, '2') + gains(1.0, '4')
    m('SweepAnyOneHi', f(max(anyone), 1))
    have = {}
    for mm, w in W.items():
        for key, kw in (('ps', 'Gps'), ('2', 'Gb'), ('4', 'Gf')):
            g_ = gains(mm, key)
            if g_:
                have[(mm, key)] = (min(g_), max(g_))
                m('Sweep' + kw + w + 'Lo', f(min(g_), 1)); m('Sweep' + kw + w + 'Hi', f(max(g_), 1))
    if all(k in have for k in ((1.0, 'ps'), (1.0, '2'), (2.0, 'ps'), (2.0, '2'))):
        t3.append(r"Adaptation gains more as hubs grow. At the hosting limit, over the source strengths and current limits swept, own settings per state shorten the fixed design's mean clearing time by \SweepGpsOneLo--\SweepGpsOneHi\,\% and the best two-group policy by \SweepGbOneLo--\SweepGbOneHi\,\%." +
                  (r" At 1.5 times the limit these gains are \SweepGpsOnefiveLo--\SweepGpsOnefiveHi\,\% and \SweepGbOnefiveLo--\SweepGbOnefiveHi\,\%," if (1.5, 'ps') in have and (1.5, '2') in have else '') +
                  r" and at twice the limit \SweepGpsTwoLo--\SweepGpsTwoHi\,\% and \SweepGbTwoLo--\SweepGbTwoHi\,\%" +
                  (r" (four groups: \SweepGfTwoLo--\SweepGfTwoHi\,\%)" if (2.0, '4') in have else '') +
                  r", because the fixed design's phase pickups must then ride through a much larger charging load. These hubs are voltage-infeasible without support.")
    psinf = sorted({v['m'] for v in pts if not v['per_state'].get('feasible')})
    if mfail is not None:
        nopol = all(all(b is None for b in v['best'].values()) for v in pts if v['m'] >= mfail and not v['robust'].get('all_selective'))
        if nopol:
            t3.append(r"Where the fixed design fails to trip, no policy with up to four groups is fully selective either: the CT, and with it the earth pickup, does not change with the setting group, and in charging states every group must carry the same load." +
                      (r" Own settings per state cannot even be graded for every state there." if psinf and min(psinf) >= mfail else ''))
    elif psinf:
        t3.append(r"At some sweep points (from " + fm(min(psinf)) + r" times the limit) own settings per state cannot be graded for every state.")
    kfd = max(abs(get(sc, 2.0, mm)['robust']['mean_t']/get(sc, 1.2, mm)['robust']['mean_t'] - 1)
              for sc in (50.0, 100.0, 250.0) for mm in sel_m if get(sc, 2.0, mm) and get(sc, 1.2, mm))
    t3.append(r"The converter current limit matters little for the fixed design: raising $k_f$ from 1.2 to 2.0 changes its mean clearing time by at most " +
              f(100*kfd, 1) + r"\,\%.")
    txt.append(' '.join(t3))
    if mfail is not None:
        txt.append(r"Adaptation therefore buys speed only for hubs well beyond the hosting limit, made feasible by voltage support, and it is never what keeps the protection selective. Up to " + fm(ok_upto) +
                   r" times the limit the fixed design is selective on its own; beyond that, the binding problem is earth-fault sensitivity, which more setting groups cannot repair. The remedy there is a sensitive earth-fault element set independently of the CT rating, or a different backup principle.")
    fig = r"""
\begin{figure*}[t]
\centering
\includegraphics[width=\textwidth]{boundary.pdf}
\caption{Hubs scaled beyond the hosting limit (33-bus; grey: voltage-feasible without support). Top: mean primary clearing time of the fixed design, the best two-group policy and own settings per state (missing where no such design is fully selective or where single-state designs cannot be graded). Red region: the fixed design fails to trip some faults (hollow markers: mean over cleared faults only). Bottom: smallest remote-backup sensitivity factor of the fixed design.}
\label{fig:boundary}
\end{figure*}
"""
    open(T + 'boundary.tex', 'w').write('\n\n'.join(txt) + '\n' + fig)
    m('SweepCross', f(cross, 1) if cross else '--')
    m('SweepOK', fm(ok_upto) if ok_upto else '--')
    m('SweepFail', fm(mfail) if mfail else '--')

# ================================================================ off-path slack (both feeders)
def _slack_sentence():
    an = {fd: J(f'policies_{fd}.json')['robust_anatomy'] for fd, _ in FEED}
    sl = {fd: an[fd]['other_onpath_min_slack_s'] for fd, _ in FEED}
    c = {fd: an[fd]['other_onpath_min_slack_case'] for fd, _ in FEED}
    kdt = CURVE['k']/(CURVE['Mmax'] - 1)
    same = abs(sl['33'] - sl['69']) < 5e-5
    same_pair = (c['33']['other'] == c['69']['other'] and c['33']['primary_element'] == c['69']['primary_element'] ==
                 c['33']['other_element'] == c['69']['other_element'] and
                 c['33']['primary_TMS'] == c['69']['primary_TMS'] and c['33']['other_TMS'] == c['69']['other_TMS'])
    if not (same and same_pair and all(c[fd]['definite_time_both'] for fd in c)):
        return (r"Relays that are neither primary nor designated backup operate at least \SlackOtherA~ms (33-bus) and "
                r"\SlackOtherB~ms (69-bus) later than the margin would require.")
    a = c['33']; tp, to = a['primary_TMS'], a['other_TMS']
    assert abs(kdt*(to - (1 + E_MARG)*tp) - C_MARG - sl['33']) < 1e-9
    hub = all(c[fd]['primary'].startswith('H') and c[fd]['loc'].startswith('H') for fd in c)
    el = {'51N': 'earth', '51P': 'phase'}[a['other_element']]
    ft = {'SLG': 'a single-line-to-ground fault', 'LLG': 'a double-line-to-ground fault', 'LL': 'a line-to-line fault',
          '3ph': 'a three-phase fault'}[a['ftype']]
    where = 'at a hub terminal, cleared by the hub breaker' if hub else 'cleared by the primary relay'
    return (r"Relays that are neither primary nor designated backup operate at least \SlackOtherA~ms later than the margin "
            r"would require, on both feeders. The two minima are equal because on each feeder the smallest slack occurs for " + ft +
            r" " + where + r", during which " + role(a['other']) + r" also operates. Both relays then operate on the definite-time part of their " + el +
            r" characteristics, above " + f(CURVE['Mmax'], 0) + r" times pickup, and their time multipliers are the same on both feeders (" +
            f(tp, 2) + r" and " + f(to, 2) + r"). The slack, $\frac{" + f(CURVE['k'], 1) + r"}{" + f(CURVE['Mmax'] - 1, 0) + r"}(" + f(to, 2) +
            r"-" + f(1 + E_MARG, 1) + r"\times" + f(tp, 2) + r")-" + f(C_MARG, 2) + r"$~s, therefore does not depend on the fault current.")
m('SlackSentence', _slack_sentence())

# ================================================================ generated sentences
RULE_NAME = {'TOD': 'time-of-day rule', 'CHG': 'any-hub-charging rule', 'TOD+CHG': 'time-of-day-with-charging rule',
             'EXP': 'export-keyed rule'}
def rule_name(k): return RULE_NAME.get(k, f'hub-{k[3:]}-charging rule')
def polname2(kind, k):
    if kind == 'rule': return rule_name(k)
    if kind == 'cl':
        meth, K = k.split('_K'); return f'{K}-means partition' if meth == 'kmeans' else f'{K}-group Ward partition'
    return f'best {k}-group policy'
def feeders_txt(fds): return 'both feeders' if len(fds) == 2 else f'{fds[0]}-bus feeder'
PJ = {fd: J(f'policies_{fd}.json') for fd, _ in FEED}
VJ = {fd: J(f'value_{fd}.json') for fd, _ in FEED}
SJ = {fd: J(f'stress_{fd}.json') for fd, _ in FEED}
for fd, _ in FEED:                    # every policy must be fully selective in its own states
    P = PJ[fd]
    for a in [P['per_state']] + list(P['rules'].values()) + list(P['cluster'].values()) + \
             [v for v in P['exhaustive'].values() if v]:
        assert a['all_selective'], ('policy not fully selective', fd, a.get('name'))
r0 = {fd: PJ[fd]['robust']['mean_t'] for fd, _ in FEED}
gps = {fd: 100*(1 - PJ[fd]['per_state']['mean_t']/r0[fd]) for fd, _ in FEED}
to = {fd: J(f'tmsonly_{fd}.json')['gain_pct'] for fd, _ in FEED}
assert all(to[fd] < gps[fd] for fd, _ in FEED), 'TMS-only gain exceeds per-state gain: revise the Discussion'
if all(to[fd] < gps[fd] - 0.05 for fd, _ in FEED):
    m('TmsSentence', r"With the fixed design's pickups and instantaneous settings kept, separate time multipliers for every state shorten clearing by \TmsOnlyA\,\% and \TmsOnlyB\,\%; the rest of the per-state gain comes from pickups and instantaneous settings matched to each state.")
elif all(to[fd] >= gps[fd] - 0.05 for fd, _ in FEED):
    m('TmsSentence', r"Keeping the fixed design's pickups and instantaneous settings and adapting only the time multipliers to every state gains \TmsOnlyA\,\% and \TmsOnlyB\,\%, as much as own settings for every state or more: adapting pickups adds no speed here.")
else:
    m('TmsSentence', r"With the fixed design's pickups and instantaneous settings kept, separate time multipliers for every state shorten clearing by \TmsOnlyA\,\% and \TmsOnlyB\,\%.")
after = {fd: max(int(k) for k in PJ[fd]['exhaustive'] if PJ[fd]['exhaustive'][k]) > kbest[fd] and
         PJ[fd]['exhaustive']['9']['mean_t'] > PJ[fd]['exhaustive'][str(kbest[fd])]['mean_t'] + 1e-12 for fd, _ in FEED}
psslow = {fd: PJ[fd]['per_state']['mean_t'] > PJ[fd]['exhaustive'][str(kbest[fd])]['mean_t'] + 1e-12 for fd, _ in FEED}
slower = {fd: [rule_name(k) for k, a in PJ[fd]['rules'].items() if a['mean_t'] > r0[fd] + 1e-12] for fd, _ in FEED}
ft = r"Finer adaptation is not always faster."
if all(after.values()):
    ft += r" Beyond $K=\KbestA$ (33-bus) and $K=\KbestB$ (69-bus) groups the best policy slows down again"
    ft += r", and own settings for every state are slower than the best policy found." if all(psslow.values()) else "."
ft += r" Each group's pickups and instantaneous settings follow the rules for its own states rather than being optimised, so a smaller group is not guaranteed a faster design"
sl = [f"the {words(v)} on the {fd}-bus feeder" for fd, v in slower.items() if v]
nsl = sum(len(v) for v in slower.values())
ft += ('; ' + words(sl) + (' is' if nsl == 1 else ' are') +
       r" even slightly slower than the fixed design (Table~\ref{tab:policies})." if sl else '.')
m('FinerSentence', ft if (any(after.values()) or any(psslow.values()) or sl) else '')
inf2 = {fd: info_needed(PJ[fd]['exhaustive']['2']['groups'], scenarios(tuple(sorted(int(b) for b in PJ[fd]['hubs']))))
        for fd, _ in FEED}
apart = all(not any(0 in b and 8 in b for b in PJ[fd]['exhaustive']['2']['class_blocks']) for fd, _ in FEED)
if all(v == 'clock, hub status' for v in inf2.values()) and apart:
    m('InfoTwoSentence', r"Because peak-load states are grouped apart from light-load states with no hub charging, either policy needs the clock as well as hub status.")
elif all(v == 'hub status' for v in inf2.values()):
    m('InfoTwoSentence', r"Either policy needs only hub status.")
else:
    m('InfoTwoSentence', r"Operating them needs " + words(sorted(set(inf2.values()))) + '.')
ct = []
for fd, _ in FEED:
    byrule = {}
    for k, a in PJ[fd]['cluster'].items():
        for rr in a['matches_rules']: byrule.setdefault(rr, []).append((k, a))
    for rr, lst in byrule.items():
        meths = words(sorted({'two-cluster $k$-means' if k.startswith('kmeans') else 'two-cluster Ward clustering'
                              for k, a in lst})) if all(a['K'] == 2 for k, a in lst) else words(sorted(k for k, _ in lst))
        ari = min(a['stability_ari_mean'] for k, a in lst); tt = lst[0][1]['mean_t']
        ct.append(f"On the {fd}-bus feeder, {meths} reproduce{'s' if len(lst) == 1 else ''} the {rule_name(rr)} exactly; "
                  f"this partition is stable (bootstrap adjusted Rand index {'of ' + f(ari, 2) if ari >= 0.995 else 'of at least ' + f(ari, 2)}) but "
                  + ('no faster than' if tt >= r0[fd] - 1e-12 else 'only slightly faster than') + ' the fixed design.')
m('ClusterTodSentence', ' '.join(ct))
m("ClusterSentence", r"never more than the best policy with the same number of groups." if clus_never_better else
  r"in some cases more than the best class-preserving policy with the same number of groups, because they split load classes.")
zero = {}
for fd, _ in FEED:
    P = PJ[fd]
    pols = [('rule', k, a) for k, a in P['rules'].items()] + [('cl', k, a) for k, a in P['cluster'].items()] + \
           [('best', k, a) for k, a in P['exhaustive'].items() if a and int(k) > 1]
    for kind, k, a in pols:
        wg = a.get('wrong_group')
        if wg and wg['total'].get('3', 0) == 0 and wg['encroach_total'] == 0:
            zero.setdefault(polname2(kind, k), []).append(fd)
if zero:
    one = len(zero) == 1
    m('ZeroFtSentence', 'Only ' + words([f'the {n} ({feeders_txt(v)})' for n, v in zero.items()]) +
      (' causes' if one else ' cause') + ' no false trip under the wrong group: ' + ('its' if one else 'their') +
      ' pickups still exceed the load of every state ' + ('it meets.' if one else 'they meet.'))
else:
    m('ZeroFtSentence', 'Every adaptive policy causes false trips under the wrong group.')
m('TripPHi', f(max(100*max(VJ[fd]['policies'][k].get('trip_prob_per_mismatch', 0) for k in VJ[fd]['policies'])
                   for fd, _ in FEED), 0))
if lost == 0:
    st_ = r"In none of the \StressN{} variants on either feeder does an upstream or off-path relay clear first, and no fault goes undetected."
    worst = max(((fd, k, v['frozen']['short_margin']) for fd, _ in FEED for k, v in SJ[fd]['variants'].items()), key=lambda x: x[2])
    st_ += (r" The only effect is a margin shortfall in some cases, under \StressWhere; the largest, " + i(worst[2]) +
            r" cases (" + f(100*worst[2]/sum(SJ[worst[0]]['variants'][worst[1]]['frozen']['outcomes'].values()), 1) +
            r"\,\%), occurs on the " + worst[0] + r"-bus feeder with " + LAB(worst[1]).replace(' = ', '~$=$~') + r"." if max(short) > 0
            else r" Every case remains selective with the margin met.")
else:
    st_ = r"Over all variants the frozen designs lose \StressLost{} cases to selectivity loss, false trips or failures to trip."
m('StressSentence', st_)
worst = max(((fd, k, v['frozen']['short_margin'], sum(v['frozen']['outcomes'].values())) for fd, _ in FEED
             for k, v in SJ[fd]['variants'].items()), key=lambda x: x[2])
assert worst[1].startswith('S_sc'), 'abstract assumes the worst shortfall is a source-strength variant'
m('StressShortPct', f(100*worst[2]/worst[3], 1)); m('StressShortFd', worst[0])
m('StressShortVar', LAB(worst[1]).replace('$S_\\mathrm{sc}$ = ', '').replace(' MVA', '~MVA'))
wv = SJ[worst[0]]['variants'][worst[1]]['frozen']
assert 'ct_beyond_alf' in wv, 'rerun run_stress.py'
m('StressCTn', i(len(wv['ct_beyond_alf']))); m('StressCTtot', i(len(SJ[worst[0]]['base_ct'])))
m('StressCTmax', f(wv['max_current_over_ct'], 0))
beyond = {(fd, k): v['frozen']['ct_beyond_alf'] for fd, _ in FEED for k, v in SJ[fd]['variants'].items()
          if v['frozen']['ct_beyond_alf']}
short_no_ct = [(fd, k) for fd, _ in FEED for k, v in SJ[fd]['variants'].items()
               if v['frozen']['short_margin'] > 0 and not v['frozen']['ct_beyond_alf']]
def LABw(k):
    """variant as a phrase after 'with'"""
    if k.startswith('S_sc'): return 'a ' + k.split('= ')[1].replace(' MVA', '~MVA') + ' source'
    if k.startswith('k_f'):
        x = k.split('= ')[1]
        return f'$k_f={x.split(",")[0]}$' + (' and law Q' if 'mode Q' in x else '')
    return LAB(k).replace(' = ', '~$=$~')
big = [(fd, k) for (fd, k) in beyond if len(beyond[(fd, k)]) >= 3]
small = {}
for (fd, k), rl in beyond.items():
    if len(rl) < 3:
        for r in rl: small.setdefault((fd, r), []).append(k)
def _variants_or(ks):
    """'law Q, k_f = 2.0 or both' when the combined variant is listed with its two parts"""
    comb = [k for k in ks if ', mode Q' in k and k.split(',')[0] in ks and any(x.startswith('mode Q') for x in ks)]
    rest = [LABw(k) for k in ks if k not in comb]
    return (', '.join(rest) + ' or both') if comb else words(rest, 'or')
parts = []
byvar = {}
for fd, k in big: byvar.setdefault(k, []).append(fd)
for k, fds in byvar.items():
    cm = max(SJ[fd]['variants'][k]['frozen']['max_current_over_ct'] for fd in fds)
    parts.append(words([f"{nw(len(beyond[(fd, k)]))} of the {nw(len(SJ[fd]['base_ct']))} on the {fd}-bus feeder" for fd in fds])
                 + ' with ' + LABw(k) + f' (up to {f(cm, 0)} times rating)')
for (fd, r), ks in small.items():
    parts.append('the CT of ' + r + f' on the {fd}-bus feeder with ' + _variants_or(ks))
cmax = max(SJ[fd]['variants'][k]['frozen']['max_current_over_ct'] for fd, k in beyond) if beyond else 0
m('StressCTSentence', (r"The frozen evaluation is also optimistic wherever fault currents grow, because the largest fault current then exceeds " +
                       f(CT_ALF, 0) + r" times the rating of some frozen CTs: " + (', and '.join(parts) if len(parts) == 2 else words(parts)) + r". Beyond this accuracy-limit factor the 5\,\% composite error of a 5P20 CT is no longer guaranteed, so the operating times of these relays, and the margins in which they take part, are less certain than the frozen evaluation assumes.")
  if beyond else '')
m('StressShortNoCT', words([f"{LAB(k)} ({fd}-bus)" for fd, k in short_no_ct]) if short_no_ct else 'none')
v250 = {fd: SJ[fd]['variants']['S_sc = 250 MVA'] for fd, _ in FEED}
slow250 = all(v250[fd]['redesigned']['mean_t'] and v250[fd]['redesigned']['mean_t'] > r0[fd] for fd, _ in FEED)
ctup = all(all(v250[fd]['redesigned_ct'][r] >= SJ[fd]['base_ct'][r] for r in SJ[fd]['base_ct']) and
           v250[fd]['redesigned_ct']['R1'] > SJ[fd]['base_ct']['R1'] for fd, _ in FEED)
if slow250 and ctup:
    m('StrongSentence', r"A stronger source makes the redesigned fixed design slower (" +
      words([f"{f(r0[fd]*1e3, 0)} to {f(v250[fd]['redesigned']['mean_t']*1e3, 0)}~ms on the {fd}-bus feeder" for fd, _ in FEED]) +
      r" with 250~MVA). The higher fault currents need larger CTs to stay within 20 times rating (the feeder breaker's rises from " +
      (f"{i(SJ['33']['base_ct']['R1'])} to {i(v250['33']['redesigned_ct']['R1'])}~A on both feeders"
       if all(SJ[fd]['base_ct']['R1'] == SJ['33']['base_ct']['R1'] and v250[fd]['redesigned_ct']['R1'] == v250['33']['redesigned_ct']['R1'] for fd, _ in FEED)
       else words([f"{i(SJ[fd]['base_ct']['R1'])} to {i(v250[fd]['redesigned_ct']['R1'])}~A on the {fd}-bus feeder" for fd, _ in FEED])) +
      r"), so the pickups tied to CT rating (the earth pickups and the phase-pickup floor) rise with them, and high-resistance faults operate closer to pickup, further down the inverse-time curve.")
else:
    m('StrongSentence', '')
zv = {}
for fd, _ in FEED:
    for k, r in VJ[fd]['policies'].items():
        if k == 'robust': continue
        if r.get('trip_prob_per_mismatch', 0) == 0 and r.get('ens_per_mismatch', 0) == 0:
            zv.setdefault(k, []).append(fd)
VNAME = {'TOD': 'time-of-day rule', 'CHG': 'any-hub-charging rule', 'CHGL': 'largest-hub-charging rule',
         'TOD+CHG': 'time-of-day-with-charging rule', 'EXP': 'export-keyed rule', 'CL': 'clustered policy',
         'per_state': 'own settings per state'}
def vname(k): return VNAME.get(k, f"best {k.split('K')[-1]}-group policy")
if zv:
    m('ZeroValueSentence', 'The ' + words([f'{vname(k)} ({feeders_txt(v)})' for k, v in zv.items()]) +
      (' has' if len(zv) == 1 else ' have') + ' no load-trip exposure, and also no reliability gain.')
else:
    m('ZeroValueSentence', '')

tab_hubs(); tab_settings('33'); tab_policies(); tab_stress(); tab_speed(); boundary()
m('PsFastest', 'yes' if all(psfast.values()) else 'no')
with open(T + 'numbers.tex', 'w') as fh:
    fh.write('% generated by src/make_tex.py from results/*.json -- do not edit\n')
    for k, v in M.items():
        fh.write(f'\\newcommand{{\\{k}}}{{{v}}}\n')
print(len(M), 'macros written; tables written')
