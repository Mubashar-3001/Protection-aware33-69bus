MATLAB versions of Figs. 2-6
=============================

Protection-aware integration of vehicle-to-grid charging hubs:
when do directional overcurrent relays need adaptive setting groups?

How to use
----------
1. Unzip this folder anywhere and open it in MATLAB (R2020b or later; tested with R2026a).
2. Run  make_all_figures  (or any single script, e.g. fig4_policy_size).
3. The figures are written to the subfolder figures/ as
     figN_*.fig   editable MATLAB figure (open with openfig or double-click)
     figN_*.pdf   vector graphics for LaTeX
     figN_*.png   300 dpi raster

Changing legends, labels, colours or size
-----------------------------------------
Every script starts with a block

    %% ---------------- USER SETTINGS ----------------
    legendText = {...};   xLabel = ...;   yLabel = ...;   colours ...;   fontName ...;   figSize ...
    %% -----------------------------------------------

Edit the text there and rerun the script. You can also open a .fig file and edit the legend
interactively (double-click the legend text, or use the Property Inspector).

Files
-----
  fig2_hosting.m       Fig. 2  largest single hub each bus can host
  fig3_impact.m        Fig. 3  change of primary/backup relay current vs. all hubs off
  fig4_policy_size.m   Fig. 4  mean clearing time vs. number of setting groups
  fig5_gain_risk.m     Fig. 5  gain vs. expected energy lost per wrong-group event
  fig6_boundary.m      Fig. 6  hubs scaled beyond the hosting limit (33-bus sweep)
  make_all_figures.m   runs all five scripts
  data/*.csv           the plotted data (exported from the Python results by src/export_data.py;
                       values rounded to 6 significant digits; full precision in GTD_V2G_data.xlsx)

Fig. 1 (one-line diagrams) is a drawing, not a data plot: its editable sources are in the
diagrams package (draw.io and Graphviz).
