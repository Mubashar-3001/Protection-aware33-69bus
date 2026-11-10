"""settings.py — relay settings for a group of scenarios, exact time grading
on the relays' discrete TMS grid, and the protection-operation evaluator.

Element set per relay: 51P, 50P (phase), 51N, 50N (earth); all directional
(forward = away from the source; hub relays: into the hub).
Rule-based quantities (utility practice): CT ratio, pickups, 50 settings.
Optimised quantity: TMS of 51P and 51N on the relay's discrete grid,
minimising the sum over every case of the primary relay's clearing time
(fastest operating element, as the evaluator measures it) subject to the
tolerance-aware grading margin  t_B >= (1+e) t_P + c  against the designated
backup in every case.  Each relay has one designated backup, so the
constraints form a tree and the problem is solved exactly by dynamic
programming over that tree (coordinate).  coordinate_milp keeps the earlier
mixed-integer formulation, in which each case is graded on one designated
element; it is used only to cross-check the dynamic programme
(verify_grading.py).
"""
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
from params import (CT_STD, CT_ALF, OLF, EF_PICKUP_CT, STEP_IS, TMS_MIN, TMS_MAX, TMS_STEP,
                    CURVE, T50, K50, margin_coeffs, SENS_PRIMARY, SENS_BACKUP)
from cases import _direction

E_MARG, C_MARG = margin_coeffs()
NSTEP = int(round((TMS_MAX - TMS_MIN)/TMS_STEP))
INF = 1e12
GROUND = ('SLG', 'LLG')


def ceil_step(x, step):
    return np.ceil(x/step - 1e-9)*step


def fixed_hardware(ds):
    """CT primary per relay (same for every setting group)."""
    Imax_load = np.abs(ds['Iload']).max(axis=0)
    Imax_flt = ds['Iph'].max(axis=(0, 1, 2))
    ct = []
    for r in range(ds['lay'].nr):
        need = max(Imax_load[r], Imax_flt[r]/CT_ALF)
        ct.append(next(c for c in CT_STD if c >= need))
    return np.array(ct, float)


def forward_load(ds, s, gross=True):
    """forward load current per relay used for pickup security. With
    gross=True exporting hubs are treated as off: export can stop at any
    instant, so the load it masks must not trip the relay."""
    I = ds['Iload_g'][s] if gross else ds['Iload'][s]
    P = ds['Pflow_g'][s] if gross else ds['Pflow'][s]
    return np.where(P > 0, np.abs(I), 0.0)


def group_settings(ds, G, ct):
    """pickups and instantaneous settings for scenario group G (list of s)."""
    lay = ds['lay']; nr = lay.nr; G = list(G)
    owner, fwd = ds['owner'], ds['topo_fwd']
    Iload_fwd = np.max([forward_load(ds, s) for s in G], axis=0)
    IsP = np.maximum(ceil_step(OLF*Iload_fwd, STEP_IS*ct), 0.10*ct)
    IsN = np.maximum(ceil_step(EF_PICKUP_CT*ct, STEP_IS*ct), 0.0)
    I50P = np.full(nr, INF); I50N = np.full(nr, INF)
    gt = np.array([ft in GROUND for ft, _ in ds['ftypes']])
    for r in range(nr):
        outside = (fwd[:, r] == 1) & (owner != r)          # downstream, other zones
        inside = owner == r
        maxP_out = ds['Iph'][G][:, outside][..., r].max() if outside.any() else 0.0
        maxN_out = ds['I3o'][G][:, outside][..., r].max() if outside.any() else 0.0
        lvmask = ds['LVfwd'][:, r]                          # LV faults downstream of r
        maxLV = ds['LV'][G][:, lvmask, r].max() if lvmask.any() else 0.0
        setP = K50*max(maxP_out, maxLV); setN = K50*maxN_out
        maxP_in = ds['Iph'][G][:, inside][..., r].max()
        maxN_in = (ds['I3o'][G][:, inside][..., r][..., gt]).max()
        setP = ceil_step(max(setP, IsP[r]), STEP_IS*ct[r]); setN = ceil_step(max(setN, IsN[r]), STEP_IS*ct[r])
        I50P[r] = setP if (setP < maxP_in and (outside.any() or lvmask.any())) else INF
        # earth instantaneous only where a downstream relay zone defines its reach
        I50N[r] = setN if (setN < maxN_in and outside.any()) else INF
    return dict(IsP=IsP, IsN=IsN, I50P=I50P, I50N=I50N)


