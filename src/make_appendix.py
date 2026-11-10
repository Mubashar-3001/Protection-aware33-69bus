"""make_appendix.py — appendix tables from results/groups_<feeder>.json and
results/policies_69.json (fixed settings of the 69-bus feeder)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES, TEX
import json
def J(n): return json.load(open(os.path.join(RES, n)))
def f(x, d=1): return f'{x:,.{d}f}'.replace(',', '\\,')
def i50(x): return '--' if x is None else f(x, 0)

rows = []
for fd in ('33', '69'):
    G = J(f'groups_{fd}.json'); a, b = G['groups']
    pol = J(f'policies_{fd}.json')
    assert 0 in pol['exhaustive']['2']['groups'][0], 'first group must contain the peak-load states'
    rows.append(f'\\multicolumn{{4}}{{l}}{{\\emph{{IEEE {fd}-bus}}}} \\\\')
    for r in G['relays']:
        A, B = a[r], b[r]
        material = (abs(A['IsP'] - B['IsP']) > 0.05*max(A['IsP'], B['IsP']) or abs(A['TMSP'] - B['TMSP']) > 1e-9
                    or abs(A['TMSN'] - B['TMSN']) > 1e-9 or A['IsN'] != B['IsN'])
        if not material: continue
        rows.append(f"\\quad {r} & {f(A['IsP'])} / {f(B['IsP'])} & {f(A['TMSP'],2)} / {f(B['TMSP'],2)} & "
                    f"{f(A['TMSN'],2)} / {f(B['TMSN'],2)} \\\\")
    rows.append('\\midrule')
rows = rows[:-1]
open(os.path.join(TEX, 'tab_groups.tex'), 'w').write('\n'.join(rows) + '\n')

P = J('policies_69.json'); rows = []
for r, s in P['robust_settings'].items():
    rows.append(f"{r} & {P['backup'][r] or '--'} & {int(s['CT'])}/1 & {f(s['IsP'])} & {f(s['TMSP'],2)} & {i50(s['I50P'])} & "
                f"{f(s['IsN'])} & {f(s['TMSN'],2)} & {i50(s['I50N'])} \\\\")
open(os.path.join(TEX, 'tab_settings_69.tex'), 'w').write('\n'.join(rows) + '\n')
print('appendix tables written')
