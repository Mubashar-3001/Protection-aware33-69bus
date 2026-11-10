"""grid.py — feeder data, radial load flow and sequence-domain fault solver.

Conventions
  * per-phase phasors, line-to-neutral volts and amperes (SI);
  * branch k connects from-node f to to-node t (f is upstream); branch
    current is positive in the f->t ("forward", away from the source) sense;
  * injections are positive INTO the network (generator convention).

Fault model (one fault at a time, any node incl. inserted mid-line nodes)
  sequence networks Y1/Y2/Y0 with
    - grid:  EMF E behind Zs1=Zs2, Zs0 (EMF from the prefault solution);
    - lines: z1, z2=z1, z0 = LINE_Z0_OVER_Z1 * z1;
    - loads: constant admittance from prefault S and V (Y1, Y2), none in Y0
             (delta-connected distribution transformers);
    - charging hubs: constant admittance in Y1 only (balanced converter);
    - exporting hubs: positive-sequence current sources, no negative- or
      zero-sequence path, magnitude/angle from a current-limited control
      law evaluated at the hub's own terminal voltage (fixed-point loop).
"""
import numpy as np
from params import VPH, VLL, SOURCE, LINE_Z0_OVER_Z1, HUB_CABLE_OHM, CONVERTER

A = np.exp(2j*np.pi/3)
SEQ2PH = np.array([[1, 1, 1], [1, A*A, A], [1, A, A*A]])   # [I0,I1,I2] -> [Ia,Ib,Ic]

