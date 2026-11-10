"""run_all.py — rebuilds every result, figure, table, number and the PDF.
usage:  python src/run_all.py            (full; the boundary sweep dominates the run time)
        python src/run_all.py --quick    (skips the boundary sweep; reuses results/sweep_33.json)
"""
import os, sys, subprocess, time
SRC = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(SRC)
quick = '--quick' in sys.argv
steps = [['hosting.py', '33'], ['hosting.py', '69'], ['verify_model.py'], ['verify_convergence.py'],
         ['run_policies.py', '33'], ['run_policies.py', '69'], ['verify_grading.py'],
         ['run_tmsonly.py', '33'], ['run_tmsonly.py', '69'], ['run_impact.py', '33'], ['run_impact.py', '69'],
         ['run_stress.py', '33'], ['run_stress.py', '69'], ['run_value.py', '33'], ['run_value.py', '69'],
         ['run_groups.py', '33'], ['run_groups.py', '69'], ['run_boundary_diag.py']]
if not quick:
    sweep = os.path.join(ROOT, 'results', 'sweep_33.json')
    if os.path.exists(sweep): os.remove(sweep)          # the sweep resumes from this file
    steps.append(['run_sweep.py', '33'])
steps += [['make_appendix.py'], ['figs.py'], ['make_tex.py'], ['export_data.py'], ['make_diagrams.py']]
for st in steps:
    t0 = time.time(); print('>>', ' '.join(st), flush=True)
    subprocess.run([sys.executable, os.path.join(SRC, st[0])] + st[1:], check=True, cwd=SRC)
    print(f'   done in {time.time() - t0:.0f} s', flush=True)
tex = os.path.join(ROOT, 'tex')
for cmd in (['pdflatex', '-interaction=nonstopmode', 'main.tex'], ['bibtex', 'main'],
            ['pdflatex', '-interaction=nonstopmode', 'main.tex'], ['pdflatex', '-interaction=nonstopmode', 'main.tex']):
    subprocess.run(cmd, cwd=tex, stdout=subprocess.DEVNULL)
print('built tex/main.pdf')
