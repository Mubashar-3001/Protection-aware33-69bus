"""figs.py — every figure of the paper, drawn only from results/*.json.
usage: python figs.py           -> figs/*.pdf
Palette: validated categorical slots (CVD-safe adjacent pairs); text in ink
tokens; one y-axis per panel; legends for >=2 series plus direct labels.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import RES, FIGS, TEX, SRC
import json, sys, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
R = RES + '/'; F = FIGS + '/'
C1, C2, C3, C4, C5, C6, C7, C8 = ('#2a78d6', '#eb6834', '#1baf7a', '#eda100',
                                  '#e87ba4', '#008300', '#6250d6', '#e34948')
INK, INK2, GRID = '#0b0b0b', '#52514e', '#e4e3df'
plt.rcParams.update({'font.family': 'serif', 'font.size': 8, 'axes.linewidth': 0.6,
                     'axes.edgecolor': INK2, 'axes.labelcolor': INK, 'xtick.color': INK2,
                     'ytick.color': INK2, 'text.color': INK, 'mathtext.fontset': 'stix',
                     'legend.frameon': False, 'lines.linewidth': 1.4, 'savefig.bbox': 'tight',
                     'savefig.pad_inches': 0.02})
def J(n): return json.load(open(R + n))
def grid(ax, axis='y'):
    ax.grid(axis=axis, color=GRID, lw=0.6); ax.set_axisbelow(True)
    for s in ('top', 'right'): ax.spines[s].set_visible(False)

# ------------------------------------------------------------- Fig 1 one-lines
def oneline_layout(name):
    """branches, bus positions, relays and hub ratings of the one-line diagram (Fig. 1);
    shared with make_diagrams.py, which writes the draw.io and Graphviz versions."""
    from grid import feeder_data
    BR, PL, QL, _ = feeder_data(name)
    from cases import LAYOUTS
    H = J(f'hosting_{name}.json'); hubs = {int(b): v for b, v in H['P_MW'].items()}
    pos = {}
    if name == '33':
        for i, b in enumerate(range(1, 19)): pos[b] = (i, 0)
        for i, b in enumerate(range(19, 23)): pos[b] = (1 + (i + 1)*0.9, 1.1)
        for i, b in enumerate(range(23, 26)): pos[b] = (2 + (i + 1)*0.9, -1.1)
        for i, b in enumerate(range(26, 34)): pos[b] = (5 + (i + 1)*0.95, 1.1)
    else:
        for i, b in enumerate(range(1, 28)): pos[b] = (i*0.62, 0)
        # rows chosen so that no lateral crosses another one
        lat = [(51, 52, 8, 1.0), (68, 69, 12, 1.0), (66, 67, 11, 2.0), (36, 46, 3, 3.0),
               (47, 50, 4, -1.0), (53, 65, 9, -1.0), (28, 35, 3, -2.0)]
        for a, b, root, y in lat:
            x0 = pos[root][0]
            for i, n in enumerate(range(a, b + 1)):
                pos[n] = (x0 + (i + 1)*0.55, y)
    rel = {}
    for r, (f, t) in LAYOUTS[name]['relays'].items():    # relay symbol on its branch
        (x1, y1), (x2, y2) = pos[f], pos[t]
        rel[r] = (x1, y1 + 0.45*(y2 - y1)) if y1 != y2 else (x1 + 0.4*(x2 - x1), y1)
    return [(f, t) for f, t, *_ in BR], pos, rel, hubs

def oneline(ax, name):
    BR, pos, relpos, hubs = oneline_layout(name)
    for f, t in BR:
        (x1, y1), (x2, y2) = pos[f], pos[t]
        if y1 != y2 and x1 != x2: ax.plot([x1, x1, x2], [y1, y2, y2], color='#9b9a95', lw=0.9, zorder=1)
        else: ax.plot([x1, x2], [y1, y2], color='#9b9a95', lw=0.9, zorder=1)
    for b, (x, y) in pos.items():
        ax.plot(x, y, 'o', ms=2.2, color=INK2, zorder=2)
    for b in (1,):
        ax.plot(pos[b][0] - 0.45, pos[b][1], marker='$\\sim$', ms=9, color=INK)
    for r, (xm, ym) in relpos.items():
        ax.plot(xm, ym, 's', ms=5.2, mfc='white', mec=C1 if r.startswith('R') else C2, mew=1.3, zorder=4)
        ax.annotate(r, (xm, ym), textcoords='offset points', xytext=(0, -9 if ym <= 0 else 6),
                    ha='center', fontsize=6.3, color=INK)
    for b, P in hubs.items():
        x, y = pos[b]
        ax.plot(x, y, 'D', ms=7, mfc=C3, mec=INK, mew=0.5, zorder=5)
        ax.annotate(f'H{b}\n{P:.2f} MW', (x, y), textcoords='offset points',
                    xytext=(0, 7 if y >= 0 else -16), ha='center', fontsize=6.1, color=INK)
    ax.set_title(f'IEEE {name}-bus', fontsize=8, loc='left'); ax.axis('off')

def fig1():
    fig, axs = plt.subplots(2, 1, figsize=(7.0, 5.0), gridspec_kw=dict(height_ratios=[1, 1.45]))
    oneline(axs[0], '33'); oneline(axs[1], '69')
    h = [Line2D([], [], ls='', marker='s', mfc='white', mec=C1, mew=1.3, label='trunk breaker / recloser (R)'),
         Line2D([], [], ls='', marker='s', mfc='white', mec=C2, mew=1.3, label='lateral recloser (L)'),
         Line2D([], [], ls='', marker='D', mfc=C3, mec=INK, mew=0.5, label='V2G hub with hub breaker (H)')]
    axs[0].legend(handles=h, loc='upper right', fontsize=6.3, ncol=1, bbox_to_anchor=(1.0, 1.05))
    fig.savefig(F + 'oneline.pdf'); plt.close(fig)

# ------------------------------------------------------------- Fig 2 hosting
def fig2():
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.3), gridspec_kw=dict(width_ratios=[1, 1.9]))
    for ax, name in zip(axs, ('33', '69')):
        H = J(f'hosting_{name}.json'); s = H['single']
        b = np.array([int(k) for k in s]); man = np.array([v['managed'] for v in s.values()])*0.35
        un = np.array([v['unmanaged'] for v in s.values()])*0.35
        ax.bar(b, man, width=0.72, color=C1, label='charge at light load only', zorder=2)
        ax.plot(b, un, ls='', marker='_', ms=5, mew=1.3, color=C2, label='charge at any time', zorder=3)
        for i, hb in enumerate(H['buses']):
            v = H['P_MW'][str(hb)]
            ax.plot(hb, v, 'D', ms=4.2, mfc=C3, mec=INK, mew=0.5, zorder=4,
                    label='rating used (all hubs together)' if i == 0 else None)
            ax.annotate(f'H{hb}: {v:.2f}', (hb, v), textcoords='offset points', xytext=(0, 5),
                        ha='center', fontsize=5.8, color=INK,
                        bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.85))
        ax.set_xlabel('bus'); ax.set_xlim(1, b.max() + 1); grid(ax)
        ax.set_title(f'IEEE {name}-bus', fontsize=8, loc='left')
    axs[0].set_ylabel('single-hub hosting limit (MW)')
    h, l = axs[1].get_legend_handles_labels()
    fig.legend(h, l, loc='upper center', ncol=3, fontsize=6.5, bbox_to_anchor=(0.5, 1.06))
    fig.tight_layout(w_pad=1.2); fig.savefig(F + 'hosting.pdf'); plt.close(fig)

# ------------------------------------------------------------- Fig 3 impact
def fig3():
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.2), sharey=True)
    types = ('3ph', 'LL', 'SLG', 'LLG')
    for ax, name in zip(axs, ('33', '69')):
        I = J(f'impact_{name}.json')['by_type']
        for k, t in enumerate(types):
            for j, (role, col) in enumerate((('primary', C1), ('backup', C2))):
                y = k + (0.17 if j == 0 else -0.17)
                lo, hi = 100*I[t][f'{role}_max_decrease'], 100*I[t][f'{role}_max_increase']
                p95 = 100*I[t][f'{role}_p95_abs']
                ax.plot([lo, hi], [y, y], color=col, lw=2.0, solid_capstyle='round')
                ax.plot([-p95, p95], [y, y], ls='', marker='|', ms=6, mew=1.2, color=INK)
        ax.axvline(0, color=INK2, lw=0.6)
        ax.set_yticks(range(4)); ax.set_yticklabels(types); ax.set_xlabel('change vs. all hubs off (%)')
        ax.set_title(f'IEEE {name}-bus', fontsize=8, loc='left'); grid(ax, 'x')
    h = [Line2D([], [], color=C1, lw=2, label='primary relay (range)'),
         Line2D([], [], color=C2, lw=2, label='backup relay (range)'),
         Line2D([], [], ls='', marker='|', ms=6, mew=1.2, color=INK, label='±95th percentile')]
    fig.legend(handles=h, loc='lower center', ncol=3, fontsize=6.5, bbox_to_anchor=(0.5, -0.07))
    fig.tight_layout(w_pad=1.0, rect=(0, 0.05, 1, 1)); fig.savefig(F + 'impact.pdf'); plt.close(fig)

# ------------------------------------------------------------- Fig 4 policy-size curve
def fig4():
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.6))
    for ax, name in zip(axs, ('33', '69')):
        P = J(f'policies_{name}.json'); r0 = P['robust']['mean_t']*1e3
        K = sorted(int(k) for k in P['exhaustive'] if P['exhaustive'][k])
        y = [P['exhaustive'][str(k)]['mean_t']*1e3 for k in K]
        ax.plot(K, y, '-o', color=C1, ms=4, label='best K-group policy (exhaustive)', zorder=3)
        ax.axhline(P['per_state']['mean_t']*1e3, color=INK2, ls='--', lw=0.9)
        rules = sorted(P['rules'].items(), key=lambda kv: (kv[1]['K'], kv[1]['mean_t']))
        for j, (nm, a) in enumerate(rules):
            ax.plot(a['K'], a['mean_t']*1e3, 's', ms=4.5, mfc='white', mec=C2, mew=1.2, zorder=4)

        for nm, a in P['cluster'].items():
            if a.get('mean_t') is None: continue
            ax.plot(a['K'], a['mean_t']*1e3, '^', ms=4.5, mfc='white', mec=C3, mew=1.2, zorder=4)
        ax.set_xlabel('number of setting groups K'); ax.set_xlim(-0.6, 9.6)
        ax.set_title(f'IEEE {name}-bus (fixed design: {r0:.1f} ms)', fontsize=8, loc='left'); grid(ax)
    axs[0].set_ylabel('mean primary clearing time (ms)')
    h = [Line2D([], [], color=C1, marker='o', ms=4, label='best K-group policy (exhaustive)'),
         Line2D([], [], ls='', marker='s', mfc='white', mec=C2, mew=1.2, label='physical rule'),
         Line2D([], [], ls='', marker='^', mfc='white', mec=C3, mew=1.2, label='clustering'),
         Line2D([], [], color=INK2, ls='--', lw=0.9, label='own settings per state (K = 35)')]
    fig.legend(handles=h, loc='lower center', ncol=4, fontsize=6.5, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(w_pad=1.0, rect=(0, 0.07, 1, 1)); fig.savefig(F + 'policy_size.pdf'); plt.close(fig)

# ------------------------------------------------------------- Fig 5 gain vs risk
def fig5():
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    mk = {'33': 'o', '69': 's'}
    for name in ('33', '69'):
        P = J(f'policies_{name}.json'); V = J(f'value_{name}.json')['policies']; r0 = P['robust']['mean_t']
        pts = {'best K=2': P['exhaustive']['2'], 'best K=4': P['exhaustive']['4'], 'TOD': P['rules']['TOD'],
               'CHG': P['rules']['CHG'], 'EXP': P['rules']['EXP'], 'own per state': P['per_state']}
        key = {'best K=2': 'best_K2', 'best K=4': 'best_K4', 'TOD': 'TOD', 'CHG': 'CHG', 'EXP': 'EXP',
               'own per state': 'per_state'}
        for lab, a in pts.items():
            g = 100*(1 - a['mean_t']/r0); e = V[key[lab]].get('ens_per_mismatch', 0.0)/1e3
            ax.plot(g, e, mk[name], ms=5, mfc=C1 if name == '33' else 'white', mec=C1, mew=1.2)
            off = {'best K=2': (4, -9), 'best K=4': (4, 3), 'TOD': (-4, 6), 'CHG': (4, 5), 'EXP': (5, 3),
                   'own per state': (-6, -10)}
            if name == '33':
                ha = 'right' if off[lab][0] < 0 else 'left'
                ax.annotate(lab, (g, e), textcoords='offset points', xytext=off[lab], ha=ha, fontsize=6, color=INK2)
    ax.set_xlabel('reduction of mean clearing time vs. fixed (%)')
    ax.set_ylabel('expected lost energy per\nwrong-group event (MWh)'); grid(ax)
    h = [Line2D([], [], ls='', marker='o', mfc=C1, mec=C1, label='IEEE 33-bus'),
         Line2D([], [], ls='', marker='s', mfc='white', mec=C1, mew=1.2, label='IEEE 69-bus')]
    ax.legend(handles=h, loc='lower right', fontsize=6.3)
    fig.tight_layout(); fig.savefig(F + 'gain_risk.pdf'); plt.close(fig)

# ------------------------------------------------------------- Fig 6 boundary
def fig6(name='33'):
    S = J(f'sweep_{name}.json')
    ssc = sorted({v['ssc'] for v in S.values()}); kfs = sorted({v['kf'] for v in S.values()})
    fig, axs = plt.subplots(2, len(ssc), figsize=(7.0, 3.9), sharex=True, sharey='row')
    ls = {kfs[0]: '-', kfs[-1]: '--'}
    for c, sc in enumerate(ssc):
        a1, a2 = axs[0, c], axs[1, c]
        for kf in kfs:
            pts = sorted((v['m'], v) for v in S.values() if v['ssc'] == sc and v['kf'] == kf and 'robust' in v)
            m = [p[0] for p in pts]
            rob = [p[1]['robust']['mean_t']*1e3 for p in pts]
            b2 = [(p[1]['best'].get('2') or {}).get('mean_t') for p in pts]
            ps = [p[1]['per_state'].get('mean_t') for p in pts]
            sens = [p[1]['robust']['sens_backup_P'] for p in pts]
            a1.plot(m, rob, ls[kf], color=C1, label=f'fixed, $k_f$={kf}')
            for x, y, p in zip(m, rob, pts):
                if not p[1]['robust'].get('all_selective'):
                    a1.plot(x, y, 'o', ms=4, mfc='white', mec=C1, mew=1.1, zorder=5)
            a1.plot([x for x, y in zip(m, b2) if y], [y*1e3 for y in b2 if y], ls[kf], color=C2,
                    label=f'best 2 groups, $k_f$={kf}')
            a1.plot([x for x, y in zip(m, ps) if y], [y*1e3 for y in ps if y], ls[kf], color=C3,
                    marker='o', ms=2.5, label=f'own settings per state, $k_f$={kf}')
            a2.plot(m, sens, ls[kf], color=C1, marker='o', ms=2.5)
        bad = [v['m'] for v in S.values() if v['ssc'] == sc and 'robust' in v and not v['robust'].get('all_selective')]
        for a in (a1, a2):
            a.axvspan(0, 1.0, color='#f0efec', zorder=0); grid(a)
            if bad: a.axvspan(min(bad) - 0.25, 3.2, color='#fbe3e2', zorder=0)
            a.set_xlim(0.4, max(v['m'] for v in S.values()) + 0.1)
        a2.axhline(1.2, color=C8, lw=0.9)
        a2.text(0.45, 1.23, 'required 1.2', fontsize=6, color=INK2)
        a1.set_title(f'$S_{{sc}}$ = {sc:.0f} MVA', fontsize=8, loc='left')
        a1.text(0.7, 0.96, 'voltage-\nfeasible', transform=a1.get_xaxis_transform(), fontsize=6,
                color=INK2, va='top', ha='center')
        if bad: a1.text(min(bad) + 0.12, 0.06, 'fixed design\nmisses faults', transform=a1.get_xaxis_transform(),
                        fontsize=6, color=INK2, va='bottom', ha='center')
        a2.set_xlabel('hub size / hosting limit')
    axs[0, 0].set_ylabel('mean primary\nclearing time (ms)')
    axs[1, 0].set_ylabel('fixed design: min.\nbackup sensitivity')
    h = [Line2D([], [], color=C1, label='fixed design'), Line2D([], [], color=C2, label='best 2 groups'),
         Line2D([], [], color=C3, marker='o', ms=2.5, label='own settings per state'),
         Line2D([], [], color=INK2, ls='-', label=f'$k_f$ = {kfs[0]}'),
         Line2D([], [], color=INK2, ls='--', label=f'$k_f$ = {kfs[-1]}')]
    fig.legend(handles=h, loc='upper center', ncol=5, fontsize=6.5, bbox_to_anchor=(0.5, 1.04))
    fig.tight_layout(w_pad=0.6, h_pad=0.6); fig.savefig(F + 'boundary.pdf'); plt.close(fig)

if __name__ == '__main__':
    import os; os.makedirs(F, exist_ok=True)
    which = sys.argv[1:] or ['1', '2', '3', '4', '5', '6']
    for w in which:
        globals()['fig' + w](); print('fig', w, 'done')
