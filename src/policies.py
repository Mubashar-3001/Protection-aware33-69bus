"""policies.py — setting-group policies, their certified design, and the
tests every policy is put through (own-group outcomes, sensitivity, load
encroachment, wrong-group operation).

A policy is a list of groups; a group is a list of scenario indices that
share one relay setting group.
"""
import itertools, numpy as np
from collections import Counter
import settings as S
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score
from sklearn.metrics import adjusted_rand_score


class Designer:
    """caches certified designs per group (frozenset of scenarios)."""

    def __init__(self, ds):
        self.ds = ds; self.ct = S.fixed_hardware(ds); self.cache = {}

    def design(self, G):
        key = frozenset(G)
        if key not in self.cache:
            st = S.group_settings(self.ds, sorted(G), self.ct)
            tp, tn, info = S.coordinate(self.ds, sorted(G), st, self.ct)
            if info['feasible']:
                o, tP, m = S.evaluate(self.ds, sorted(G), lambda s: (st, tp, tn))
                fin = np.isfinite(tP)
                info.update(obj=float(tP[fin].sum()), n_sel=int((o == 0).sum()),
                            n_case=int(o.size), outcomes=dict(Counter(o.ravel().tolist())),
                            ok=bool((o == 0).all()))
            else:
                info.update(obj=np.inf, ok=False)
            self.cache[key] = dict(st=st, tp=tp, tn=tn, info=info)
        return self.cache[key]


def load_encroachment(ds, st, ids):
    """scenarios in ids where some relay's forward load (gross and net) exceeds
    its phase pickup -> the relay would eventually trip on load."""
    bad = Counter(); n = 0
    for s in ids:
        fl = np.maximum(S.forward_load(ds, s, True), S.forward_load(ds, s, False))
        trip = fl > st['IsP']
        if trip.any():
            n += 1; bad.update([ds['lay'].names[i] for i in np.where(trip)[0]])
    return n, dict(bad)


def assess(D, groups, name=''):
    """own-group performance of a policy."""
    ds = D.ds; nS = len(ds['scen'])
    owner = {s: g for g, G in enumerate(groups) for s in G}
    assert len(owner) == nS, 'policy must cover every scenario exactly once'
    designs = [D.design(G) for G in groups]
    feas = all(d['info']['feasible'] for d in designs)
    res = dict(name=name, K=len(groups), feasible=feas, groups=[sorted(G) for G in groups])
    if not feas:
        res['infeasible_groups'] = [g for g, d in enumerate(designs) if not d['info']['feasible']]
        return res
    o, tP, m = S.evaluate(ds, list(range(nS)), lambda s: (designs[owner[s]]['st'],
                                                         designs[owner[s]]['tp'], designs[owner[s]]['tn']))
    fin = np.isfinite(tP)
    sens = [S.sensitivity_report(ds, G, d['st']) for G, d in zip(groups, designs)]
    def mins(key):
        return min(v[key] for rep in sens for v in rep.values() if key in v)
    enc = sum(load_encroachment(ds, d['st'], G)[0] for G, d in zip(groups, designs))
    res.update(outcomes={int(k): int(v) for k, v in Counter(o.ravel().tolist()).items()},
               all_selective=bool((o == 0).all()), sum_t=float(tP[fin].sum()),
               mean_t=float(tP[fin].mean()), p95_t=float(np.percentile(tP[fin], 95)),
               max_t=float(tP[fin].max()), min_margin=float(np.min(m[np.isfinite(m)])),
               sens_primary_P=mins('primary_P'), sens_primary_N=mins('primary_N'),
               sens_backup_P=mins('backup_P'), sens_backup_N=mins('backup_N'),
               load_encroach=enc)
    return res


def wrong_group(D, groups):
    """apply each group's settings to every other group's scenarios."""
    ds = D.ds; designs = [D.design(G) for G in groups]; out = []
    tot = Counter(); enc_tot = 0; pairs = 0
    for g, dg in enumerate(designs):
        for h, H in enumerate(groups):
            if g == h: continue
            o, tP, m = S.evaluate(ds, sorted(H), lambda s: (dg['st'], dg['tp'], dg['tn']))
            c = Counter(o.ravel().tolist()); enc = load_encroachment(ds, dg['st'], H)
            out.append(dict(settings=g, scenarios=h, outcomes={int(k): int(v) for k, v in c.items()},
                            encroach_scen=enc[0], encroach_relays=enc[1], n=int(o.size)))
            tot.update(c); enc_tot += enc[0]; pairs += 1
    return dict(pairs=out, total={int(k): int(v) for k, v in tot.items()}, encroach_total=enc_tot,
                n_pairs=pairs)