# =========================================================== feeder data
def feeder_data(name):
    if name == '33':
        BR = [(1,2,.0922,.0470),(2,3,.4930,.2511),(3,4,.3660,.1864),(4,5,.3811,.1941),
              (5,6,.8190,.7070),(6,7,.1872,.6188),(7,8,.7114,.2351),(8,9,1.0300,.7400),
              (9,10,1.0440,.7400),(10,11,.1966,.0650),(11,12,.3744,.1238),(12,13,1.4680,1.1550),
              (13,14,.5416,.7129),(14,15,.5910,.5260),(15,16,.7463,.5450),(16,17,1.2890,1.7210),
              (17,18,.7320,.5740),(2,19,.1640,.1565),(19,20,1.5042,1.3554),(20,21,.4095,.4784),
              (21,22,.7089,.9373),(3,23,.4512,.3083),(23,24,.8980,.7091),(24,25,.8960,.7011),
              (6,26,.2030,.1034),(26,27,.2842,.1447),(27,28,1.0590,.9337),(28,29,.8042,.7006),
              (29,30,.5075,.2585),(30,31,.9744,.9630),(31,32,.3105,.3619),(32,33,.3410,.5302)]
        PL = {2:100,3:90,4:120,5:60,6:60,7:200,8:200,9:60,10:60,11:45,12:60,13:60,14:120,
              15:60,16:60,17:60,18:90,19:90,20:90,21:90,22:90,23:90,24:420,25:420,26:60,
              27:60,28:60,29:120,30:200,31:150,32:210,33:60}
        QL = {2:60,3:40,4:80,5:30,6:20,7:100,8:100,9:20,10:20,11:30,12:35,13:35,14:80,
              15:10,16:20,17:20,18:40,19:40,20:40,21:40,22:40,23:50,24:200,25:200,26:25,
              27:25,28:20,29:70,30:600,31:70,32:100,33:40}
        bench = dict(loss_kW=202.68, vmin=0.9131, vmin_bus=18)        # [B] baranwu1989
    elif name == '69':
        BR = [(1,2,.0005,.0012),(2,3,.0005,.0012),(3,4,.0015,.0036),(4,5,.0251,.0294),
              (5,6,.3660,.1864),(6,7,.3811,.1941),(7,8,.0922,.0470),(8,9,.0493,.0251),
              (9,10,.8190,.2707),(10,11,.1872,.0619),(11,12,.7114,.2351),(12,13,1.0300,.3400),
              (13,14,1.0440,.3450),(14,15,1.0580,.3496),(15,16,.1966,.0650),(16,17,.3744,.1238),
              (17,18,.0047,.0016),(18,19,.3276,.1083),(19,20,.2106,.0690),(20,21,.3416,.1129),
              (21,22,.0140,.0046),(22,23,.1591,.0526),(23,24,.3463,.1145),(24,25,.7488,.2475),
              (25,26,.3089,.1021),(26,27,.1732,.0572),(3,28,.0044,.0108),(28,29,.0640,.1565),
              (29,30,.3978,.1315),(30,31,.0702,.0232),(31,32,.3510,.1160),(32,33,.8390,.2816),
              (33,34,1.7080,.5646),(34,35,1.4740,.4873),(3,36,.0044,.0108),(36,37,.0640,.1565),
              (37,38,.1053,.1230),(38,39,.0304,.0355),(39,40,.0018,.0021),(40,41,.7283,.8509),
              (41,42,.3100,.3623),(42,43,.0410,.0478),(43,44,.0092,.0116),(44,45,.1089,.1373),
              (45,46,.0009,.0012),(4,47,.0034,.0084),(47,48,.0851,.2083),(48,49,.2898,.7091),
              (49,50,.0822,.2011),(8,51,.0928,.0473),(51,52,.3319,.1114),(9,53,.1740,.0886),
              (53,54,.2030,.1034),(54,55,.2842,.1447),(55,56,.2813,.1433),(56,57,1.5900,.5337),
              (57,58,.7837,.2630),(58,59,.3042,.1006),(59,60,.3861,.1172),(60,61,.5075,.2585),
              (61,62,.0974,.0496),(62,63,.1450,.0738),(63,64,.7105,.3619),(64,65,1.0410,.5302),
              (11,66,.2012,.0611),(66,67,.0047,.0014),(12,68,.7394,.2444),(68,69,.0047,.0016)]
        PL = {6:2.6,7:40.4,8:75,9:30,10:28,11:145,12:145,13:8,14:8,16:45.5,17:60,18:60,
              20:1,21:114,22:5,24:28,26:14,27:14,28:26,29:26,33:14,34:19.5,35:6,36:26,37:26,
              39:24,40:24,41:1.2,43:6,45:39.22,46:39.22,48:79,49:384.7,50:384.7,51:40.5,
              52:3.6,53:4.35,54:26.4,55:24,59:100,61:1244,62:32,64:227,65:59,66:18,67:18,
              68:28,69:28}
        QL = {6:2.2,7:30,8:54,9:22,10:19,11:104,12:104,13:5.5,14:5.5,16:30,17:35,18:35,
              20:.6,21:81,22:3.5,24:20,26:10,27:10,28:18.6,29:18.6,33:10,34:14,35:4,36:18.55,
              37:18.55,39:17,40:17,41:1,43:4.3,45:26.3,46:26.3,48:56.4,49:274.5,50:274.5,
              51:28.3,52:2.7,53:3.5,54:19,55:17.2,59:72,61:888,62:23,64:162,65:42,66:13,
              67:13,68:20,69:20}
        bench = dict(loss_kW=224.95, vmin=0.9092, vmin_bus=65)        # [B] baranwu1989b
    else:
        raise ValueError(name)
    return BR, PL, QL, bench


