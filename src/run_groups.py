"""run_groups.py — settings of each group of the certified best two-group
policy, to show what actually changes between groups.
usage: python run_groups.py 33 -> results/groups_<feeder>.json"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES
import json, pickle
import policies as P

name = sys.argv[1] if len(sys.argv) > 1 else '33'
ds = pickle.load(open(RES + f'/ds_{name}_base.pkl', 'rb'))
pol = json.load(open(RES + f'/policies_{name}.json'))
D = P.Designer(ds); lay = ds['lay']
groups = pol['exhaustive']['2']['groups']
out = dict(feeder=name, relays=lay.names, blocks=pol['exhaustive']['2']['class_blocks'],
           classes=pol['classes'], groups=[])
for G in groups:
    d = D.design(G)
    out['groups'].append({r: dict(IsP=float(d['st']['IsP'][i]), TMSP=float(d['tp'][i]),
                                  I50P=(None if d['st']['I50P'][i] > 1e11 else float(d['st']['I50P'][i])),
                                  IsN=float(d['st']['IsN'][i]), TMSN=float(d['tn'][i]),
                                  I50N=(None if d['st']['I50N'][i] > 1e11 else float(d['st']['I50N'][i])))
                          for i, r in enumerate(lay.names)})
json.dump(out, open(RES + f'/groups_{name}.json', 'w'), indent=1)
diff = [r for r in lay.names if any(out['groups'][0][r][k] != out['groups'][1][r][k] for k in out['groups'][0][r])]
print('relays whose settings differ between the two groups:', diff)
for r in diff: print(' ', r, out['groups'][0][r], '|', out['groups'][1][r])