def _elem_coeffs(ds, s, st):
    """per-case operating coefficients for scenario s under settings st.
    returns dict of arrays shaped (nL, nT, nR): kP, kN (51 time per unit TMS,
    inf if not operating), o50 (instantaneous operates)."""
    Iph, I3o = ds['Iph'][s], ds['I3o'][s]
    dP, dN = ds['dP'][s] == 1, ds['dN'][s] == 1
    MP = Iph/st['IsP']; MN = I3o/st['IsN']
    cP = np.minimum(MP, CURVE['Mmax']); cN = np.minimum(MN, CURVE['Mmax'])   # IEC: flat above Mmax
    kP = np.where(dP & (MP > 1.0), CURVE['k']/np.maximum(cP**CURVE['a'] - 1, 1e-12), np.inf)
    kN = np.where(dN & (MN > 1.0), CURVE['k']/np.maximum(cN**CURVE['a'] - 1, 1e-12), np.inf)
    o50 = (dP & (Iph > st['I50P'])) | (dN & (I3o > st['I50N']))
    return kP, kN, o50


X_GRID = TMS_MIN + TMS_STEP*np.arange(NSTEP + 1)      # the relay's TMS settings
NG = len(X_GRID)
_TIE = 1e-9*(np.arange(NG)[:, None] + np.arange(NG)[None, :])   # prefer lower TMS on ties
_CH = 256


def _case_arrays(ds, G, st, designated=False):
    """for every relay p as primary, the coefficients of every case of group G
    in its zone: own 51P/51N time per unit TMS (aP, aN; inf if the element
    does not operate), whether its 50 operates, and the same for its
    designated backup (bP, bN, b50)."""
    lay = ds['lay']; nr = lay.nr; owner = ds['owner']
    ftg = np.array([ft in GROUND for ft, _ in ds['ftypes']])
    bk = [lay.names.index(lay.backup[n]) if lay.backup[n] else -1 for n in lay.names]
    acc = {p: {k: [] for k in ('aP', 'aN', 'o50', 'bP', 'bN', 'b50', 'gt')} for p in range(nr)}
    for s in G:
        kP, kN, o50 = _elem_coeffs(ds, s, st)
        for p in range(nr):
            L = np.where(owner == p)[0]
            if not len(L): continue
            A = acc[p]; b = bk[p]
            A['aP'].append(kP[L, :, p].ravel()); A['aN'].append(kN[L, :, p].ravel())
            A['o50'].append(o50[L, :, p].ravel())
            A['gt'].append(np.broadcast_to(ftg, (len(L), len(ftg))).ravel())
            if b >= 0:
                A['bP'].append(kP[L, :, b].ravel()); A['bN'].append(kN[L, :, b].ravel())
                A['b50'].append(o50[L, :, b].ravel())
    out = {}
    for p in range(nr):
        A = acc[p]
        if not A['aP']:
            out[p] = None; continue
        c = {k: np.concatenate(v) for k, v in A.items() if v}
        if bk[p] < 0:
            n = len(c['aP']); c['bP'] = np.full(n, np.inf); c['bN'] = np.full(n, np.inf); c['b50'] = np.zeros(n, bool)
        if designated:                       # MILP convention: one element per case
            useN = c['gt'] & np.isfinite(c['aN'])
            c['aP'] = np.where(useN, np.inf, c['aP']); c['aN'] = np.where(useN, c['aN'], np.inf)
        out[p] = c
    return out, bk


def _pareto(aP, aN, gm):
    """indices of the non-dominated requirement terms min(aP x + gm, aN y + gm):
    term j is dropped if some term i has aP_i >= aP_j, aN_i >= aN_j, gm_i >= gm_j
    (it can then never set the maximum). Exact."""
    o = np.lexsort((-aN, -aP, -gm)); aP, aN = aP[o], aN[o]
    keep = np.ones(len(o), bool); FP = np.empty(0); FN = np.empty(0); B = 512
    for k0 in range(0, len(o), B):
        bp, bn = aP[k0:k0 + B], aN[k0:k0 + B]
        dom = ((FP[:, None] >= bp[None, :]) & (FN[:, None] >= bn[None, :])).any(axis=0) if len(FP) else \
            np.zeros(len(bp), bool)
        tri = np.triu(np.ones((len(bp), len(bp)), bool), 1)             # earlier i dominates later j
        dom |= ((bp[:, None] >= bp[None, :]) & (bn[:, None] >= bn[None, :]) & tri).any(axis=0)
        keep[k0:k0 + B] = ~dom
        FP = np.r_[FP, bp[~dom]]; FN = np.r_[FN, bn[~dom]]
    return o[keep]


