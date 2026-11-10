"""make_diagrams.py — editable sources of Fig. 1 (one-line diagrams of both feeders).

usage: python make_diagrams.py
  -> diagrams/oneline.drawio   open in https://app.diagrams.net (File > Open from > Device)
  -> diagrams/oneline.dot      paste into https://dreampuf.github.io/GraphvizOnline (engine: neato)
                               or run: neato -Tpdf oneline.dot -o oneline_graphviz.pdf
The geometry is the same as in figs.py (oneline_layout), so both files reproduce Fig. 1:
buses, branches, feeder breaker / trunk reclosers (R), lateral reclosers (L) and the V2G hubs
with their hosting-feasible ratings. Bus numbers are on a separate draw.io layer ('Bus numbers',
hidden by default) and are commented out in the .dot file.
"""
import os, sys, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import oneline_layout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'diagrams')
C_R, C_L, C_HUB, INK, INK2, LINE = '#2a78d6', '#eb6834', '#1baf7a', '#0b0b0b', '#52514e', '#9b9a95'


def build():
    """both feeders in one canvas: lists of nodes and edges in data units (y up)."""
    nodes, edges, texts = [], [], []
    y_off = {'33': 0.0, '69': -5.6}                 # 69-bus block below the 33-bus block
    for name in ('33', '69'):
        BR, pos, rel, hubs = oneline_layout(name)
        dy = y_off[name]; P = {b: (x, y + dy) for b, (x, y) in pos.items()}
        ymax = max(y for _, y in P.values())
        texts.append(dict(id=f't{name}', x=-0.6, y=ymax + 0.75, text=f'IEEE {name}-bus', size=11, anchor='w'))
        for b, (x, y) in P.items():
            nodes.append(dict(id=f'b{name}_{b}', kind='bus', x=x, y=y, label=str(b)))
        nodes.append(dict(id=f'src{name}', kind='source', x=P[1][0] - 0.45, y=P[1][1], label='~'))
        for k, (f, t) in enumerate(BR):
            (x1, y1), (x2, y2) = P[f], P[t]
            pts = [(x1, y2)] if (y1 != y2 and x1 != x2) else []
            edges.append(dict(id=f'e{name}_{f}_{t}', s=f'b{name}_{f}', t=f'b{name}_{t}', pts=pts))
        for r, (x, y) in rel.items():
            y += dy
            nodes.append(dict(id=f'r{name}_{r}', kind='R' if r.startswith('R') else 'L', x=x, y=y, label=r,
                              below=(y - dy) <= 0))
        for b, MW in hubs.items():
            x, y = P[b]
            nodes.append(dict(id=f'h{name}_{b}', kind='hub', x=x, y=y, label=f'H{b}<br>{MW:.2f} MW',
                              text=f'H{b}\\n{MW:.2f} MW', below=(y - dy) < 0))
    # legend (top right, as in Fig. 1)
    lx, ly = 13.6, 2.2
    for i, (kind, txt) in enumerate((('R', 'trunk breaker / recloser (R)'), ('L', 'lateral recloser (L)'),
                                     ('hub', 'V2G hub with hub breaker (H)'))):
        nodes.append(dict(id=f'leg{i}', kind=kind, x=lx, y=ly - 0.42*i, label='', legend=txt))
    return nodes, edges, texts


