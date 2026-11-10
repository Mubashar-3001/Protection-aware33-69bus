"""paths.py — package-relative locations (works from any clone)."""
import os
SRC = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SRC)
RES, FIGS, TEX = (os.path.join(ROOT, d) for d in ('results', 'figs', 'tex'))
for d in (RES, FIGS): os.makedirs(d, exist_ok=True)