def _relay_tables(c):
    """own cost f(i,j) = sum of primary clearing times over the relay's cases,
    and the backup requirement g^P(i,j), g^N(i,j) (smallest backup TMS of its
    51P/51N element) as functions of the relay's own TMS grid indices.
    Primary time of a case: T50 if its 50 element operates, else
    min(aP*TMS_P, aN*TMS_N) over the 51 elements that operate."""
    X = X_GRID
    f = np.zeros((NG, NG)); gP = np.full((NG, NG), -np.inf); gN = np.full((NG, NG), -np.inf)
    st = dict(n51=0, n50=0, sens_fail=0, struct_viol=0, nrows=0, nrows_kept=0)
    if c is None: return f, gP, gN, st
    fP, fN = np.isfinite(c['aP']), np.isfinite(c['aN'])
    oper = fP | fN | c['o50']
    st['sens_fail'] = int((~oper).sum())
    st['struct_viol'] = int((oper & c['b50']).sum())
    c50 = c['o50']; c51 = oper & ~c50
    st['n50'] = int(c50.sum()); st['n51'] = int(c51.sum())
    # ---- own cost
    f += st['n50']*T50
    onlyP, onlyN, both = c51 & fP & ~fN, c51 & fN & ~fP, c51 & fP & fN
    f += c['aP'][onlyP].sum()*X[:, None] + c['aN'][onlyN].sum()*X[None, :]
    if both.any():          # sum_c min(aP x, aN y): 51P is faster iff aP/aN < y/x
        aP, aN = c['aP'][both], c['aN'][both]; r = aP/aN; o = np.argsort(r)
        r, aP, aN = r[o], aP[o], aN[o]
        cP = np.r_[0.0, np.cumsum(aP)]; cN = np.r_[0.0, np.cumsum(aN)]
        k = np.searchsorted(r, X[None, :]/X[:, None], side='left')
        f += X[:, None]*cP[k] + X[None, :]*(cN[-1] - cN[k])
    # ---- backup requirement: max over cases of min(aP' x + gm, aN' y + gm)
    tP = np.where(c50, 0.0, np.where(fP, (1 + E_MARG)*c['aP'], np.inf))
    tN = np.where(c50, 0.0, np.where(fN, (1 + E_MARG)*c['aN'], np.inf))
    c0 = np.where(c50, (1 + E_MARG)*T50, 0.0)
    for kb, g in ((c['bP'], gP), (c['bN'], gN)):
        m = oper & np.isfinite(kb)
        if not m.any(): continue
        aP, aN, gm = tP[m]/kb[m], tN[m]/kb[m], (c0[m] + C_MARG)/kb[m]
        st['nrows'] += int(m.sum())
        kp = _pareto(aP, aN, gm); st['nrows_kept'] += len(kp)
        for k0 in range(0, len(kp), _CH):
            ii = kp[k0:k0 + _CH]
            with np.errstate(invalid='ignore'):
                A = aP[ii, None, None]*X[None, :, None]; Bn = aN[ii, None, None]*X[None, None, :]
            req = np.minimum(A, Bn) + gm[ii, None, None]
            g[...] = np.maximum(g, req.max(axis=0))
    return f, gP, gN, st


def _bin(g):
    """smallest grid index whose TMS meets requirement g (0 if unconstrained;
    > NSTEP if no setting can)."""
    i = np.ceil((g - TMS_MIN)/TMS_STEP - 1e-12)
    i = np.where(np.isneginf(g), 0, i)
    return np.maximum(i, 0)