# ------------------------------------------------------------------ draw.io
def drawio(nodes, edges, texts, path):
    S = 40.0; X0, Y0 = 60.0, 140.0                      # px per data unit, origin
    X = lambda x: X0 + S*x; Y = lambda y: Y0 - S*y
    size = {'bus': 6, 'source': 16, 'R': 10, 'L': 10, 'hub': 14}
    style = {
        'bus': f'ellipse;shape=ellipse;perimeter=ellipsePerimeter;whiteSpace=wrap;html=1;aspect=fixed;fillColor={INK2};strokeColor=none;',
        'source': f'text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;fontSize=16;fontColor={INK};fontFamily=Times New Roman;',
        'R': f'rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor={C_R};strokeWidth=2;',
        'L': f'rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor={C_L};strokeWidth=2;',
        'hub': f'rhombus;shape=rhombus;perimeter=rhombusPerimeter;whiteSpace=wrap;html=1;fillColor={C_HUB};strokeColor={INK};strokeWidth=1;',
    }
    cells = ['<mxCell id="0"/>', '<mxCell id="1" value="Fig. 1" parent="0"/>',
             '<mxCell id="busnum" value="Bus numbers" style="locked=0;" parent="0" visible="0"/>']
    for n in nodes:
        w = size[n['kind']]; x, y = X(n['x']) - w/2, Y(n['y']) - w/2
        val = html.escape(n['label']) if n['kind'] == 'source' else ''
        cells.append(f'<mxCell id="{n["id"]}" value="{val}" style="{style[n["kind"]]}" vertex="1" parent="1">'
                     f'<mxGeometry x="{x:.1f}" y="{y:.1f}" width="{w}" height="{w}" as="geometry"/></mxCell>')
        if n['kind'] in ('R', 'L', 'hub') and n['label']:
            lab = html.escape(n['label'].replace('<br>', '\n')).replace('\n', '&lt;br&gt;')
            h = 26 if n['kind'] == 'hub' else 12
            ty = (Y(n['y']) + w/2 + 1) if n.get('below') else (Y(n['y']) - w/2 - h - 1)
            cells.append(f'<mxCell id="{n["id"]}_lbl" value="{lab}" style="text;html=1;strokeColor=none;fillColor=none;labelBackgroundColor=#ffffff;align=center;verticalAlign=middle;'
                         f'fontSize=8;fontColor={INK};fontFamily=Times New Roman;" vertex="1" parent="1"><mxGeometry x="{X(n["x"]) - 30:.1f}" '
                         f'y="{ty:.1f}" width="60" height="{h}" as="geometry"/></mxCell>')
        if n['kind'] == 'bus':
            cells.append(f'<mxCell id="{n["id"]}_num" value="{n["label"]}" style="text;html=1;strokeColor=none;fillColor=none;align=center;'
                         f'verticalAlign=bottom;fontSize=6;fontColor=#8a8984;fontFamily=Times New Roman;" vertex="1" parent="busnum">'
                         f'<mxGeometry x="{X(n["x"]) - 10:.1f}" y="{Y(n["y"]) - 14:.1f}" width="20" height="10" as="geometry"/></mxCell>')
        if n.get('legend'):
            cells.append(f'<mxCell id="{n["id"]}_txt" value="{html.escape(n["legend"])}" style="text;html=1;strokeColor=none;fillColor=none;align=left;'
                         f'verticalAlign=middle;fontSize=8;fontColor={INK};fontFamily=Times New Roman;" vertex="1" parent="1"><mxGeometry '
                         f'x="{X(n["x"]) + 10:.1f}" y="{Y(n["y"]) - 8:.1f}" width="170" height="16" as="geometry"/></mxCell>')
    for e in edges:
        pts = ''.join(f'<mxPoint x="{X(px):.1f}" y="{Y(py):.1f}"/>' for px, py in e['pts'])
        arr = f'<Array as="points">{pts}</Array>' if pts else ''
        cells.append(f'<mxCell id="{e["id"]}" style="endArrow=none;html=1;rounded=0;strokeColor={LINE};strokeWidth=1.5;" '
                     f'edge="1" parent="1" source="{e["s"]}" target="{e["t"]}"><mxGeometry relative="1" as="geometry">'
                     f'{arr}</mxGeometry></mxCell>')
    for t in texts:
        cells.append(f'<mxCell id="{t["id"]}" value="{html.escape(t["text"])}" style="text;html=1;strokeColor=none;fillColor=none;align=left;'
                     f'verticalAlign=middle;fontSize={t["size"]};fontColor={INK};fontFamily=Times New Roman;" vertex="1" parent="1"><mxGeometry '
                     f'x="{X(t["x"]):.1f}" y="{Y(t["y"]) - 10:.1f}" width="140" height="20" as="geometry"/></mxCell>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<mxfile host="app.diagrams.net" type="device">\n'
           '  <diagram id="fig1-oneline" name="Fig. 1 one-line diagrams">\n'
           '    <mxGraphModel dx="1200" dy="800" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
           'fold="1" page="1" pageScale="1" pageWidth="1100" pageHeight="760" math="0" shadow="0">\n      <root>\n        '
           + '\n        '.join(cells) + '\n      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>\n')
    open(path, 'w').write(xml)