# =========================================================== network
class Network:
    """Radial network. Node 0 is the regulated source bus (bus 1)."""

    def __init__(self, name, hubs=None, ssc=None, xr=None, z0r=None):
        BR, PL, QL, bench = feeder_data(name)
        self.name, self.bench = name, bench
        nb = max(max(f, t) for f, t, *_ in BR)
        self.labels = list(range(1, nb + 1))          # node index i -> label
        self.f, self.t, self.z1 = [], [], []
        for f, t, r, x in BR:
            self.f.append(f - 1); self.t.append(t - 1); self.z1.append(complex(r, x))
        self.bus_branch = {t - 1: k for k, (f, t, *_) in enumerate(BR)}   # node -> its incoming branch
        self.SL = np.zeros(nb, complex)                # three-phase load, VA
        for b, p in PL.items():
            self.SL[b - 1] = (p + 1j*QL.get(b, 0.0))*1e3
        ssc = SOURCE['Ssc_MVA'] if ssc is None else ssc
        xr = SOURCE['XR'] if xr is None else xr
        zm = VLL**2/(ssc*1e6); th = np.arctan(xr)
        self.Zs1 = zm*complex(np.cos(th), np.sin(th))
        self.Zs0 = SOURCE['Z0_over_Z1']*self.Zs1
        self.z0r = LINE_Z0_OVER_Z1 if z0r is None else z0r
        self.hubs = {}                                 # bus label -> dict
        for b, P_MW in (hubs or {}).items():
            self.add_hub(b, P_MW)
        self._finalise()

    # ---- topology helpers
    def add_hub(self, bus, P_MW):
        i = len(self.labels); self.labels.append(f'H{bus}')
        k = len(self.f)
        self.f.append(bus - 1); self.t.append(i); self.z1.append(HUB_CABLE_OHM)
        self.bus_branch[i] = k
        self.SL = np.append(self.SL, 0j)
        P = P_MW*1e6
        self.hubs[bus] = dict(node=i, branch=k, P=P, Irated=P/(np.sqrt(3)*VLL))

    def _finalise(self):
        self.n = len(self.labels)
        self.f = np.array(self.f); self.t = np.array(self.t)
        self.z1 = np.array(self.z1); self.z0 = self.z0r*self.z1
        self.children = [[] for _ in range(self.n)]
        for k in range(len(self.f)):
            self.children[self.f[k]].append(self.t[k])
        order, st = [], [0]
        while st:
            u = st.pop(); order.append(u); st.extend(self.children[u])
        self.order = order                              # parents before children
        self.parent_branch = np.full(self.n, -1)
        for k in range(len(self.f)):
            self.parent_branch[self.t[k]] = k

    def idx(self, label):
        return self.labels.index(label)

    def path_to_root(self, i):
        p = [i]
        while p[-1] != 0:
            p.append(self.f[self.parent_branch[p[-1]]])
        return p

    def subtree(self, i):
        s, k = [i], 0
        while k < len(s):
            s.extend(self.children[s[k]]); k += 1
        return s

    # ---- loads/hub injections for a scenario
    def injections(self, load_scale, hub_state):
        """three-phase complex power drawn at each node (VA); hubs as PQ."""
        S = self.SL*load_scale
        S = S.copy()
        for b, h in self.hubs.items():
            st = hub_state.get(b, 'off')
            if st == 'chg': S[h['node']] += h['P']
            elif st == 'exp': S[h['node']] -= h['P']
        return S

    # ---- load flow (backward/forward sweep, constant power)
    def load_flow(self, load_scale=1.0, hub_state=None, vset=1.0, tol=1e-9, itmax=500):
        S = self.injections(load_scale, hub_state or {})
        V = np.full(self.n, vset*VPH, complex)
        nbr = len(self.f)
        for it in range(itmax):
            Inode = np.conj(S/3.0/V)                    # per-phase current drawn
            Ibr = np.zeros(nbr, complex)
            acc = Inode.copy()
            for u in reversed(self.order):
                if u == 0: continue
                k = self.parent_branch[u]
                Ibr[k] = acc[u]
                acc[self.f[k]] += acc[u]
            Vn = V.copy(); Vn[0] = vset*VPH
            for u in self.order:
                if u == 0: continue
                k = self.parent_branch[u]
                Vn[u] = Vn[self.f[k]] - self.z1[k]*Ibr[k]
            dv = np.max(np.abs(Vn - V)); V = Vn
            if dv < tol: break
        loss = 3*np.sum(np.abs(Ibr)**2*self.z1.real)
        Isrc = sum(Ibr[k] for k in range(nbr) if self.f[k] == 0)
        return dict(V=V, Ibr=Ibr, loss=loss, S=S, Isrc=Isrc, iters=it, converged=dv < tol)