def _lift(Cc, gP, gN):
    """V(i,j) = min cost of the child sub-tree over child settings whose
    backup requirement is met by parent setting (i,j); with arg-min."""
    iP, iN = _bin(gP).ravel(), _bin(gN).ravel(); cost = Cc.ravel()
    ok = np.isfinite(cost) & (iP <= NSTEP) & (iN <= NSTEP)
    sidx = np.where(ok)[0]
    M = np.full(NG*NG, np.inf); A = np.full(NG*NG, -1, dtype=np.int64)
    if len(sidx):
        b = iP[sidx].astype(np.int64)*NG + iN[sidx].astype(np.int64)
        o = np.lexsort((sidx, cost[sidx], b)); bs = b[o]
        first = np.r_[True, bs[1:] != bs[:-1]]
        M[bs[first]] = cost[sidx][o][first]; A[bs[first]] = sidx[o][first]
    M = M.reshape(NG, NG); A = A.reshape(NG, NG)
    for i in range(1, NG):                   # 2-D prefix minimum
        w = M[i - 1] < M[i]; M[i] = np.where(w, M[i - 1], M[i]); A[i] = np.where(w, A[i - 1], A[i])
    for j in range(1, NG):
        w = M[:, j - 1] < M[:, j]; M[:, j] = np.where(w, M[:, j - 1], M[:, j]); A[:, j] = np.where(w, A[:, j - 1], A[:, j])
    return M, A