# ---------------------------------------------------------------- policies
def policy_robust(ds):
    return [list(range(len(ds['scen'])))]

def policy_per_state(ds):
    return [[s] for s in range(len(ds['scen']))]

def policy_by(ds, key):
    """rule-based policy: groups = distinct values of key(level, hub_state)."""
    g = {}
    for s, (lvl, hs) in enumerate(ds['scen']):
        g.setdefault(key(lvl, hs), []).append(s)
    return [g[k] for k in sorted(g, key=str)]

def policy_legacy_ids(ds):
    return [s for s, (lvl, hs) in enumerate(ds['scen']) if all(v == 'off' for v in hs.values())]


# ---------------------------------------------------------------- clustering
def signatures(ds):
    X = np.concatenate([ds['Iph'].reshape(len(ds['scen']), -1),
                        ds['I3o'].reshape(len(ds['scen']), -1)], axis=1)
    X = np.log10(1.0 + X)
    keep = X.std(axis=0) > 1e-9
    X = X[:, keep]
    return (X - X.mean(axis=0))/X.std(axis=0)

def cluster_scan(X, Ks=range(2, 7), seed=0):
    out = {}
    for K in Ks:
        for meth in ('kmeans', 'ward'):
            lab = (KMeans(K, n_init=50, random_state=seed).fit_predict(X) if meth == 'kmeans'
                   else AgglomerativeClustering(K, linkage='ward').fit_predict(X))
            out[(meth, K)] = dict(labels=lab.tolist(), silhouette=float(silhouette_score(X, lab)),
                                  db=float(davies_bouldin_score(X, lab)),
                                  ch=float(calinski_harabasz_score(X, lab)))
    return out

def cluster_stability(X, labels, K, meth, B=200, seed=1):
    rng = np.random.default_rng(seed); aris = []
    for _ in range(B):
        cols = rng.integers(0, X.shape[1], X.shape[1])
        Xb = X[:, cols]
        lab = (KMeans(K, n_init=20, random_state=int(rng.integers(1e9))).fit_predict(Xb)
               if meth == 'kmeans' else AgglomerativeClustering(K, linkage='ward').fit_predict(Xb))
        aris.append(adjusted_rand_score(labels, lab))
    return float(np.mean(aris)), float(np.percentile(aris, 5))

def labels_to_groups(labels):
    g = {}
    for s, l in enumerate(labels): g.setdefault(l, []).append(s)
    return [g[k] for k in sorted(g)]


# ---------------------------------------------------------------- exhaustive
def set_partitions(n, K):
    """all partitions of range(n) into exactly K blocks (restricted growth)."""
    def rec(i, a, m):
        if i == n:
            if m == K: yield list(a)
            return
        for v in range(min(m + 1, K)):
            a.append(v)
            yield from rec(i + 1, a, max(m, v + 1))
            a.pop()
    yield from rec(0, [], 0)

def exhaustive_classes(D, Kmax=None):
    """certified best policy for every K over partitions of load classes."""
    ds = D.ds; C = int(ds['cls'].max()) + 1
    members = {c: [s for s in range(len(ds['scen'])) if ds['cls'][s] == c] for c in range(C)}
    Kmax = C if Kmax is None else Kmax
    best = {}
    for K in range(1, Kmax + 1):
        bk = None
        for a in set_partitions(C, K):
            blocks = [[c for c in range(C) if a[c] == k] for k in range(K)]
            groups = [sum((members[c] for c in b), []) for b in blocks]
            infos = [D.design(G)['info'] for G in groups]
            if not all(i['ok'] for i in infos): continue
            obj = sum(i['obj'] for i in infos)
            if bk is None or obj < bk[0] - 1e-9: bk = (obj, blocks, groups)
        best[K] = bk
    return best, members
