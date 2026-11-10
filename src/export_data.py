"""export_data.py — the data behind every table and figure, as one Excel workbook
and as CSV files for the MATLAB figure scripts.

usage: python export_data.py
  -> data/GTD_V2G_data.xlsx  (README, benchmark feeder data, modelling inputs,
                              Tables 1-8, data of Figs 2-6, value grid)
  -> data/csv/fig*.csv       (tidy data read by matlab/fig*.m)

Everything is read from results/*.json (and the benchmark data in grid.py), so the
workbook always matches the manuscript. Raw values are written at full precision
in blue; derived columns are Excel formulas (black) that recompute from them.
"""
import os, sys, csv, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES
from grid import feeder_data
from cases import LAYOUTS
from params import VLL, CONVERTER, CHARGER_KW
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data'); CSV = os.path.join(OUT, 'csv')
FEED = ('33', '69')
REPO = 'https://github.com/Mubashar-3001/Protection-aware33-69bus'
def J(n): return json.load(open(os.path.join(RES, n)))

SRC = {
    'bw33': 'M. E. Baran, F. F. Wu, Network reconfiguration in distribution systems for loss reduction and load '
            'balancing, IEEE Trans. Power Delivery 4(2) (1989) 1401-1407, doi:10.1109/61.25627',
    'bw69': 'M. E. Baran, F. F. Wu, Optimal capacitor placement on radial distribution systems, IEEE Trans. Power '
            'Delivery 4(1) (1989) 725-734, doi:10.1109/61.19265',
    'rbts': 'R. N. Allan et al., A reliability test system for educational purposes - basic distribution system data '
            'and results, IEEE Trans. Power Systems 6(2) (1991) 813-820, doi:10.1109/59.76730',
    'vcr': 'Australian Energy Regulator, Values of customer reliability: 2024 VCR review, final report (Dec. 2024)',
    'npag': 'Alstom Grid, Network Protection & Automation Guide, Stafford, UK, 2011',
    'iec61869': 'IEC 61869-2:2012 Instrument transformers - Part 2 (class 5P20)',
    'iec60255': 'IEC 60255-151:2009 Measuring relays and protection equipment - Part 151 (very-inverse curve)',
    'iec60076': 'IEC 60076-5:2006 Power transformers - Part 5 (minimum short-circuit impedance)',
}

# ------------------------------------------------------------------ styles
ARIAL = 'Arial'
F_DATA = Font(name=ARIAL, size=10, color='0000FF')        # hard-coded values (from the simulations)
F_FORM = Font(name=ARIAL, size=10, color='000000')        # formulas
F_TEXT = Font(name=ARIAL, size=10, color='000000')
F_HEAD = Font(name=ARIAL, size=10, bold=True)
F_TITLE = Font(name=ARIAL, size=12, bold=True)
F_NOTE = Font(name=ARIAL, size=9, italic=True, color='595959')
FILL_HEAD = PatternFill('solid', start_color='D9D9D9')
THIN = Side(style='thin', color='A6A6A6')
B_HEAD = Border(bottom=THIN, top=THIN)


class Sheet:
    """writes a titled sheet with one or more tables; tracks the next free row."""
    def __init__(self, wb, name, title, notes=()):
        self.ws = wb.create_sheet(name); self.r = 1
        self.ws.cell(1, 1, title).font = F_TITLE; self.r = 2
        for n in notes:
            self.ws.cell(self.r, 1, n).font = F_NOTE; self.r += 1
        self.r += 1; self.widths = {}

    def table(self, header, rows, fmt=None, subtitle=None, freeze=False):
        """rows: lists of values; a value that is a str starting with '=' is a formula.
        fmt: list of number formats per column (None = general). Returns (first_row, last_row)."""
        ws = self.ws
        if subtitle:
            ws.cell(self.r, 1, subtitle).font = F_HEAD; self.r += 1
        for c, h in enumerate(header, 1):
            cell = ws.cell(self.r, c, h); cell.font = F_HEAD; cell.fill = FILL_HEAD; cell.border = B_HEAD
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            self.widths[c] = max(self.widths.get(c, 0), min(28, len(str(h)) + 2))
        if freeze: ws.freeze_panes = ws.cell(self.r + 1, 1)
        hr = self.r; self.r += 1; first = self.r
        for row in rows:
            for c, v in enumerate(row, 1):
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): v = None
                cell = ws.cell(self.r, c, v)
                if isinstance(v, str) and v.startswith('='): cell.font = F_FORM
                elif isinstance(v, (int, float)) and not isinstance(v, bool): cell.font = F_DATA
                else: cell.font = F_TEXT
                if fmt and fmt[c - 1] and not (isinstance(v, str) and not v.startswith('=')): cell.number_format = fmt[c - 1]
                if isinstance(v, str) and not v.startswith('='):
                    self.widths[c] = max(self.widths.get(c, 0), min(60, len(v) + 2))
                else:
                    self.widths[c] = max(self.widths.get(c, 0), 11)
            self.r += 1
        last = self.r - 1; self.r += 1
        return hr, first, last

    def note(self, text):
        self.ws.cell(self.r, 1, text).font = F_NOTE; self.r += 1

    def finish(self):
        for c, w in self.widths.items():
            self.ws.column_dimensions[get_column_letter(c)].width = w