def coordinate(ds, G, st, ct, designated=False):
    """exact TMS (51P, 51N) for group G on the discrete grid; minimises the sum
    of primary clearing times (fastest operating element) subject to the
    grading margin against the designated backup in every case.
    designated=True reproduces the MILP's one-element convention (check only).
    Returns tmsP, tmsN, info."""
    lay = ds['lay']; nr = lay.nr
    cases, bk = _case_arrays(ds, list(G), st, designated)
    tabs = {p: _relay_tables(cases[p]) for p in range(nr)}
    children = {r: [p for p in range(nr) if bk[p] == r] for r in range(nr)}
    order, seen = [], set()
    def post(r):
        for q in children[r]: post(q)
        order.append(r); seen.add(r)
    for r in range(nr):
        if bk[r] < 0: post(r)
    assert len(seen) == nr, 'backup graph must be a forest'
    C, arg = {}, {}
    for q in order:
        Cq = tabs[q][0] + _TIE
        for ch in children[q]:
            V, A = _lift(C[ch], tabs[ch][1], tabs[ch][2]); Cq = Cq + V; arg[ch] = A
        C[q] = Cq
    state = {}; feasible = True
    for r in range(nr):
        if bk[r] < 0:
            k = int(np.argmin(C[r])); state[r] = k; feasible &= bool(np.isfinite(C[r].ravel()[k]))
    if feasible:
        for q in reversed(order):
            for ch in children[q]: state[ch] = int(arg[ch].ravel()[state[q]])
        iP = np.array([state[r] // NG for r in range(nr)]); iN = np.array([state[r] % NG for r in range(nr)])
        tp, tn = X_GRID[iP], X_GRID[iN]
        objective = float(sum(tabs[r][0][iP[r], iN[r]] for r in range(nr)))
    else:
        tp = tn = np.full(nr, np.nan); objective = np.nan
    agg = {k: sum(tabs[p][3][k] for p in range(nr)) for k in ('n51', 'n50', 'sens_fail', 'struct_viol', 'nrows',
                                                              'nrows_kept')}
    info = dict(status=0 if feasible else 2, message='optimal (tree dynamic programme)' if feasible else 'infeasible',
                feasible=bool(feasible), nrows=agg['nrows'], nrows_kept=agg['nrows_kept'], struct_viol=agg['struct_viol'],
                sens_fail=agg['sens_fail'], ncase=agg['n51'] + agg['n50'] + agg['sens_fail'],
                objective=objective, gap=0.0, method='tree-DP' + ('-designated' if designated else ''))
    return tp, tn, info


def coordinate_milp(ds, G, st, ct, integer=True, time_limit=120):
    """cross-check only: MILP in which each case is graded on ONE designated
    primary element (51N for earth faults when it operates, else 51P; the
    50 element when it operates). Exact for that designated objective."""
    lay = ds['lay']; nr = lay.nr; owner = ds['owner']
    ftg = np.array([ft in GROUND for ft, _ in ds['ftypes']])
    rows = {}                      # (b_var, p_var or -1) -> list of (a, d)
    obj = np.zeros(2*nr)           # variables: TMS_P[0..nr-1], TMS_N[0..nr-1]
    struct_viol = 0; sens_fail = 0; ncase = 0
    for s in G:
        kP, kN, o50 = _elem_coeffs(ds, s, st)
        for l in range(len(ds['locs'])):
            p = owner[l]; bname = lay.backup[lay.names[p]]
            for t in range(len(ds['ftypes'])):
                ncase += 1
                pk = (kP[l, t, p], kN[l, t, p])
                if not (np.isfinite(pk[0]) or np.isfinite(pk[1]) or o50[l, t, p]):
                    sens_fail += 1; continue
                if o50[l, t, p]:
                    des = None                                     # constant T50
                elif ftg[t] and np.isfinite(pk[1]):
                    des = (nr + p, pk[1]); obj[nr + p] += pk[1]
                else:
                    des = (p, pk[0]); obj[p] += pk[0]
                if bname is None: continue
                b = lay.names.index(bname)
                if o50[l, t, b]:
                    struct_viol += 1
                for bvar, kb in ((b, kP[l, t, b]), (nr + b, kN[l, t, b])):
                    if not np.isfinite(kb): continue
                    if des is None:
                        rows.setdefault((bvar, -1), []).append((kb, 0.0))
                    else:
                        rows.setdefault((bvar, des[0]), []).append((kb, des[1]))
    # Pareto pruning: x_b >= (d/a) x_p + C/a ; keep non-dominated (slope, intercept)
    A, lb = [], []
    for (bv, pv), lst in rows.items():
        arr = np.array(lst)
        if pv == -1:
            a = arr[:, 0].min()
            row = np.zeros(2*nr); row[bv] = a
            A.append(row); lb.append((1 + E_MARG)*T50 + C_MARG); continue
        slope = (1 + E_MARG)*arr[:, 1]/arr[:, 0]; icpt = C_MARG/arr[:, 0]
        order = np.lexsort((-icpt, -slope)); keep = []; best_q = -np.inf
        for i in order:
            if icpt[i] > best_q + 1e-12:
                keep.append(i); best_q = icpt[i]
        for i in keep:
            row = np.zeros(2*nr); row[bv] = arr[i, 0]; row[pv] = -(1 + E_MARG)*arr[i, 1]
            A.append(row); lb.append(C_MARG)
    A = np.array(A) if A else np.zeros((0, 2*nr))
    # discrete TMS: x = TMS_MIN + TMS_STEP*n
    if integer:
        # rows: A x >= lb  ->  A(TMS_MIN + step n) >= lb  ->  (A*step) n >= lb - A*TMS_MIN
        An = A*TMS_STEP; lbn = np.array(lb) - A.sum(axis=1)*TMS_MIN
        cons = [LinearConstraint(An, lbn, np.inf)] if len(A) else []
        res = milp(c=obj*TMS_STEP + 1e-9, constraints=cons, integrality=np.ones(2*nr),
                   bounds=Bounds(np.zeros(2*nr), np.full(2*nr, NSTEP)),
                   options=dict(time_limit=time_limit, mip_rel_gap=0.0))
        ok = res.x is not None
        x = TMS_MIN + TMS_STEP*np.round(res.x) if ok else np.full(2*nr, np.nan)
    else:
        cons = [LinearConstraint(A, np.array(lb), np.inf)] if len(A) else []
        res = milp(c=obj + 1e-9, constraints=cons, integrality=np.zeros(2*nr),
                   bounds=Bounds(np.full(2*nr, TMS_MIN), np.full(2*nr, TMS_MAX)))
        ok = res.x is not None; x = res.x if ok else np.full(2*nr, np.nan)
    info = dict(status=res.status, message=res.message, feasible=bool(ok), nrows=len(A),
                struct_viol=struct_viol, sens_fail=sens_fail, ncase=ncase,
                objective=float(obj @ x) if ok else np.nan,
                gap=getattr(res, 'mip_gap', None))
    return x[:nr], x[nr:], info


def operate_times(ds, s, st, tmsP, tmsN):
    """nominal relay operating times (s) for every case of scenario s, shape
    (nL, nT, nR); inf if the relay does not operate."""
    kP, kN, o50 = _elem_coeffs(ds, s, st)
    t = np.minimum(kP*tmsP, kN*tmsN)
    return np.where(o50, np.minimum(t, T50), t)


def evaluate(ds, scen_ids, settings_of):
    """protection outcome for every case. settings_of(s) -> (st, tmsP, tmsN).
    Outcome codes: 0 selective & margin met, 1 selective but margin short,
    2 backup/upstream relay first (selectivity loss), 3 relay off the fault
    path trips (false trip), 4 nothing trips (sensitivity failure).
    Also returns primary clearing times and margins."""
    lay = ds['lay']; owner = np.asarray(ds['owner']); fwd = ds['topo_fwd']
    bk = np.array([lay.names.index(lay.backup[lay.names[p]]) if lay.backup[lay.names[p]] else -1 for p in owner])
    out, tP, marg = [], [], []
    for s in scen_ids:
        st, tp_, tn_ = settings_of(s)
        T = operate_times(ds, s, st, tp_, tn_)                     # (nL,nT,nR)
        nL, nT, nR = T.shape; L = np.arange(nL)[:, None]
        first = np.argmin(T, axis=2); tf = np.take_along_axis(T, first[..., None], axis=2)[..., 0]
        tpp = T[np.arange(nL), :, owner]                            # (nL,nT) primary time
        tbb = np.where(bk[:, None] >= 0, T[np.arange(nL), :, np.maximum(bk, 0)], np.inf)
        o = np.zeros((nL, nT), np.int8)
        none = ~np.isfinite(tf)
        off = ~none & (fwd[L, first] != 1)
        up = ~none & ~off & (first != owner[:, None]) & (tpp > tf + 1e-12)
        sel = ~(none | off | up)
        with np.errstate(invalid='ignore'):                         # inf - inf only where masked out
            m = np.where(sel & np.isfinite(tbb), tbb - ((1 + E_MARG)*tpp + C_MARG), np.inf)
        o[sel] = np.where(m[sel] >= -1e-9, 0, 1)
        o[up] = 2; o[off] = 3; o[none] = 4
        out.append(o); tP.append(np.where(sel, tpp, np.inf)); marg.append(m)
    return np.array(out), np.array(tP), np.array(marg)


def evaluate_loop(ds, scen_ids, settings_of):
    """reference (loop) implementation of evaluate, kept for testing."""
    lay = ds['lay']; owner = ds['owner']; fwd = ds['topo_fwd']
    out, tP, marg = [], [], []
    for s in scen_ids:
        st, tp_, tn_ = settings_of(s)
        T = operate_times(ds, s, st, tp_, tn_)
        nL, nT, nR = T.shape
        o = np.zeros((nL, nT), np.int8); tpri = np.full((nL, nT), np.inf); m = np.full((nL, nT), np.inf)
        for l in range(nL):
            p = owner[l]; bname = lay.backup[lay.names[p]]
            b = lay.names.index(bname) if bname else None
            for t in range(nT):
                row = T[l, t]
                first = int(np.argmin(row)); tf = row[first]
                if not np.isfinite(tf):
                    o[l, t] = 4; continue
                if fwd[l, first] != 1:
                    o[l, t] = 3; continue
                if first != p and row[p] > tf + 1e-12:
                    o[l, t] = 2; continue
                tpri[l, t] = row[p]
                if b is not None and np.isfinite(row[b]):
                    m[l, t] = row[b] - ((1 + E_MARG)*row[p] + C_MARG)
                o[l, t] = 0 if m[l, t] >= -1e-9 else 1
        out.append(o); tP.append(tpri); marg.append(m)
    return np.array(out), np.array(tP), np.array(marg)


def sensitivity_report(ds, G, st):
    """pickup sensitivity factors: primary zone (min phase-fault current over
    bolted LL at zone nodes / pickup) and remote backup."""
    lay = ds['lay']; owner = ds['owner']
    ti = [i for i, (ft, Rf) in enumerate(ds['ftypes']) if ft == 'LL' and Rf == 0.0][0]
    tg = [i for i, (ft, Rf) in enumerate(ds['ftypes']) if ft == 'SLG' and Rf == 0.0][0]
    rep = {}
    for r, name in enumerate(lay.names):
        inside = owner == r
        Imin_P = ds['Iph'][list(G)][:, inside, ti, r].min()
        Imin_N = ds['I3o'][list(G)][:, inside, tg, r].min()
        rep[name] = dict(primary_P=Imin_P/st['IsP'][r], primary_N=Imin_N/st['IsN'][r])
        bn = lay.backup[name]
        if bn:
            b = lay.names.index(bn)
            rep[name]['backup_P'] = ds['Iph'][list(G)][:, inside, ti, b].min()/st['IsP'][b]
            rep[name]['backup_N'] = ds['I3o'][list(G)][:, inside, tg, b].min()/st['IsN'][b]
    return rep