# ------------------------------------------------------------------ Graphviz
def dot(nodes, edges, texts, path):
    S = 0.42                                             # inches per data unit
    p = lambda x, y: f'"{S*x:.3f},{S*y:.3f}!"'
    L = ['// Fig. 1 - one-line diagrams of the IEEE 33- and 69-bus feeders (generated by src/make_diagrams.py)',
         '// Graphviz Online: https://dreampuf.github.io/GraphvizOnline  (set the engine to "neato")',
         '// Command line:    neato -Tpdf oneline.dot -o oneline_graphviz.pdf',
         'graph oneline {',
         '  layout=neato; splines=false; overlap=true; outputorder=edgesfirst; bgcolor=white; pad=0.2;',
         f'  node [fontname="Times-Roman", fontsize=8, fontcolor="{INK}"];',
         f'  edge [color="{LINE}", penwidth=1.3];']
    for t in texts:
        L.append(f'  {t["id"]} [shape=plaintext, label="{t["text"]}", fontsize=11, pos={p(t["x"] + 1.0, t["y"])}];')
    for n in nodes:
        k = n['kind']
        if k == 'bus':
            L.append(f'  {n["id"]} [shape=circle, style=filled, fillcolor="{INK2}", color="{INK2}", width=0.06, '
                     f'fixedsize=true, label="", pos={p(n["x"], n["y"])}];  // bus {n["label"]}')
        elif k == 'source':
            L.append(f'  {n["id"]} [shape=plaintext, label="~", fontsize=16, pos={p(n["x"], n["y"])}];')
        elif k in ('R', 'L'):
            col = C_R if k == 'R' else C_L
            L.append(f'  {n["id"]} [shape=square, style=filled, fillcolor=white, color="{col}", penwidth=1.6, width=0.11, '
                     f'fixedsize=true, label="", pos={p(n["x"], n["y"])}];')
        elif k == 'hub':
            L.append(f'  {n["id"]} [shape=diamond, style=filled, fillcolor="{C_HUB}", color="{INK}", penwidth=0.6, width=0.16, '
                     f'height=0.16, fixedsize=true, label="", pos={p(n["x"], n["y"])}];')
        if k in ('R', 'L', 'hub') and n['label']:
            txt = n.get('text', n['label'])
            dy = (-0.52 if k == 'hub' else -0.3) if n.get('below') else (0.55 if k == 'hub' else 0.3)
            L.append(f'  {n["id"]}_lbl [shape=plaintext, style=filled, fillcolor=white, margin=0, width=0, height=0, label="{txt}", '
                     f'pos={p(n["x"], n["y"] + dy)}];')
        if n.get('legend'):                              # left-justified text box starting right of the symbol
            L.append(f'  {n["id"]}_txt [shape=plaintext, label="{n["legend"]}\\l", width=2.4, fixedsize=true, '
                     f'pos={p(n["x"] + (0.18 + 1.2)/S, n["y"])}];')
    for e in edges:
        if e['pts']:
            (cx, cy), = e['pts']
            L.append(f'  {e["id"]}_c [shape=point, width=0.001, color="{LINE}", pos={p(cx, cy)}];')
            L.append(f'  {e["s"]} -- {e["id"]}_c -- {e["t"]};')
        else:
            L.append(f'  {e["s"]} -- {e["t"]};')
    L.append('}')
    open(path, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    nodes, edges, texts = build()
    drawio(nodes, edges, texts, os.path.join(OUT, 'oneline.drawio'))
    dot(nodes, edges, texts, os.path.join(OUT, 'oneline.dot'))
    print('wrote diagrams/oneline.drawio and diagrams/oneline.dot')