def write_csv(name, header, rows):
    with open(os.path.join(CSV, name), 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(header)
        for r in rows:
            w.writerow(['' if (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) or v is None else
                        (f'{v:.6g}' if isinstance(v, float) else v) for v in r])


def main():
    os.makedirs(CSV, exist_ok=True)
    wb = Workbook(); wb.remove(wb.active)
    P = {fd: J(f'policies_{fd}.json') for fd in FEED}; V = {fd: J(f'value_{fd}.json') for fd in FEED}
    H = {fd: J(f'hosting_{fd}.json') for fd in FEED}; S = {fd: J(f'stress_{fd}.json') for fd in FEED}
    I = {fd: J(f'impact_{fd}.json') for fd in FEED}; G = {fd: J(f'groups_{fd}.json') for fd in FEED}
    VM = J('verify_model.json')
    kbest = {fd: min((int(k) for k, v in P[fd]['exhaustive'].items() if v),
                     key=lambda k: P[fd]['exhaustive'][str(k)]['mean_t']) for fd in FEED}

    # ============================================================== README
    rd = wb.create_sheet('README'); rows = [
        ('Protection-aware integration of vehicle-to-grid charging hubs: when do directional overcurrent relays need adaptive setting groups?', F_TITLE),
        ('Data behind every table and figure of the manuscript (M. Javed, M. Wagner, L. Khan).', F_TEXT),
        (f'Generated by src/export_data.py from results/*.json; the code and results are released at {REPO}.', F_TEXT),
        ('Do not edit by hand: rerun python src/run_all.py and python src/export_data.py to regenerate.', F_TEXT),
        ('', F_TEXT),
        ('Colour code: blue = value computed by the simulation code (or benchmark/sourced input); black = Excel formula derived from the blue cells.', F_TEXT),
        ('Units are given in every column header. Percentages are stored as fractions and displayed with %.', F_TEXT),
        ('', F_TEXT), ('Sheets', F_HEAD)]
    sheets = [
        ('Feeder_33', 'IEEE 33-bus benchmark: branch impedances and peak loads [B]', SRC['bw33']),
        ('Feeder_69', 'IEEE 69-bus benchmark: branch impedances and peak loads [B]', SRC['bw69']),
        ('Relays', 'Relay layout: protected branch, designated backup and CT rating of every relay', 'results/policies_*.json'),
        ('T1_Hubs', 'Table 1: hosting-feasible hubs (Ir, kf*Ir and rho recomputed by formula)', 'results/hosting_*.json'),
        ('T2_Inputs', 'Table 2: every modelling input with its tag ([B] benchmark, [S] sourced, [A] assumption) and source', 'see Source column'),
        ('T3_Settings33', 'Table 3: fixed settings, 33-bus feeder', 'results/policies_33.json'),
        ('T4_Policies', 'Table 4: setting-group policies (gain recomputed by formula)', 'results/policies_*.json, value_*.json'),
        ('T5_Stress', 'Table 5: fixed designs under alternative assumptions, incl. CTs beyond their accuracy limit', 'results/stress_*.json'),
        ('T6_Speed', 'Table 6: speed-sensitive measures (reductions recomputed by formula)', 'results/value_*.json'),
        ('T7_Settings69', 'Table 7 (appendix): fixed settings, 69-bus feeder', 'results/policies_69.json'),
        ('T8_Groups', 'Table 8 (appendix): settings of both groups of the best two-group policies', 'results/groups_*.json'),
        ('Fig2_Hosting', 'Fig. 2: single-hub hosting limits and the hub ratings used', 'results/hosting_*.json'),
        ('Fig3_Impact', 'Fig. 3: change of primary/backup relay current vs. all hubs off', 'results/impact_*.json'),
        ('Fig4_PolicySize', 'Fig. 4: mean clearing time vs. number of setting groups', 'results/policies_*.json'),
        ('Fig5_GainRisk', 'Fig. 5: gain vs. expected energy lost per wrong-group event', 'results/policies_*.json, value_*.json'),
        ('Fig6_Boundary', 'Fig. 6: hubs scaled beyond the hosting limit (33-bus sweep)', 'results/sweep_33.json'),
        ('Value_Grid', 'Annual value of adaptation (A$/yr) for every mismatch rate and event length', 'results/value_*.json'),
    ]
    for name, desc, src in sheets:
        rows.append((f'{name}: {desc}. Source: {src}', F_TEXT))
    rows += [('', F_TEXT), ('Sources of benchmark and sourced data', F_HEAD)] + [(v, F_TEXT) for v in SRC.values()]
    rows += [('', F_TEXT), ('Fig. 1 (one-line diagrams) is not data-driven; its editable sources are in diagrams/ (draw.io and Graphviz).', F_TEXT)]
    for k, (t, fnt) in enumerate(rows, 1):
        rd.cell(k, 1, t).font = fnt
    rd.column_dimensions['A'].width = 150

    # ============================================================== feeders
    for fd in FEED:
        BR, PL, QL, bench = feeder_data(fd)
        sh = Sheet(wb, f'Feeder_{fd}', f'IEEE {fd}-bus feeder (12.66 kV) [B]',
                   (f'Source: {SRC["bw33" if fd == "33" else "bw69"]}', 'Bus 1 is the substation (source) bus. Loads are the benchmark peak loads; light load is 40 % of peak [A].'))
        sh.table(['Branch', 'From bus', 'To bus', 'R (ohm)', 'X (ohm)'],
                 [[k + 1, f, t, r, x] for k, (f, t, r, x) in enumerate(BR)], [None, None, None, '0.0000', '0.0000'],
                 subtitle='Branches', freeze=True)
        buses = sorted(set(PL) | set(QL))
        sh.table(['Bus', 'P (kW)', 'Q (kvar)'], [[b, PL.get(b, 0.0), QL.get(b, 0.0)] for b in buses],
                 [None, '0.00', '0.00'], subtitle='Peak loads')
        v = VM[f'V1_{fd}']
        sh.table(['Quantity', 'Published', 'This model'],
                 [['Total losses (kW)', bench['loss_kW'], v['loss_kW']], ['Minimum voltage (pu)', bench['vmin'], v['vmin']],
                  ['Bus of minimum voltage', bench['vmin_bus'], bench['vmin_bus']]],
                 [None, '0.0000', '0.0000'], subtitle='Benchmark check (results/verify_model.json)')
        sh.finish()

    # ============================================================== inputs (Table 2)
    sh = Sheet(wb, 'T2_Inputs', 'Table 2. Modelling inputs', ('[B] benchmark data, [S] sourced, [A] assumption; dagger = varied in the stress tests.',))
    inp = [
        ('Feeders', 'B', 'IEEE 33- and 69-bus, 12.66 kV', SRC['bw33'] + '; ' + SRC['bw69']),
        ('Upstream grid (varied)', 'A', '100 MVA, X/R = 10, Zs0 = Zs1', 'assumption'),
        ('Line zero sequence (varied)', 'A', 'Z0 = 3 Z1', 'assumption (cf. Kersting 2017)'),
        ('Load levels', 'A', 'peak (benchmark) and light (40 % of peak)', 'assumption'),
        ('Hosting limits', 'A', 'V in [0.90, 1.05] pu; branch current <= 300 A', 'assumption'),
        ('Hubs', 'A', f'{CHARGER_KW:.0f} kW chargers, unity power factor; cable 0.05+j0.03 ohm; Dyn transformer rated above P/0.95', 'assumption'),
        ('Hub envelope', 'A', 'charge at light load only; export or off at peak', 'assumption'),
        ('Converter (varied)', 'A', f"law {CONVERTER['mode']}, kf = {CONVERTER['kf']}; laws Q and MC; kf 1.0-2.0; phase hold below 0.2 pu", 'assumption (cf. Keller & Kroposki 2010; IEEE 1547-2018)'),
        ('Directional elements', 'A', 'characteristic angles 45 deg (positive sequence), 60 deg (negative and zero sequence)', 'assumption'),
        ('Relays', 'S/A', 'IEC very inverse, definite time above 20x; TMS 0.05-1.00 step 0.01; 50/50N operate time 30 ms', SRC['iec60255']),
        ('Pickups and 50 reach', 'A', 'phase 1.25x gross forward load; earth 10 % CT; 50 at 1.3x largest fault beyond zone', 'assumption'),
        ('CTs', 'S', 'smallest standard rating carrying the load with the largest fault current within 20x rating (5P20)', SRC['iec61869']),
        ('LV transformers', 'S/A', 'R10 rating above 1.25x load; impedance per IEC 60076-5; X/R = 5', SRC['iec60076']),
        ('Grading margin', 'S/A', 'tb >= 1.2 tp + 0.11 s: ER = 5 %, ECT = 10 %, tCB = 60 ms, to = 20 ms, ts = 30 ms', SRC['npag']),
        ('Fault rate, repair, switching', 'S', f"{V['33']['params']['lam_per_km']} /km-yr, {V['33']['params']['r_rep']:.0f} h, {V['33']['params']['r_sw']:.0f} h; length = |Z| / {V['33']['params']['ohm_per_km']} ohm/km [A]", SRC['rbts']),
        ('Fault-type shares', 'A', '70/15/10/5 % (SLG/LL/LLG/3ph)', 'assumption'),
        ('State probabilities', 'A', 'peak 30 % of hours; per hub: peak off/export 0.6/0.4; light off/charge/export 0.5/0.4/0.1', 'assumption'),
        ('Mismatch events (varied)', 'A', 'n in {0, 1, 10, 100} per year of h in {0.25, 1, 4} h', 'assumption'),
        ('Margin-shortfall conversion', 'A', f"Monte Carlo, {V['33']['params']['mc']} draws per case, errors uniform within the margin bounds", 'assumption'),
        ('Customer reliability value', 'S', 'A$34.39-41.48/kWh (commercial overall / residential, 2024)', SRC['vcr']),
    ]
    sh.table(['Input', 'Tag', 'Value', 'Source'], [list(x) for x in inp], freeze=True)
    sh.finish()

    # ============================================================== relays
    sh = Sheet(wb, 'Relays', 'Relay layout and CT ratings', ('R: feeder breaker / trunk recloser, L: lateral recloser, H: hub breaker. Backup: designated backup relay.',))
    rows = []
    for fd in FEED:
        for r, (f, t) in LAYOUTS[fd]['relays'].items():
            rows.append([fd, r, f, t, P[fd]['backup'].get(r) or '-', P[fd]['ct'][r]])
        # hub breakers are added by cases.Layout from the hub list
        for r in P[fd]['relays']:
            if r not in LAYOUTS[fd]['relays']:
                rows.append([fd, r, int(r[1:]), f'hub terminal H{r[1:]}', P[fd]['backup'].get(r) or '-', P[fd]['ct'][r]])
    sh.table(['Feeder', 'Relay', 'From bus', 'To bus', 'Designated backup', 'CT primary (A)'], rows,
             [None, None, None, None, None, '0'], freeze=True)
    sh.finish()

    # ============================================================== Table 1 hubs
    sh = Sheet(wb, 'T1_Hubs', 'Table 1. Hosting-feasible hubs', (
        'Ir, kf*Ir and rho are formulas: Ir = P / (sqrt(3) * V_LL); kf*Ir = kf * Ir; rho = kf*Ir / Isc. Isc: bolted three-phase fault current at the hub bus, all hubs off.',
        'dV/V: the hub\'s own voltage change (alone, light load, off -> charging); cos(theta): power factor of the Thevenin impedance; rho_hat: first-order estimate kf*(dV/V)/cos(theta).'))
    ws = sh.ws
    ws.cell(sh.r, 1, 'V_LL (kV)').font = F_HEAD; ws.cell(sh.r, 2, VLL/1e3).font = F_DATA; vrow = sh.r; sh.r += 1
    ws.cell(sh.r, 1, 'kf').font = F_HEAD; ws.cell(sh.r, 2, CONVERTER['kf']).font = F_DATA; krow = sh.r; sh.r += 1
    ws.cell(sh.r, 1, 'Charger rating (MW)').font = F_HEAD; ws.cell(sh.r, 2, CHARGER_KW/1e3).font = F_DATA; crow = sh.r; sh.r += 2
    sh.widths[1] = max(sh.widths.get(1, 0), 21)
    rows = []; r0 = sh.r + 1
    for fd in FEED:
        for b, h in H[fd]['hubs'].items():
            rr = r0 + len(rows)
            rows.append([fd, int(b), h['chargers'], f'=C{rr}*$B${crow}', f'=D{rr}*1000/(SQRT(3)*$B${vrow})',
                         f'=$B${krow}*E{rr}', h['Isc_local_A'], f'=F{rr}/G{rr}', h['dv'], h['cos_theta'], h['rho_pred']])
            assert abs(h['P_MW'] - h['chargers']*CHARGER_KW/1e3) < 1e-9
    sh.table(['Feeder', 'Bus', 'Chargers', 'P (MW)', 'Ir (A)', 'kf*Ir (A)', 'Isc (A)', 'rho', 'dV/V', 'cos(theta)', 'rho_hat'], rows,
             [None, None, None, '0.00', '0.0', '0.0', '0', '0.0%', '0.0%', '0.00', '0.0%'])
    sh.finish()

    # ============================================================== settings tables
    def settings_sheet(fd, name, title):
        sh = Sheet(wb, name, title, ('Primary amperes. Empty I50: instantaneous element disabled because no reach remains.',))
        rows = []
        for r, s in P[fd]['robust_settings'].items():
            rows.append([r, P[fd]['backup'][r] or '-', s['CT'], s['IsP'], s['TMSP'], s['I50P'], s['IsN'], s['TMSN'], s['I50N']])
        sh.table(['Relay', 'Backup', 'CT (A)', 'Is phase (A)', 'TMS phase', 'I50 phase (A)', 'Is earth (A)', 'TMS earth', 'I50 earth (A)'],
                 rows, [None, None, '0', '0.0', '0.00', '0', '0.0', '0.00', '0'], freeze=True)
        sh.finish()
    settings_sheet('33', 'T3_Settings33', 'Table 3. Fixed settings, IEEE 33-bus feeder')
    settings_sheet('69', 'T7_Settings69', 'Table 7. Fixed settings, IEEE 69-bus feeder')

    # ============================================================== Table 4 policies
    names = [('Fixed (one group)', 'robust'), ('Time of day', 'TOD'), ('Any hub charging', 'CHG'), ('Largest hub charging', 'CHGL'),
             ('Any hub exporting', 'EXP'), ('Time of day + charging', 'TOD+CHG'), ('Clustering (best silhouette)', 'CL'),
             ('Best 2 groups', 'B2'), ('Best 4 groups', 'B4'), ('Best overall (K* groups)', 'BK'), ('Own settings per state', 'PS')]
    def look(fd, k):
        p = P[fd]; big = [x for x in p['rules'] if x.startswith('CHG') and x != 'CHG'][0]
        a = {'robust': p['robust'], 'TOD': p['rules']['TOD'], 'CHG': p['rules']['CHG'], 'CHGL': p['rules'][big],
             'EXP': p['rules']['EXP'], 'TOD+CHG': p['rules']['TOD+CHG'], 'CL': p['cluster'][p['cluster_best_by_silhouette']],
             'B2': p['exhaustive']['2'], 'B4': p['exhaustive']['4'], 'BK': p['exhaustive'][str(kbest[fd])], 'PS': p['per_state']}[k]
        vk = {'robust': 'robust', 'TOD': 'TOD', 'CHG': 'CHG', 'CHGL': 'CHGL', 'EXP': 'EXP', 'TOD+CHG': 'TOD+CHG', 'CL': 'CL',
              'B2': 'best_K2', 'B4': 'best_K4', 'BK': f'best_K{kbest[fd]}', 'PS': 'per_state'}[k]
        return a, V[fd]['policies'][vk]
    sh = Sheet(wb, 'T4_Policies', 'Table 4. Setting-group policies', (
        't: mean primary clearing time over all cases of the own states. Gain = 1 - t / t(fixed) (formula).',
        'False trips: share of cases cleared by an off-path relay under the wrong group. Lost energy: expected unserved energy per mismatch event from relays tripping on load (restored after the 1 h switching time).',
        f"K* = {kbest['33']} (33-bus) and {kbest['69']} (69-bus)."))
    rows = []; r0 = sh.r + 1; fixed_row = r0
    for lab, k in names:
        rr = r0 + len(rows); row = [lab]
        for fd in FEED:
            a, v = look(fd, k)
            wg = a.get('wrong_group')
            ft = (wg['total'].get('3', 0)/sum(wg['total'].values())) if wg else None
            row += [a['K'], a['mean_t']*1e3, ft, (v.get('ens_per_mismatch')/1e3 if 'ens_per_mismatch' in v else None)]
        # gains as formulas
        row.insert(3, f'=1-C{rr}/C${fixed_row}'); row.insert(8, f'=1-H{rr}/H${fixed_row}')
        rows.append(row)
    sh.table(['Policy', 'K (33)', 't 33 (ms)', 'Gain 33', 'False trips 33', 'Lost energy 33 (MWh)',
              'K (69)', 't 69 (ms)', 'Gain 69', 'False trips 69', 'Lost energy 69 (MWh)'], rows,
             [None, '0', '0.0', '0.0%', '0.0%', '0.00', '0', '0.0', '0.0%', '0.0%', '0.00'], freeze=True)
    sh.finish()

    # ============================================================== Table 5 stress
    sh = Sheet(wb, 'T5_Stress', 'Table 5. Fixed designs under alternative assumptions', (
        'Frozen: base-case fixed design re-evaluated without redesign (nominal operating times, ideal CTs). Margin met = share of cases selective with the margin met (formula).',
        'CTs beyond ALF: frozen CTs whose largest fault current under the variant exceeds 20 x rating (accuracy-limit factor of a 5P20 CT).'))
    rows = []; r0 = sh.r + 1
    for fd in FEED:
        for k, v in S[fd]['variants'].items():
            o = v['frozen']['outcomes']; n = sum(o.values()); rr = r0 + len(rows)
            lost = sum(c for kk, c in o.items() if kk in ('2', '3', '4'))
            rows.append([fd, k, n, o.get('0', 0), f'=D{rr}/C{rr}', v['frozen']['short_margin'], lost, v['frozen']['mean_t']*1e3,
                         'yes' if v['redesigned']['all_selective'] else 'no', (v['redesigned']['mean_t'] or float('nan'))*1e3,
                         ', '.join(v['frozen']['ct_beyond_alf']) or '-', v['frozen']['max_current_over_ct']])
    sh.table(['Feeder', 'Variant', 'Cases', 'Margin met (cases)', 'Margin met', 'Short margin (cases)', 'Lost (cases)',
              'Frozen t (ms)', 'Redesign selective', 'Redesigned t (ms)', 'CTs beyond ALF', 'Max fault current / CT rating'],
             rows, [None, None, '#,##0', '#,##0', '0.00%', '#,##0', '#,##0', '0.0', None, '0.0', None, '0.0'], freeze=True)
    sh.finish()

    # ============================================================== Table 6 speed
    sh = Sheet(wb, 'T6_Speed', 'Table 6. Speed-sensitive measures over each policy\'s own states', (
        'Fault duration = sum of w * (t_op + t_CB) (s/yr); I2t = sum of w * I^2 * (t_op + t_CB) (kA^2 s/yr), with the weights w of the expected unserved energy.',
        'Reductions are formulas relative to the fixed design (negative: increase). Rate-weighted t_op excludes the breaker time.'))
    rows = []; r0 = sh.r + 1
    for lab, k in names:
        rr = r0 + len(rows); row = [lab]
        for fd in FEED:
            _, v = look(fd, k)
            row += [v['fault_duration_s_per_yr'], v['i2t_kA2s_per_yr'], v['rate_weighted_mean_top_s']*1e3]
        # columns: B,C,D = 33 (dur, i2t, top); E,F,G = 69
        row += [f'=1-B{rr}/B${r0}', f'=1-E{rr}/E${r0}', f'=1-C{rr}/C${r0}', f'=1-F{rr}/F${r0}']
        rows.append(row)
    sh.table(['Policy', 'Fault duration 33 (s/yr)', 'I2t 33 (kA2s/yr)', 'Rate-weighted t_op 33 (ms)',
              'Fault duration 69 (s/yr)', 'I2t 69 (kA2s/yr)', 'Rate-weighted t_op 69 (ms)',
              'Duration reduction 33', 'Duration reduction 69', 'I2t reduction 33', 'I2t reduction 69'], rows,
             [None, '0.0000', '0.0000', '0.00', '0.0000', '0.0000', '0.00', '0.0%', '0.0%', '0.0%', '0.0%'], freeze=True)
    sh.finish()

    # ============================================================== Table 8 groups
    sh = Sheet(wb, 'T8_Groups', 'Table 8. Settings of the two groups of the best two-group policies', (
        'Group A contains the peak-load states. "Material" marks the relays listed in the paper (pickup differs by more than 5 % or any TMS differs).',))
    rows = []
    for fd in FEED:
        ga, gb = G[fd]['groups']
        for r in G[fd]['relays']:
            A, B = ga[r], gb[r]
            mat = (abs(A['IsP'] - B['IsP']) > 0.05*max(A['IsP'], B['IsP']) or abs(A['TMSP'] - B['TMSP']) > 1e-9
                   or abs(A['TMSN'] - B['TMSN']) > 1e-9 or A['IsN'] != B['IsN'])
            rows.append([fd, r, A['IsP'], B['IsP'], A['TMSP'], B['TMSP'], A['IsN'], B['IsN'], A['TMSN'], B['TMSN'], 'yes' if mat else 'no'])
    sh.table(['Feeder', 'Relay', 'Is phase A (A)', 'Is phase B (A)', 'TMS phase A', 'TMS phase B', 'Is earth A (A)', 'Is earth B (A)',
              'TMS earth A', 'TMS earth B', 'Material'], rows,
             [None, None, '0.0', '0.0', '0.00', '0.00', '0.0', '0.0', '0.00', '0.00', None], freeze=True)
    sh.finish()

    # ============================================================== Fig 2 hosting
    rows = []
    for fd in FEED:
        s = H[fd]['single']; hub = {int(b): v for b, v in H[fd]['P_MW'].items()}
        for b, v in s.items():
            rows.append([fd, int(b), v['managed']*CHARGER_KW/1e3, v['unmanaged']*CHARGER_KW/1e3, hub.get(int(b), float('nan'))])
    hdr = ['feeder', 'bus', 'limit_light_only_MW', 'limit_any_time_MW', 'hub_rating_MW']
    write_csv('fig2_hosting.csv', hdr, rows)
    sh = Sheet(wb, 'Fig2_Hosting', 'Fig. 2. Largest single hub each bus can host', (
        'limit_light_only: charging confined to light load (the envelope used); limit_any_time: charging allowed at any time; hub_rating: rating used when all three hubs operate together.',))
    sh.table(hdr, rows, [None, None, '0.00', '0.00', '0.00'], freeze=True); sh.finish()

    # ============================================================== Fig 3 impact
    rows = []
    for fd in FEED:
        for t in ('3ph', 'LL', 'SLG', 'LLG'):
            d = I[fd]['by_type'][t]
            for role in ('primary', 'backup'):
                rows.append([fd, t, role, 100*d[f'{role}_max_decrease'], 100*d[f'{role}_max_increase'], 100*d[f'{role}_p95_abs']])
    hdr = ['feeder', 'fault_type', 'role', 'max_decrease_pct', 'max_increase_pct', 'p95_abs_pct']
    write_csv('fig3_impact.csv', hdr, rows)
    sh = Sheet(wb, 'Fig3_Impact', 'Fig. 3. Change of relay current relative to the same fault with all hubs off (%)', (
        'Phase current for 3ph and LL faults, 3I0 for SLG and LLG faults. Bars span max_decrease..max_increase; ticks at +/- p95_abs.',))
    sh.table(hdr, rows, [None, None, None, '0.00', '0.00', '0.00'], freeze=True); sh.finish()

    # ============================================================== Fig 4 policy size
    rows = []
    for fd in FEED:
        p = P[fd]
        rows.append([fd, 'fixed', 'fixed design', 1, p['robust']['mean_t']*1e3])
        for k in sorted(int(x) for x in p['exhaustive'] if p['exhaustive'][x]):
            rows.append([fd, 'best', f'best {k} groups', k, p['exhaustive'][str(k)]['mean_t']*1e3])
        for nm, a in p['rules'].items():
            rows.append([fd, 'rule', nm, a['K'], a['mean_t']*1e3])
        for nm, a in p['cluster'].items():
            if a.get('mean_t') is not None: rows.append([fd, 'cluster', nm, a['K'], a['mean_t']*1e3])
        rows.append([fd, 'per_state', 'own settings per state', p['per_state']['K'], p['per_state']['mean_t']*1e3])
    hdr = ['feeder', 'kind', 'name', 'K', 'mean_t_ms']
    write_csv('fig4_policy_size.csv', hdr, rows)
    sh = Sheet(wb, 'Fig4_PolicySize', 'Fig. 4. Mean primary clearing time against the number of setting groups', (
        'kind: fixed / best (exhaustive best K-group policy) / rule (physical rule) / cluster / per_state (own settings for each state, drawn as a dashed line).',))
    sh.table(hdr, rows, [None, None, None, '0', '0.00'], freeze=True); sh.finish()

    # ============================================================== Fig 5 gain vs risk
    rows = []
    for fd in FEED:
        p = P[fd]; r0 = p['robust']['mean_t']
        pts = [('best K=2', p['exhaustive']['2'], 'best_K2'), ('best K=4', p['exhaustive']['4'], 'best_K4'),
               ('TOD', p['rules']['TOD'], 'TOD'), ('CHG', p['rules']['CHG'], 'CHG'), ('EXP', p['rules']['EXP'], 'EXP'),
               ('own per state', p['per_state'], 'per_state')]
        for lab, a, vk in pts:
            rows.append([fd, lab, 100*(1 - a['mean_t']/r0), V[fd]['policies'][vk].get('ens_per_mismatch', 0.0)/1e3])
    hdr = ['feeder', 'label', 'gain_pct', 'lost_energy_MWh']
    write_csv('fig5_gain_risk.csv', hdr, rows)
    sh = Sheet(wb, 'Fig5_GainRisk', 'Fig. 5. Gain against risk for the adaptive policies', (
        'gain_pct: reduction of mean clearing time vs. the fixed design; lost_energy_MWh: expected energy lost per wrong-group event.',))
    sh.table(hdr, rows, [None, None, '0.00', '0.000'], freeze=True); sh.finish()

    # ============================================================== Fig 6 boundary sweep
    SW = J('sweep_33.json'); rows = []
    for key, v in sorted(SW.items(), key=lambda kv: (kv[1]['ssc'], kv[1]['kf'], kv[1]['m'])):
        if 'robust' not in v:
            rows.append([v['ssc'], v['kf'], v['m'], 0, float('nan'), float('nan'), float('nan'), float('nan'), float('nan')]); continue
        b2 = (v['best'].get('2') or {}).get('mean_t'); ps = v['per_state'].get('mean_t')
        rows.append([v['ssc'], v['kf'], v['m'], 1, v['robust']['mean_t']*1e3, int(bool(v['robust'].get('all_selective'))),
                     b2*1e3 if b2 else float('nan'), ps*1e3 if ps else float('nan'), v['robust']['sens_backup_P']])
    hdr = ['ssc_MVA', 'kf', 'm', 'load_flow_solved', 'fixed_mean_t_ms', 'fixed_all_selective', 'best2_mean_t_ms',
           'per_state_mean_t_ms', 'fixed_min_backup_sensitivity']
    write_csv('fig6_boundary.csv', hdr, rows)
    sh = Sheet(wb, 'Fig6_Boundary', 'Fig. 6. Hubs scaled beyond the hosting limit (33-bus)', (
        'm: hub size / hosting limit. Empty cells: no fully selective design of that kind (or no power-flow solution). fixed_all_selective = 0: the fixed design fails to trip some faults.',))
    sh.table(hdr, rows, ['0', '0.0', '0.0', '0', '0.0', '0', '0.0', '0.0', '0.000'], freeze=True); sh.finish()

    # ============================================================== value grid
    sh = Sheet(wb, 'Value_Grid', 'Annual value of adaptation relative to the fixed design (A$/yr)', (
        'Value = (EUE_fixed - EUE_policy - n * lost energy per event - p_wg * extra fault-driven EUE) * VCR, with p_wg = n h / 8760.',
        f"VCR low/high: A${V['33']['params']['vcr'][0]} and A${V['33']['params']['vcr'][1]} per kWh ({SRC['vcr']}). Negative: adaptation costs more than it gains."))
    rows = []
    for fd in FEED:
        for key, d in V[fd]['value_grid'].items():
            n, h = key.split('|'); n = int(n.split('=')[1]); h = float(h.split('=')[1])
            for pol, (lo, hi) in d.items():
                rows.append([fd, n, h, pol, lo, hi])
    sh.table(['Feeder', 'Events per year n', 'Event length h (h)', 'Policy', 'Value at low VCR (A$/yr)', 'Value at high VCR (A$/yr)'],
             rows, [None, '0', '0.00', None, '#,##0', '#,##0'], freeze=True)
    sh.finish()

    order = ['README', 'Feeder_33', 'Feeder_69', 'Relays', 'T1_Hubs', 'T2_Inputs', 'T3_Settings33', 'T4_Policies', 'T5_Stress',
             'T6_Speed', 'T7_Settings69', 'T8_Groups', 'Fig2_Hosting', 'Fig3_Impact', 'Fig4_PolicySize', 'Fig5_GainRisk',
             'Fig6_Boundary', 'Value_Grid']
    assert sorted(order) == sorted(wb.sheetnames)
    wb._sheets.sort(key=lambda w: order.index(w.title))
    wb.active = 0
    wb.save(os.path.join(OUT, 'GTD_V2G_data.xlsx'))
    # the MATLAB scripts read their own copy of the figure data
    import shutil
    md = os.path.join(ROOT, 'matlab', 'data'); os.makedirs(md, exist_ok=True)
    for fn in os.listdir(CSV):
        shutil.copy(os.path.join(CSV, fn), os.path.join(md, fn))
    print('wrote', os.path.join(OUT, 'GTD_V2G_data.xlsx'), 'and', len(os.listdir(CSV)), 'CSV files (also in matlab/data)')


if __name__ == '__main__':
    main()