# =========================================================== fault solver
def _insert_node(net, k, x):
    """Return arrays for a network with branch k split at fraction x (0<x<1).
    New node index = net.n; branch k becomes f->m, new branch m->t."""
    f = np.append(net.f.copy(), net.n); t = np.append(net.t.copy(), net.t[k])
    z1 = np.append(net.z1.copy(), (1 - x)*net.z1[k]); z1[k] = x*net.z1[k]
    t[k] = net.n
    return f, t, z1


class FaultModel:
    """Pre-builds prefault state for one scenario; solves faults at any node
    (or at fraction x along any branch)."""

    def __init__(self, net, load_scale, hub_state, vset=1.0, conv=None):
        self.net, self.hub_state = net, dict(hub_state)
        self.conv = dict(CONVERTER if conv is None else conv)
        lf = net.load_flow(load_scale, hub_state, vset)
        assert lf['converged'], 'load flow did not converge'
        self.lf = lf
        self.Vpre, self.Ipre = lf['V'], lf['Ibr']
        self.E = lf['V'][0] + net.Zs1*lf['Isrc']        # Thevenin EMF behind Zs
        # constant-admittance loads (per phase) from prefault S/V
        S = net.SL*load_scale
        self.yL = np.conj(S/3.0)/np.abs(self.Vpre)**2
        self.yH = np.zeros(net.n, complex)               # charging hubs -> Y1 only
        self.src = {}                                    # exporting hubs -> sources
        for b, h in net.hubs.items():
            st = hub_state.get(b, 'off')
            if st == 'chg':
                self.yH[h['node']] = h['P']/3.0/np.abs(self.Vpre[h['node']])**2
            elif st == 'exp':
                self.src[b] = h

    # ---- network matrices for a (possibly split) topology
    def _Y(self, f, t, z1, n, yload1, yload2):
        Y1 = np.zeros((n, n), complex); Y0 = np.zeros((n, n), complex)
        y1 = 1/z1; y0 = 1/(self.net.z0r*z1)
        for k in range(len(f)):
            a, b = f[k], t[k]
            Y1[a, a] += y1[k]; Y1[b, b] += y1[k]; Y1[a, b] -= y1[k]; Y1[b, a] -= y1[k]
            Y0[a, a] += y0[k]; Y0[b, b] += y0[k]; Y0[a, b] -= y0[k]; Y0[b, a] -= y0[k]
        Y2 = Y1.copy()
        Y1[0, 0] += 1/self.net.Zs1; Y2[0, 0] += 1/self.net.Zs1; Y0[0, 0] += 1/self.net.Zs0
        Y1[np.diag_indices(n)] += yload1
        Y2[np.diag_indices(n)] += yload2
        return Y1, Y2, Y0

    def topology(self, at_branch=None, x=None):
        """Build (and cache) Z matrices. at_branch=None -> original nodes."""
        net = self.net
        if at_branch is None:
            f, t, z1, n = net.f, net.t, net.z1, net.n
            yl = self.yL; yh = self.yH
            Vpre = self.Vpre
        else:
            f, t, z1 = _insert_node(net, at_branch, x); n = net.n + 1
            yl = np.append(self.yL, 0j); yh = np.append(self.yH, 0j)
            k = at_branch
            Vpre = np.append(self.Vpre, self.Vpre[net.f[k]] - x*net.z1[k]*self.Ipre[k])
        Y1, Y2, Y0 = self._Y(f, t, z1, n, yl + yh, yl)
        Z1, Z2, Z0 = np.linalg.inv(Y1), np.linalg.inv(Y2), np.linalg.inv(Y0)
        return dict(f=f, t=t, z1=z1, n=n, Z1=Z1, Z2=Z2, Z0=Z0, Vpre=Vpre)

    # ---- converter control law (current injected, A phasor)
    def _ctrl(self, h, V, Vpre, ppre, latch):
        """Grid-following, balanced current control, current limit kf.
        latch['pll'] / latch['mc'] are decided once, from the terminal voltage
        at fault inception (first iterate: network solved with every converter
        still injecting its prefault current), and then held for the fault
        duration."""
        c = self.conv; kf = c['kf']; Ir = h['Irated']
        v = abs(V)/VPH; vpre = abs(Vpre)/VPH
        if 'pll' not in latch:                       # fault inception
            latch['pll'] = bool(v < c['Vpll'])
            latch['mc'] = bool(c['mode'] == 'MC' and v < c['Vmc'])
        if latch['mc']: return 0j
        th = np.angle(Vpre) if latch['pll'] else np.angle(V)
        iq = 0.0
        if c['mode'] == 'Q':                     # continuous K-factor beyond deadband
            iq = min(c['K']*max(0.0, (vpre - v) - c['deadband']), kf)
        id_ = ppre/max(v, 1e-3)
        id_ = np.sign(id_)*min(abs(id_), np.sqrt(max(kf**2 - iq**2, 0.0)))
        return (id_ - 1j*iq)*Ir*np.exp(1j*th)

    def solve(self, topo, F, ftype, Rf=0.0, itmax=200, tol=1e-7):
        """Fault at node F of topology topo. Returns sequence node voltages,
        sequence branch currents (f->t) and fault currents."""
        Z1, Z2, Z0, n = topo['Z1'], topo['Z2'], topo['Z0'], topo['n']
        J = np.zeros(n, complex); J[0] = self.E/self.net.Zs1
        hubs = list(self.src.items())
        Ih = {}
        for b, h in hubs:                                       # prefault export current
            i = h['node']; Ih[b] = np.conj(h['P']/3.0/self.Vpre[i])     # S = V conj(I) = +P/3 (export)
        z1F, z2F, z0F = Z1[F, F], Z2[F, F], Z0[F, F]
        latch = {b: {} for b, _ in hubs}
        converged = True
        for it in range(itmax):
            Jt = J.copy()
            for b, h in hubs: Jt[h['node']] += Ih[b]
            V1oc = Z1 @ Jt
            vf = V1oc[F]
            if ftype == '3ph':
                I1 = vf/(z1F + Rf); I2 = I0 = 0j
            elif ftype == 'LL':
                I1 = vf/(z1F + z2F + Rf); I2 = -I1; I0 = 0j
            elif ftype == 'SLG':
                I1 = vf/(z1F + z2F + z0F + 3*Rf); I2 = I1; I0 = I1
            elif ftype == 'LLG':
                zx = z0F + 3*Rf
                I1 = vf/(z1F + z2F*zx/(z2F + zx)); I2 = -I1*zx/(z2F + zx); I0 = -I1*z2F/(z2F + zx)
            elif ftype == 'none':
                I1 = I2 = I0 = 0j
            else:
                raise ValueError(ftype)
            V1 = V1oc - Z1[:, F]*I1; V2 = -Z2[:, F]*I2; V0 = -Z0[:, F]*I0
            if not hubs: break
            dmax = 0.0
            for b, h in hubs:
                i = h['node']
                new = self._ctrl(h, V1[i], self.Vpre[i], +1.0, latch[b])
                upd = 0.5*Ih[b] + 0.5*new
                dmax = max(dmax, abs(upd - Ih[b])/h['Irated']); Ih[b] = upd
            if dmax < tol: break
        else:
            converged = False
        f, t, z1 = topo['f'], topo['t'], topo['z1']
        I1b = (V1[f] - V1[t])/z1; I2b = (V2[f] - V2[t])/z1
        I0b = (V0[f] - V0[t])/(self.net.z0r*z1)
        return dict(V1=V1, V2=V2, V0=V0, I1b=I1b, I2b=I2b, I0b=I0b,
                    IF=np.array([I0, I1, I2]), Ih=Ih, iters=it + 1, converged=converged,
                    latch=latch)


def phase_currents(I0b, I1b, I2b):
    """sequence -> phase branch currents, shape (3, nbranch)."""
    return SEQ2PH @ np.vstack([I0b, I1b, I2b])
