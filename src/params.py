"""params.py — single source of truth for every modelling constant.

Every number that reaches the manuscript is either computed from these
values by the code, or is one of these values.  Each entry is tagged:
  [B]  benchmark data (IEEE test feeder definition)
  [S]  sourced (reference key in tex/refs.bib given in the comment)
  [A]  disclosed engineering assumption (varied in sensitivity where noted)
"""
import numpy as np

# --------------------------------------------------------------- system
VLL = 12.66e3                       # [B] nominal line-line voltage (V)
VPH = VLL / np.sqrt(3)              # phase (line-neutral) voltage
FREQ = 50.0                         # [A] Hz (Australian context)

SOURCE = dict(                      # upstream grid Thevenin at bus 1
    Ssc_MVA=100.0,                  # [A] base fault level; swept 50/100/250
    XR=10.0,                        # [A]
    Z0_over_Z1=1.0,                 # [A] solidly earthed Dyn zone-sub transformer
)
LINE_Z0_OVER_Z1 = 3.0               # [A] overhead-line zero/positive ratio (Kersting)
VSET = 1.00                         # [B] regulated bus-1 voltage (canonical benchmark)
LOAD_LEVELS = {'peak': 1.00, 'light': 0.40}   # [A] light = 40 % of peak

# voltage / thermal feasibility of hub operation (hosting check)
VMIN_PU = 0.90                      # [A] lower limit, peak + all hubs charging
VMAX_PU = 1.05                      # [A] upper limit, light load + all hubs exporting
AMPACITY_A = 300.0                  # [A] uniform branch ampacity (benchmark gives none)

# --------------------------------------------------------------- hubs
CHARGER_KW = 350.0                  # [A] one DC fast charger
HUB_CABLE_OHM = complex(0.05, 0.03) # [A] short MV cable bus -> hub switchboard
HUB_STATES = ('off', 'chg', 'exp')  # de-energised / charging / V2G export
# operating envelope: charging only at light load; export or idle at peak   [A]
ALLOWED_STATES = {'peak': ('off', 'exp'), 'light': ('off', 'chg', 'exp')}
HUB_BUSES = {'33': (14, 25, 30), '69': (21, 49, 61)}  # [A] three zones per feeder
HUB_CHARGERS = {'33': None, '69': None}            # filled from results/hosting.json

# converter fault behaviour (grid-following, balanced current control)
CONVERTER = dict(
    kf=1.2,          # [A] current limit, pu of rated; swept 1.0-2.0
    mode='P',        # [A] 'P' active-current priority (base), 'Q' reactive
                     #     priority (K-factor), 'MC' momentary cessation
    K=2.0,           # [A] reactive-current gain for mode 'Q'
    deadband=0.10,   # [A] pu voltage deadband for mode 'Q'
    Vmc=0.50,        # [A] momentary-cessation threshold for mode 'MC'
    Vpll=0.20,       # [A] below this terminal voltage the PLL angle is held
                     #     at its prefault value (no synchronising signal)
)

# --------------------------------------------------------------- faults
FAULT_SET = {        # fault type -> fault resistances (ohm)          [A]
    '3ph': (0.0, 5.0),
    'LL':  (0.0, 5.0),
    'SLG': (0.0, 10.0, 40.0, 100.0),
    'LLG': (0.0, 10.0),
}
FAULT_TYPE_SHARE = {'SLG': 0.70, 'LL': 0.15, 'LLG': 0.10, '3ph': 0.05}  # [A] typical overhead MV mix

# --------------------------------------------------------------- relays
CT_STD = (50, 75, 100, 150, 200, 300, 400, 500, 600, 800, 1000, 1200)  # [S] iec61869
CT_ALF = 20.0                       # [S] 5P20 accuracy-limit factor
OLF = 1.25                          # [A] phase pickup / max forward load current
EF_PICKUP_CT = 0.10                 # [A] earth-fault pickup, fraction of CT primary
STEP_IS = 0.01                      # [A] pickup step, fraction of CT primary
TMS_MIN, TMS_MAX, TMS_STEP = 0.05, 1.00, 0.01   # [A] typical numerical relay
CURVE = dict(k=13.5, a=1.0, Mmax=20.0)   # [S] iec60255151 very inverse; definite time above 20xIs
T50 = 0.03                          # [A] instantaneous element operate time (s)
K50 = 1.30                          # [A] 50-element margin over max through-fault
SENS_PRIMARY = 1.5                  # [A] required pickup sensitivity factor (primary)
SENS_BACKUP = 1.2                   # [A] required sensitivity factor (remote backup)

# tolerance-aware grading margin (NPAG):  m(t) = (2E_R+E_CT)/100 * t + tCB + to + ts
MARGIN = dict(ER=5.0, ECT=10.0, tCB=0.06, to=0.02, ts=0.03)   # [S] npag + [A] tCB
def margin_coeffs():
    m = MARGIN
    e = (2*m['ER'] + m['ECT'])/100.0
    c = m['tCB'] + m['to'] + m['ts']
    return e, c        # t_B >= (1+e) t_P + c

# distribution transformers (for 50-element reach through LV faults)
DT_STD_KVA = (100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500,
              3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000, 25000, 31500)  # [A] R10 preferred ratings from 100 kVA
def dt_impedance_pct(kva):          # [S] iec60076-5 minimum short-circuit impedance
    if kva <= 630: return 4.0
    if kva <= 1250: return 5.0
    if kva <= 2500: return 6.0
    if kva <= 6300: return 7.0
    if kva <= 25000: return 8.0
    return 10.0

# --------------------------------------------------------------- policies
