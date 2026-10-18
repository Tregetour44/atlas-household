#!/usr/bin/env python3
"""Draws small-multiple learning curves (one panel per metric, one y-axis
each) from curves.py's CSV as a static SVG. Standard library only.

  python3 plot_curves.py curves.csv out.svg
"""
import csv
import sys
from collections import defaultdict

PANELS = [
    ("train", "loss", "Training loss (mini-batch)"),
    ("validation", "loss", "Validation loss (in-loop)"),
    ("validation", "recall_at_no_faph", "Validation recall at 0 FA/h (in-loop, 3.2 h ambient)"),
    ("validation", "average_viable_recall", "Validation average viable recall (in-loop)"),
]
SERIES = ["s1", "s2", "s3"]  # categorical slots, fixed order by run

W, H = 420, 210
ML, MR, MT, MB = 52, 16, 34, 34


def main():
    rows = list(csv.DictReader(open(sys.argv[1])))
    runs = sorted({r["run"] for r in rows}, key=lambda r: (r != "pilot", r))
    data = defaultdict(list)
    for r in rows:
        data[(r["run"], r["split"], r["metric"])].append((int(r["step"]), float(r["value"])))
    cols = 2
    total_w = cols * W
    total_h = ((len(PANELS) + 1) // cols) * H + 40
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} {total_h}" '
           f'width="{total_w}" height="{total_h}" font-family="system-ui, sans-serif" font-size="11">',
           """<style>
  svg { --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --grid:#e4e3df; --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; }
  @media (prefers-color-scheme: dark) {
    svg { --surface:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --grid:#3a3936; --s1:#3987e5; --s2:#d95926; --s3:#199e70; }
  }
  .bg { fill: var(--surface); } .t { fill: var(--ink); } .m { fill: var(--ink2); }
  .g { stroke: var(--grid); stroke-width: 1; } .ax { stroke: var(--ink2); stroke-width: 1; }
  .s1 { stroke: var(--s1); } .s2 { stroke: var(--s2); } .s3 { stroke: var(--s3); }
  .k1 { fill: var(--s1); } .k2 { fill: var(--s2); } .k3 { fill: var(--s3); }
  .line { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
</style>""",
           f'<rect class="bg" width="{total_w}" height="{total_h}"/>']
    # Legend (always present for >= 2 series)
    lx = ML
    for i, run in enumerate(runs):
        out.append(f'<rect class="k{i + 1}" x="{lx}" y="12" width="12" height="4" rx="2"/>')
        out.append(f'<text class="t" x="{lx + 16}" y="18">{run}</text>')
        lx += 16 + 8 * len(run) + 24
    for p, (split, metric, title) in enumerate(PANELS):
        ox, oy = (p % cols) * W, 40 + (p // cols) * H
        series = [(i, run, sorted(data[(run, split, metric)])) for i, run in enumerate(runs)
                  if data[(run, split, metric)]]
        if not series:
            continue
        xs = [s for _, _, pts in series for s, _ in pts]
        ys = [v for _, _, pts in series for _, v in pts]
        x0, x1 = 0, max(xs)
        y0, y1 = (0.0, 1.0) if "recall" in metric else (0.0, max(ys) * 1.05 or 1)
        pw, ph = W - ML - MR, H - MT - MB

        def X(s):
            return ox + ML + (s - x0) / (x1 - x0 or 1) * pw

        def Y(v):
            return oy + MT + ph - (min(max(v, y0), y1) - y0) / (y1 - y0) * ph

        out.append(f'<text class="t" x="{ox + ML}" y="{oy + 18}" font-weight="600">{title}</text>')
        for k in range(5):
            v = y0 + (y1 - y0) * k / 4
            out.append(f'<line class="g" x1="{ox + ML}" x2="{ox + ML + pw}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>')
            out.append(f'<text class="m" x="{ox + ML - 6}" y="{Y(v) + 4:.1f}" text-anchor="end">{v:.2g}</text>')
        for k in range(5):
            s = x0 + (x1 - x0) * k / 4
            out.append(f'<text class="m" x="{X(s):.1f}" y="{oy + MT + ph + 16}" text-anchor="middle">{int(s / 1000)}k</text>')
        out.append(f'<line class="ax" x1="{ox + ML}" x2="{ox + ML + pw}" y1="{oy + MT + ph}" y2="{oy + MT + ph}"/>')
        for i, run, pts in series:
            if split == "train" and len(pts) > 200:
                pts = pts[:: len(pts) // 200]
            d = " ".join(f"{'M' if j == 0 else 'L'}{X(s):.1f},{Y(v):.1f}" for j, (s, v) in enumerate(pts))
            out.append(f'<path class="line s{i + 1}" d="{d}"><title>{run} {metric}</title></path>')
            s_last, v_last = pts[-1]
            out.append(f'<text class="t" x="{X(s_last) - 2:.1f}" y="{Y(v_last) - 6:.1f}" text-anchor="end">'
                       f'{run} {v_last:.3g}</text>')
        out.append(f'<text class="m" x="{ox + ML + pw}" y="{oy + MT + ph + 30}" text-anchor="end">training step</text>')
    out.append("</svg>")
    open(sys.argv[2], "w").write("\n".join(out))


if __name__ == "__main__":
    main()
