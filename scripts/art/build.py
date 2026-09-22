"""
Builds every image in /assets (the README art).

Art direction: retro-futurist / oriental-tech / minimal — sumi black, bone white, one vermilion accent (shu),
cyan used sparingly for "live" signals. Type: Michroma, IBM Plex Mono/Sans, Zen Kaku Gothic New, Shippori Mincho.

    pip install fonttools uharfbuzz brotli
    python scripts/art/build.py              # every asset
    python scripts/art/build.py header       # one asset (see ASSETS at the bottom)

All text is shaped with HarfBuzz and converted to vector outlines (fonts are downloaded once, SIL OFL licensed),
so the SVGs need nothing external to render: GitHub serves README images with a CSP that blocks web fonts.
"""
import math
import os
import random
import sys
import xml.etree.ElementTree as ET

from svgkit import Doc, font, num, icon, fetch_fonts

fetch_fonts()

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("NEO_OUT") or os.path.join(HERE, "..", "..", "assets")
os.makedirs(OUT, exist_ok=True)

INK = "#08080A"
PANEL = "#0C0C0F"
EDGE = "#24242A"
EDGE2 = "#34343C"
BONE = "#E8E4DC"
GREY = "#8C8C95"
DIM = "#55555E"
RED = "#F0412A"
CYAN = "#6FE3E8"

BASE_CSS = """
.fi{animation:fi .6s ease-out both}
@keyframes fi{from{opacity:0}to{opacity:1}}
.up{animation:up .8s cubic-bezier(.2,.7,.2,1) both}
@keyframes up{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.fl{animation:fl .55s linear both}
@keyframes fl{0%{opacity:0}35%{opacity:.9}50%{opacity:.15}65%{opacity:1}80%{opacity:.6}100%{opacity:1}}
.blink{animation:blink 1.6s steps(1) infinite}
@keyframes blink{0%,60%{opacity:1}61%,100%{opacity:.15}}
.cur{animation:cur 1.1s steps(1) infinite}
@keyframes cur{0%,50%{opacity:1}51%,100%{opacity:0}}
"""


def save(d, name):
    path = os.path.join(OUT, name)
    size = d.save(path)
    ET.parse(path)                      # never ship broken XML
    print(f"  {name:30s} {size / 1024:6.1f} KB")
    return path


def T(d, fk, s, x, y, size, fill=BONE, anchor="start", ls=0.0, attrs="", ga=None):
    return d.text(fk, s, x, y, size, anchor=anchor, ls=ls, fill=fill, attrs=attrs, glyph_attrs=ga)[0]


def W(d, fk, s, size, ls=0.0):
    return d.measure(fk, s, size, ls)


def stagger(t0, step):
    """glyph_attrs callback: flicker each glyph in, one after another."""
    return lambda i, cl, gx: f'class="fl" style="animation-delay:{num(t0 + cl * step, 3)}s"'


def square(x, y, s, fill=RED, extra=""):
    return f'<rect x="{num(x)}" y="{num(y)}" width="{num(s)}" height="{num(s)}" fill="{fill}" {extra}/>'


def brackets(x, y, w, h, L=16, col=BONE, op=.45, sw=1.2):
    p = (f"M{x} {y + L}V{y}H{x + L} M{x + w - L} {y}H{x + w}V{y + L} "
         f"M{x + w} {y + h - L}V{y + h}H{x + w - L} M{x + L} {y + h}H{x}V{y + h - L}")
    return f'<path d="{p}" fill="none" stroke="{col}" stroke-opacity="{op}" stroke-width="{sw}"/>'


def grid(d, pid, w, h, step=48, op=.035, rx=16):
    d.defs.append(f'<pattern id="{pid}" width="{step}" height="{step}" patternUnits="userSpaceOnUse">'
                  f'<path d="M{step} 0V{step}M0 {step}H{step}" fill="none" stroke="#FFFFFF" stroke-opacity="{op}"/></pattern>')
    return f'<rect width="{w}" height="{h}" rx="{rx}" fill="url(#{pid})"/>'


def scanlines(d, w, h, rx=16, op=.22):
    d.defs.append('<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">'
                  f'<rect y="3" width="4" height="1" fill="#000" fill-opacity="{op}"/></pattern>')
    d.defs.append('<linearGradient id="sweepg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0"/>'
                  '<stop offset=".5" stop-color="#FFFFFF" stop-opacity=".045"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>')
    d.css.append(f".sweep{{animation:sweep 7s linear infinite}}@keyframes sweep{{from{{transform:translateY(-160px)}}to{{transform:translateY({h + 40}px)}}}}")
    return (f'<rect width="{w}" height="{h}" rx="{rx}" fill="url(#scan)"/>'
            f'<rect class="sweep" width="{w}" height="140" fill="url(#sweepg)"/>')


def vignette(d, w, h, rx=16):
    d.defs.append('<radialGradient id="vig" cx=".5" cy=".5" r=".75"><stop offset="0" stop-color="#000" stop-opacity="0"/>'
                  '<stop offset=".7" stop-color="#000" stop-opacity=".2"/><stop offset="1" stop-color="#000" stop-opacity=".7"/></radialGradient>')
    return f'<rect width="{w}" height="{h}" rx="{rx}" fill="url(#vig)"/>'


def panel(d, w, h, rx=14):
    return (f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{rx}" fill="{PANEL}" stroke="{EDGE}"/>')


def vtext(d, fk, s, x, y, size, lh=1.18, fill=BONE, t0=None, step=.09, ls_extra=0):
    """Vertical (tategaki) text: one glyph per line, centred on x."""
    out = []
    for i, ch in enumerate(s):
        ga = (lambda j, cl, gx, i=i: f'class="fl" style="animation-delay:{num(t0 + i * step, 3)}s"') if t0 is not None else None
        out.append(d.text(fk, ch, x, y + i * size * lh, size, anchor="middle", fill=fill, glyph_attrs=ga)[0])
    return "".join(out)


# =============================================================================== HEADER
def header():
    Wd, H = 1200, 540
    d = Doc(Wd, H, "Carlos Franco — Software Engineer · AI Product Builder",
            "Carlos Franco, カルロス・フランコ. Software engineer and AI product builder in São Paulo. "
            "A vermilion sun drawn as a HUD ring holds the vertical Japanese line 未来を設計する (design the future). Status: online, open to work.")
    d.css.append(BASE_CSS)
    cx, cy, R = 912, 258, 150
    d.css.append(f"""
.ring{{stroke-dasharray:1000;animation:ring 2.2s cubic-bezier(.6,0,.2,1) .2s both}}
@keyframes ring{{from{{stroke-dashoffset:1000}}to{{stroke-dashoffset:0}}}}
.rot{{animation:rot 26s linear infinite;transform-origin:{cx}px {cy}px}}
.rotb{{animation:rot 48s linear infinite reverse;transform-origin:{cx}px {cy}px}}
@keyframes rot{{to{{transform:rotate(360deg)}}}}
.car{{animation:car 1.4s cubic-bezier(.2,.8,.2,1) both,gr 9s steps(1) 3s infinite}}
.cac{{animation:cac 1.4s cubic-bezier(.2,.8,.2,1) both,gc 9s steps(1) 3s infinite}}
@keyframes car{{from{{transform:translateX(-14px);opacity:0}}to{{transform:translateX(-1.6px);opacity:.75}}}}
@keyframes cac{{from{{transform:translateX(14px);opacity:0}}to{{transform:translateX(1.6px);opacity:.75}}}}
@keyframes gr{{0%,92%,96%,100%{{transform:translateX(-1.6px)}}93%{{transform:translateX(-7px)}}94.5%{{transform:translateX(3px)}}}}
@keyframes gc{{0%,92%,96%,100%{{transform:translateX(1.6px)}}93%{{transform:translateX(7px)}}94.5%{{transform:translateX(-3px)}}}}
.slice{{animation:slice 9s steps(1) 3s infinite;opacity:0}}
@keyframes slice{{0%,92.6%,94%,100%{{opacity:0;transform:none}}92.7%{{opacity:1;transform:translateX(12px)}}93.3%{{opacity:1;transform:translateX(-6px)}}}}
.seal{{animation:seal .5s cubic-bezier(.3,1.5,.5,1) 2.5s both;transform-box:fill-box;transform-origin:center}}
@keyframes seal{{from{{opacity:0;transform:scale(1.35)}}to{{opacity:1;transform:none}}}}
""")
    d.add(f'<rect width="{Wd}" height="{H}" rx="16" fill="{INK}"/>')
    d.add(grid(d, "g48", Wd, H))
    d.defs.append(f'<radialGradient id="sun" cx="{cx}" cy="{cy}" r="300" gradientUnits="userSpaceOnUse">'
                  f'<stop offset="0" stop-color="{RED}" stop-opacity=".20"/><stop offset=".45" stop-color="{RED}" stop-opacity=".07"/>'
                  f'<stop offset="1" stop-color="{RED}" stop-opacity="0"/></radialGradient>')
    d.add(f'<rect width="{Wd}" height="{H}" rx="16" fill="url(#sun)"/>')

    # ---- HUD sun ------------------------------------------------------------
    ticks = []
    for k in range(120):
        a = math.radians(k * 3)
        r0, r1 = (160, 172) if k % 10 == 0 else (163, 168)
        ticks.append(f"M{num(cx + r0 * math.cos(a))} {num(cy + r0 * math.sin(a))}L{num(cx + r1 * math.cos(a))} {num(cy + r1 * math.sin(a))}")
    d.add(f'<path class="fi" style="animation-delay:.9s" d="{" ".join(ticks)}" stroke="{GREY}" stroke-opacity=".45" stroke-width="1"/>')
    d.add(f'<g class="fi" style="animation-delay:.6s" stroke="{BONE}" stroke-opacity=".10">'
          f'<path d="M{cx - 230} {cy}H{cx - 186}M{cx + 186} {cy}H{cx + 230}M{cx} {cy - 230}V{cy - 186}M{cx} {cy + 186}V{cy + 230}"/></g>')
    d.add(f'<circle class="ring" cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{RED}" stroke-width="1.8" pathLength="1000" transform="rotate(-90 {cx} {cy})"/>')
    arc_r = 182
    a0, a1 = math.radians(-20), math.radians(48)
    d.add(f'<g class="rot"><path d="M{num(cx + arc_r * math.cos(a0))} {num(cy + arc_r * math.sin(a0))} A{arc_r} {arc_r} 0 0 1 '
          f'{num(cx + arc_r * math.cos(a1))} {num(cy + arc_r * math.sin(a1))}" fill="none" stroke="{RED}" stroke-width="2.6" stroke-linecap="square"/>'
          f'<circle cx="{num(cx + arc_r * math.cos(a1))}" cy="{num(cy + arc_r * math.sin(a1))}" r="3" fill="{RED}"/></g>')
    d.add(f'<g class="rotb"><circle cx="{cx}" cy="{cy}" r="128" fill="none" stroke="{CYAN}" stroke-opacity=".45" stroke-dasharray="1.5 7"/></g>')
    d.add(f'<g class="fi" style="animation-delay:1.2s">{brackets(cx - 196, cy - 196, 392, 392, L=12, col=BONE, op=.25, sw=1)}</g>')
    # vertical Japanese line + seal
    d.add(vtext(d, "min", "未来を設計する", cx, cy - 116, 29, lh=1.2, t0=1.3, step=.1))
    sx, sy = cx + 118, cy + 92
    d.add(f'<g class="seal"><rect x="{sx}" y="{sy}" width="40" height="40" rx="3" fill="{RED}"/>'
          f'{T(d, "min7", "創", sx + 20, sy + 30, 28, fill=INK, anchor="middle")}</g>')

    # ---- identity block ---------------------------------------------------------
    x0 = 76
    d.add(f'<g class="fi" style="animation-delay:.2s">{square(x0, 55, 7)}'
          f'{T(d, "pm5", "FRANCOSDEV", x0 + 16, 63, 12, ls=3)}{T(d, "pm", "/ PROFILE.SYS", x0 + 16 + W(d, "pm5", "FRANCOSDEV", 12, 3) + 10, 63, 12, fill=GREY, ls=2)}</g>')
    d.add(f'<g class="fi" style="animation-delay:.3s">{T(d, "pm", "23.5505°S   46.6333°W", Wd - 76, 63, 12, fill=GREY, anchor="end", ls=1.5)}</g>')
    d.add(T(d, "jp3", "カルロス・フランコ", x0 + 2, 174, 21, fill=RED, ls=7, ga=stagger(.25, .05)))
    lines = [("CARLOS", 262), ("FRANCO", 362)]
    size = 84
    red_copy, cyan_copy, main = [], [], []
    for word, y in lines:
        red_copy.append(T(d, "mich", word, x0, y, size, fill=RED, ls=8))
        cyan_copy.append(T(d, "mich", word, x0, y, size, fill=CYAN, ls=8))
        main.append(T(d, "mich", word, x0, y, size, fill=BONE, ls=8, ga=stagger(.35 + (0 if word == "CARLOS" else .3), .06)))
    d.add(f'<g class="car">{"".join(red_copy)}</g><g class="cac">{"".join(cyan_copy)}</g><g>{"".join(main)}</g>')
    # glitch slice: a thin band of the name, displaced for a few frames
    d.defs.append(f'<clipPath id="band"><rect x="0" y="322" width="720" height="13"/></clipPath>')
    d.add(f'<g clip-path="url(#band)"><g class="slice">{T(d, "mich", "FRANCO", x0, 362, size, fill=BONE, ls=8)}</g></g>')
    # role line
    d.add(f'<g class="up" style="animation-delay:1.3s">{square(x0 + 1, 407, 9)}'
          f'{T(d, "pm5", "SOFTWARE ENGINEER  /  AI PRODUCT BUILDER", x0 + 22, 416, 15, ls=3.2)}</g>')
    d.add(f'<g class="up" style="animation-delay:1.5s">{T(d, "ps3", "Designing and building AI products and full-stack systems for the real world.", x0, 448, 15.5, fill=GREY)}</g>')

    # ---- status bar -----------------------------------------------------------------
    d.add(f'<path class="fi" style="animation-delay:1.6s" d="M{x0} 478H{Wd - 76}" stroke="{BONE}" stroke-opacity=".14"/>')
    for i in range(0, 41):
        tx = x0 + i * (Wd - 152) / 40
        d.add(f'<path class="fi" style="animation-delay:1.6s" d="M{num(tx)} 478v{6 if i % 5 == 0 else 3}" stroke="{BONE}" stroke-opacity=".22"/>')
    items = [("ONLINE", CYAN, True), ("OPEN TO WORK", RED, False), ("FIAP · ADS · 2027", GREY, False), ("SÃO PAULO, BR", GREY, False), ("PT / DE / EN / ES", GREY, False)]
    xs = [x0, 262, 470, 690, Wd - 76]
    for (label, col, dot), xx in zip(items, xs):
        anchor = "end" if xx == xs[-1] else "start"
        g = ""
        if dot:
            g += f'<circle class="blink" cx="{xx + 4}" cy="{506}" r="3.5" fill="{CYAN}"/>'
            g += T(d, "pm5", label, xx + 16, 510, 11.5, fill=col, ls=2.4)
        else:
            g += T(d, "pm5" if col == RED else "pm", label, xx, 510, 11.5, fill=col, anchor=anchor, ls=2.4)
        d.add(f'<g class="fi" style="animation-delay:1.8s">{g}</g>')

    d.add(brackets(22, 22, Wd - 44, H - 44, L=18, col=BONE, op=.3))
    d.add(scanlines(d, Wd, H))
    d.add(vignette(d, Wd, H))
    return save(d, "header.svg")


# =============================================================================== DOSSIER
def dossier():
    Wd, H = 1000, 404
    d = Doc(Wd, H, "Personnel file — Carlos Franco",
            "Personnel file. Name: Carlos Franco. Role: software engineer and AI product builder. School: FIAP, Systems Analysis "
            "and Development, class of 2027. Base: São Paulo, Brazil, open to relocation. Languages: Portuguese (native), German "
            "(advanced), English (upper-intermediate), Spanish (intermediate). Learning: software architecture, AI engineering, "
            "cloud, cybersecurity. Status: open to internships and junior roles.")
    d.css.append(BASE_CSS)
    d.add(panel(d, Wd, H))
    d.add(grid(d, "gd", Wd, H, step=40, op=.025, rx=14))
    # header strip
    d.add(f'<g class="fi">{square(28, 31, 7)}{T(d, "pm5", "PERSONNEL FILE", 44, 39, 12, ls=3)}'
          f'{T(d, "jp", "人事ファイル", 44 + W(d, "pm5", "PERSONNEL FILE", 12, 3) + 14, 39, 12, fill=GREY, ls=2)}'
          f'{T(d, "pm", "FILE 01 — PUBLIC", Wd - 28, 39, 11, fill=GREY, anchor="end", ls=2)}</g>')
    d.add(f'<path d="M28 58H{Wd - 28}" stroke="{BONE}" stroke-opacity=".12"/>')
    # emblem
    ex, ey, es = 28, 84, 200
    d.css.append(f".sr{{animation:rot 30s linear infinite;transform-origin:{ex + es / 2}px {ey + es / 2}px}}@keyframes rot{{to{{transform:rotate(360deg)}}}}"
                 ".ring{stroke-dasharray:1000;animation:ring 1.8s cubic-bezier(.6,0,.2,1) .3s both}@keyframes ring{from{stroke-dashoffset:1000}to{stroke-dashoffset:0}}")
    ecx, ecy = ex + es / 2, ey + es / 2
    d.add(f'<rect x="{ex + .5}" y="{ey + .5}" width="{es}" height="{es}" fill="#0A0A0D" stroke="{EDGE2}"/>')
    d.add(grid(d, "ge", es, es, step=20, op=.04, rx=0).replace("<rect ", f'<rect x="{ex + .5}" y="{ey + .5}" ', 1))
    d.add(f'<circle class="ring" cx="{ecx}" cy="{ecy}" r="70" fill="none" stroke="{RED}" stroke-width="1.4" pathLength="1000" transform="rotate(-90 {ecx} {ecy})"/>')
    d.add(f'<g class="sr"><circle cx="{ecx}" cy="{ecy}" r="84" fill="none" stroke="{BONE}" stroke-opacity=".25" stroke-dasharray="2 9"/></g>')
    d.add(f'<g class="fi" style="animation-delay:.6s">{T(d, "mich", "CF", ecx + 2, ecy + 17, 48, anchor="middle", ls=4)}</g>')
    d.add(brackets(ex - 6, ey - 6, es + 13, es + 13, L=10, col=RED, op=.9, sw=1.4))
    d.add(f'<g class="fi" style="animation-delay:.8s">{T(d, "pm", "ID // FRANCOSDEV", ecx, ey + es + 30, 10.5, fill=GREY, anchor="middle", ls=2.2)}</g>')
    # rows
    rows = [
        ("氏名", "NAME", [("Carlos Franco", "ps5", BONE, 16), ("   カルロス・フランコ", "jp3", GREY, 13)]),
        ("職種", "ROLE", [("Software Engineer  ·  AI Product Builder", "ps", BONE, 15.5)]),
        ("所属", "SCHOOL", [("FIAP — Systems Analysis & Development  ·  class of 2027", "ps", BONE, 15.5)]),
        ("拠点", "BASE", [("São Paulo, Brazil — open to relocation", "ps", BONE, 15.5)]),
        ("言語", "LANGUAGES", [("Portuguese ", "ps", BONE, 15.5), ("native", "ps", GREY, 15.5), ("  ·  German ", "ps", BONE, 15.5), ("advanced", "ps", GREY, 15.5),
                                ("  ·  English  ·  Spanish", "ps", BONE, 15.5)]),
        ("学習中", "LEARNING", [("Software architecture  ·  AI engineering  ·  Cloud  ·  Cybersecurity", "ps", BONE, 15.5)]),
        ("状態", "STATUS", [("Open to internships & junior roles", "ps5", CYAN, 15.5)]),
    ]
    lx, vx = 268, 470
    y = 104
    for i, (jp, en, parts) in enumerate(rows):
        g = [T(d, "jp5", jp, lx, y, 14, fill=BONE), T(d, "pm", en, lx + 58, y, 10.5, fill=GREY, ls=2.2)]
        xx = vx
        if en == "STATUS":
            g.append(f'<circle class="blink" cx="{vx + 5}" cy="{y - 5}" r="4" fill="{CYAN}"/>')
            xx += 18
        for text, fk, col, sz in parts:
            g.append(T(d, fk, text, xx, y, sz, fill=col))
            xx += W(d, fk, text, sz)
        if xx > Wd - 28:
            print("    ! row overflows:", en, round(xx))
        d.add(f'<g class="up" style="animation-delay:{num(.35 + i * .11)}s">' + "".join(g) + "</g>")
        if i < len(rows) - 1:
            d.add(f'<path d="M{lx} {y + 17}H{Wd - 28}" stroke="{BONE}" stroke-opacity=".07"/>')
        y += 42
    d.add(scanlines(d, Wd, H, rx=14, op=.16))
    return save(d, "dossier.svg")


# =============================================================================== PROJECT CARDS
def chip(d, x, y, text, col=BONE, fk="pm5", size=10.5, ls=1.6, op=.85):
    w = W(d, fk, text, size, ls) + 20
    return (f'<rect x="{num(x)}" y="{num(y - 15)}" width="{num(w)}" height="22" rx="3" fill="none" stroke="{col}" stroke-opacity=".32"/>'
            + T(d, fk, text, x + 10, y, size, fill=col, ls=ls, attrs=f'opacity="{op}"')), w


def status_chip(d, x_right, y, text, col):
    tw = W(d, "pm5", text, 10.5, 2)
    w = tw + 34
    x = x_right - w
    return (f'<rect x="{num(x)}" y="{num(y - 15)}" width="{num(w)}" height="22" rx="3" fill="{col}" fill-opacity=".07" stroke="{col}" stroke-opacity=".5"/>'
            f'<circle class="blink" cx="{num(x + 13)}" cy="{num(y - 4)}" r="3.4" fill="{col}"/>'
            + T(d, "pm5", text, x + 24, y, 10.5, fill=col, ls=2))


def iso(cx, cy, u, i, j, k):
    c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
    return cx + (i - j) * u * c, cy + (i + j) * u * s - k * u


def illo_ops(d, x, y, s):
    """Inventory as isometric blocks, counted one by one."""
    heights = [[1, 2, 1, 3], [2, 1, 3, 1], [1, 3, 2, 2], [2, 1, 1, 2]]
    cx, cy, u = x + s / 2, y + 98, 23
    out = []
    order = sorted(((i, j) for i in range(4) for j in range(4)), key=lambda p: p[0] + p[1])
    n = len(order)
    cyc = 6.4
    for idx, (i, j) in enumerate(order):
        h = heights[i][j] * .9
        P = lambda a, b, k: iso(cx, cy, u, a, b, k)
        top = [P(i, j, h), P(i + 1, j, h), P(i + 1, j + 1, h), P(i, j + 1, h)]
        left = [P(i, j + 1, 0), P(i + 1, j + 1, 0), P(i + 1, j + 1, h), P(i, j + 1, h)]
        right = [P(i + 1, j, 0), P(i + 1, j + 1, 0), P(i + 1, j + 1, h), P(i + 1, j, h)]
        pts = lambda ps: " ".join(f"{num(a)},{num(b)}" for a, b in ps)
        out.append(f'<polygon points="{pts(left)}" fill="#0E0E12" stroke="{BONE}" stroke-opacity=".35" stroke-width=".9"/>'
                   f'<polygon points="{pts(right)}" fill="#131318" stroke="{BONE}" stroke-opacity=".35" stroke-width=".9"/>'
                   f'<polygon points="{pts(top)}" fill="#1A1A20" stroke="{BONE}" stroke-opacity=".55" stroke-width=".9"/>')
        p = idx / n * 70
        kf = f"cnt{idx}"
        d.css.append(f"@keyframes {kf}{{0%,{num(p, 2)}%{{opacity:0}}{num(p + 1.5, 2)}%{{opacity:1}}{num(p + 9, 2)}%,100%{{opacity:0}}}}.{kf}{{animation:{kf} {cyc}s linear 1s infinite;opacity:0}}")
        out.append(f'<polygon class="{kf}" points="{pts(top)}" fill="{RED}" fill-opacity=".22" stroke="{RED}" stroke-width="1.4"/>')
    # readout
    d.css.append(f".tick{{animation:tick {cyc}s steps(1) 1s infinite}}@keyframes tick{{0%,72%{{opacity:.35}}73%,100%{{opacity:1}}}}")
    out.append(f'<g class="tick">{square(x + 22, y + s - 33, 6, fill=CYAN)}{T(d, "pm5", "SYNCED", x + 34, y + s - 26, 10.5, fill=CYAN, ls=2)}</g>')
    return "".join(out)


def illo_story(d, x, y, s):
    """A constellation that draws itself: every story is a new one."""
    rnd = random.Random(21)
    out = []
    for _ in range(46):
        sx, sy, r = x + rnd.uniform(8, s - 8), y + rnd.uniform(8, s - 8), rnd.uniform(.4, 1.1)
        dur = rnd.uniform(2.5, 5.5)
        out.append(f'<circle class="tw" cx="{num(sx)}" cy="{num(sy)}" r="{num(r)}" fill="{BONE}" style="animation-duration:{num(dur)}s;animation-delay:{num(-rnd.uniform(0, dur))}s"/>')
    d.css.append(".tw{animation:tw 4s ease-in-out infinite}@keyframes tw{0%,100%{opacity:.2}50%{opacity:.9}}"
                 ".con{stroke-dasharray:1000;animation:con 3.2s cubic-bezier(.5,0,.2,1) .4s both}@keyframes con{from{stroke-dashoffset:1000}to{stroke-dashoffset:0}}")
    # crescent moon
    mx, my = x + s - 64, y + 58
    d.defs.append(f'<mask id="moon"><rect x="{x}" y="{y}" width="{s}" height="{s}" fill="#fff"/><circle cx="{mx + 11}" cy="{my - 7}" r="21" fill="#000"/></mask>')
    out.append(f'<circle cx="{mx}" cy="{my}" r="24" fill="none" stroke="{BONE}" stroke-width="1.3" mask="url(#moon)"/>')
    stars = [(0.18, .78), (.30, .60), (.42, .67), (.50, .45), (.63, .52), (.70, .33), (.58, .74), (.80, .66)]
    pts = [(x + a * s, y + b * s) for a, b in stars]
    path = "M" + " L".join(f"{num(a)} {num(b)}" for a, b in pts[:6]) + f" M{num(pts[2][0])} {num(pts[2][1])} L{num(pts[6][0])} {num(pts[6][1])} L{num(pts[7][0])} {num(pts[7][1])}"
    out.append(f'<path class="con" d="{path}" fill="none" stroke="{BONE}" stroke-opacity=".45" stroke-width="1" pathLength="1000"/>')
    for k, (a, b) in enumerate(pts):
        hero = k == 3
        out.append(f'<g class="fl" style="animation-delay:{num(.5 + k * .28)}s"><circle cx="{num(a)}" cy="{num(b)}" r="{3.6 if hero else 2.3}" fill="{RED if hero else BONE}"/>'
                   + (f'<circle cx="{num(a)}" cy="{num(b)}" r="9" fill="none" stroke="{RED}" stroke-opacity=".6"/>' if hero else "") + "</g>")
    out.append(T(d, "pm", "READ TOGETHER", x + 22, y + s - 26, 10.5, fill=GREY, ls=2))
    return "".join(out)


def illo_orbit(d, x, y, s):
    """Wireframe planet, an orbit, and a pulse: passive signals under watch."""
    cx, cy, R = x + s / 2, y + 108, 62
    out = [f'<circle cx="{num(cx)}" cy="{num(cy)}" r="{R}" fill="#0A0D10" stroke="{CYAN}" stroke-opacity=".75" stroke-width="1.1"/>']
    for f in (.35, .7):
        out.append(f'<ellipse cx="{num(cx)}" cy="{num(cy - R * f * .62)}" rx="{num(R * math.sqrt(1 - (f * .62) ** 2))}" ry="{num(R * .16)}" fill="none" stroke="{CYAN}" stroke-opacity=".3"/>')
        out.append(f'<ellipse cx="{num(cx)}" cy="{num(cy + R * f * .62)}" rx="{num(R * math.sqrt(1 - (f * .62) ** 2))}" ry="{num(R * .16)}" fill="none" stroke="{CYAN}" stroke-opacity=".3"/>')
    out.append(f'<ellipse cx="{num(cx)}" cy="{num(cy)}" rx="{R}" ry="{num(R * .2)}" fill="none" stroke="{CYAN}" stroke-opacity=".38"/>')
    for k in range(4):
        vals = ";".join(num(R * abs(math.cos(math.radians(k * 45 + t * 15)))) for t in range(0, 25))
        out.append(f'<ellipse cx="{num(cx)}" cy="{num(cy)}" rx="{num(R * abs(math.cos(math.radians(k * 45))))}" ry="{R}" fill="none" stroke="{CYAN}" stroke-opacity=".32">'
                   f'<animate attributeName="rx" values="{vals}" dur="12s" repeatCount="indefinite"/></ellipse>')
    orbit = f"M{num(cx - 104)} {num(cy + 10)} A104 30 -14 1 1 {num(cx + 104)} {num(cy - 10)} A104 30 -14 1 1 {num(cx - 104)} {num(cy + 10)}"
    out.append(f'<path d="{orbit}" fill="none" stroke="{BONE}" stroke-opacity=".22" stroke-dasharray="3 5"/>'
               f'<circle r="3.6" fill="{RED}"><animateMotion dur="9s" repeatCount="indefinite" path="{orbit}"/></circle>')
    base = y + s - 58
    pts = [(0, 0), (70, 0), (80, -5), (88, 5), (96, 0), (108, 0), (116, -26), (126, 22), (134, -8), (142, 0), (170, 0), (178, -6), (186, 0), (s - 40, 0)]
    dp = "M" + " L".join(f"{num(x + 20 + a)} {num(base + b)}" for a, b in pts)
    d.css.append(".ecg{stroke-dasharray:70 600;animation:ecg 3s linear infinite}@keyframes ecg{from{stroke-dashoffset:670}to{stroke-dashoffset:0}}")
    out.append(f'<path d="{dp}" fill="none" stroke="{CYAN}" stroke-opacity=".18" stroke-width="1.2"/>'
               f'<path class="ecg" d="{dp}" fill="none" stroke="{CYAN}" stroke-width="1.8" stroke-linejoin="round" pathLength="670"/>')
    out.append(T(d, "pm", "CREW 06 · ICE MONITOR", x + 22, y + s - 20, 10.5, fill=GREY, ls=1.5))
    return "".join(out)


def card(file, m, illo):
    Wd, H = 1000, 300
    d = Doc(Wd, H, f'{m["title"]} — {m["subtitle"]}', m["desc"])
    d.css.append(BASE_CSS)
    d.add(panel(d, Wd, H))
    px, py, ps = 24, 24, 252
    d.defs.append(f'<clipPath id="ill"><rect x="{px}" y="{py}" width="{ps}" height="{ps}" rx="8"/></clipPath>')
    d.add(f'<rect x="{px}" y="{py}" width="{ps}" height="{ps}" rx="8" fill="#09090C"/>')
    d.add(f'<g clip-path="url(#ill)">' + grid(d, "gi", ps, ps, step=21, op=.035, rx=0).replace("<rect ", f'<rect x="{px}" y="{py}" ', 1)
          + illo(d, px, py, ps) + "</g>")
    d.add(f'<rect x="{px + .5}" y="{py + .5}" width="{ps - 1}" height="{ps - 1}" rx="8" fill="none" stroke="{EDGE2}"/>')
    x = 308
    lab = f'PROJECT {m["n"]}'
    d.add(f'<g class="fi">{T(d, "pm5", lab, x, 57, 11, fill=RED, ls=3.4)}'
          f'{T(d, "pm", "//", x + W(d, "pm5", lab, 11, 3.4) + 12, 57, 11, fill=DIM, ls=2)}'
          f'{T(d, "jp", m["jp"], x + W(d, "pm5", lab, 11, 3.4) + 36, 57, 12.5, fill=GREY, ls=2)}</g>')
    d.add(f'<g class="fi">{status_chip(d, Wd - 34, 56, m["status"], m["status_col"])}</g>')
    d.add(f'<g class="up" style="animation-delay:.1s">{T(d, "mich", m["title"], x - 2, 114, 40, ls=2.5)}</g>')
    d.add(f'<g class="up" style="animation-delay:.2s">{T(d, "ps", m["subtitle"], x, 147, 16.5, attrs=chr(111) + "pacity=" + chr(34) + ".85" + chr(34))}</g>')
    d.add(f'<path d="M{x} 170H{Wd - 34}" stroke="{BONE}" stroke-opacity=".1"/>')
    yy = 199
    for i, line in enumerate(m["points"]):
        d.add(f'<g class="up" style="animation-delay:{num(.3 + i * .1)}s">{T(d, "pm5", "›", x, yy, 13, fill=RED)}{T(d, "pm", line, x + 16, yy, 12.5, fill=GREY, ls=.3)}</g>')
        yy += 23
    cxp = x
    g = []
    for t in m["stack"]:
        c, w = chip(d, cxp, 262, t)
        g.append(c)
        cxp += w + 8
    d.add(f'<g class="fi" style="animation-delay:.5s">{"".join(g)}</g>')
    d.add(brackets(10, 10, Wd - 20, H - 20, L=14, col=RED, op=.85, sw=1.3))
    return save(d, file)


def card_barops():
    return card("card-barops.svg", {
        "n": "01", "jp": "在庫管理", "title": "BarOps", "subtitle": "Inventory & operations platform for bars and restaurants",
        "status": "DEPLOYED", "status_col": CYAN,
        "desc": "BarOps: inventory and operations platform, in production. React 19, Vite, Google Apps Script, Google Sheets.",
        "points": ["mobile counts · sheets sync · excel / pdf / csv exports · roles",
                   "in production · multi-location · ledger-based stock"],
        "stack": ["REACT 19", "VITE", "APPS SCRIPT", "GOOGLE SHEETS", "JSPDF"],
    }, illo_ops)


def card_mimo():
    return card("card-mimo.svg", {
        "n": "02", "jp": "物語", "title": "Mimo", "subtitle": "AI-generated bedtime stories where the child is the hero",
        "status": "IN DEVELOPMENT", "status_col": RED,
        "desc": "Mimo: personalized children's stories generated with an LLM, built with React Native and Expo. In development.",
        "points": ["personalized stories · 9 retold classics · memory chest",
                   "anti-engagement by design: no streaks, no push"],
        "stack": ["REACT NATIVE", "EXPO", "LLAMA 3.3 70B", "GROQ", "ASYNCSTORAGE"],
    }, illo_story)


def card_aura():
    return card("card-aura.svg", {
        "n": "03", "jp": "感情監視", "title": "AURA", "subtitle": "Emotional monitoring OS for space crews",
        "status": "LIVE DEMO", "status_col": CYAN,
        "desc": "AURA: emotional monitoring system for space crews. Python, JavaScript, IBM Watson, Oracle SQL. Live demo. Team project.",
        "points": ["passive signals → ICE index (0–100) → 4-layer response",
                   "voice + text crew assistant · 69 automated tests · team of 3"],
        "stack": ["PYTHON", "VANILLA JS", "IBM WATSON", "NODE-RED", "ORACLE SQL"],
    }, illo_orbit)


# =============================================================================== STACK
def lum(hexcol):
    h = hexcol.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return .2126 * r + .7152 * g + .0722 * b


def glyph_icon(kind, x, y, size, col):
    s = size / 24
    if kind == "db":
        return (f'<g transform="translate({num(x)} {num(y)}) scale({num(s, 4)})" fill="none" stroke="{col}" stroke-width="1.8">'
                f'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></g>')
    if kind == "cup":
        return (f'<g transform="translate({num(x)} {num(y)}) scale({num(s, 4)})" fill="none" stroke="{col}" stroke-width="1.7" stroke-linecap="round">'
                f'<path d="M4 11h13v4a6 6 0 0 1-6 6h-1a6 6 0 0 1-6-6z"/><path d="M17 12.5h1.5a2.5 2.5 0 0 1 0 5H16.5"/>'
                f'<path d="M8 2.5c-1.2 1.4 1.2 2.6 0 4.2M11.5 2.5c-1.2 1.4 1.2 2.6 0 4.2M15 2.5c-1.2 1.4 1.2 2.6 0 4.2"/></g>')
    if kind == "ai":
        return (f'<g transform="translate({num(x)} {num(y)}) scale({num(s, 4)})" fill="{col}">'
                f'<path d="M10 2l1.9 5.6L17.5 9.5l-5.6 1.9L10 17l-1.9-5.6L2.5 9.5l5.6-1.9z"/>'
                f'<path d="M18.5 13l.9 2.6 2.6.9-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9z"/></g>')
    ic = icon(kind)
    return f'<path transform="translate({num(x)} {num(y)}) scale({num(s, 4)})" d="{ic["path"]}" fill="{col}"/>'


def stack():
    rows = [
        ("言語", "LANGUAGES", [("JavaScript", "javascript"), ("TypeScript", "typescript"), ("Python", "python"), ("Java", "cup"), ("SQL", "db")]),
        ("フロントエンド", "FRONT-END", [("React", "react"), ("React Native", "expo"), ("Vite", "vite"), ("Tailwind", "tailwindcss"), ("HTML", "html5"), ("CSS", "css")]),
        ("バックエンド", "BACK-END · CLOUD · AI", [("Node.js", "nodedotjs"), ("Apps Script", "googleappsscript"), ("Google Cloud", "googlecloud"), ("Netlify", "netlify"), ("LLMs · Agents", "ai")]),
        ("ツール", "TOOLS", [("Git", "git"), ("GitHub", "github"), ("Docker", "docker"), ("Figma", "figma")]),
    ]
    Wd, rh, top = 1000, 98, 26
    H = top + rh * len(rows) + 16
    d = Doc(Wd, H, "Tech stack — Carlos Franco",
            "Languages: JavaScript, TypeScript, Python, Java, SQL. Front-end: React, React Native, Vite, Tailwind CSS, HTML, CSS. "
            "Back-end, cloud and AI: Node.js, Google Apps Script, Google Cloud, Netlify, LLMs and AI agents. Tools: Git, GitHub, Docker, Figma.")
    d.css.append(BASE_CSS)
    d.css.append(".scanx{animation:scanx 6s cubic-bezier(.5,0,.5,1) infinite}@keyframes scanx{0%{transform:translateX(0);opacity:0}8%{opacity:1}60%{transform:translateX(740px);opacity:1}64%,100%{transform:translateX(740px);opacity:0}}")
    d.add(panel(d, Wd, H))
    d.add(grid(d, "gs", Wd, H, step=40, op=.022, rx=14))
    cell, gap, x0 = 92, 16, 262
    for ri, (jp, en, items) in enumerate(rows):
        y = top + ri * rh
        d.add(f'<g class="fi" style="animation-delay:{num(ri * .15)}s">{T(d, "jp5", jp, 32, y + 40, 15)}{T(d, "pm", en, 32, y + 60, 10, fill=GREY, ls=2)}'
              f'{square(32, y + 72, 5, fill=RED)}</g>')
        for ci, (label, ic) in enumerate(items):
            cx = x0 + ci * (cell + gap)
            delay = .2 + ri * .15 + ci * .07
            g = [f'<rect x="{cx + .5}" y="{y + 2.5}" width="{cell}" height="{cell - 6}" rx="4" fill="#0A0A0D" stroke="{EDGE2}"/>',
                 glyph_icon(ic, cx + cell / 2 - 14, y + 17, 28, BONE),
                 T(d, "pm", label.upper(), cx + cell / 2, y + 76, 9 if len(label) > 10 else 9.6, fill=GREY, anchor="middle", ls=.7)]
            d.add(f'<g class="fl" style="animation-delay:{num(delay)}s">' + "".join(g) + "</g>")
        if ri < len(rows) - 1:
            d.add(f'<path d="M32 {y + rh + 2}H{Wd - 32}" stroke="{BONE}" stroke-opacity=".06"/>')
    d.add(f'<g class="scanx"><rect x="{x0 - 20}" y="{top + 6}" width="2" height="{rh * len(rows) - 10}" fill="{RED}" fill-opacity=".55"/></g>')
    return save(d, "stack.svg")


# =============================================================================== PROCESS
def process():
    Wd, H = 1000, 150
    steps = ["PROBLEM", "RESEARCH", "PROTOTYPE", "BUILD", "TEST", "ITERATE", "SHIP"]
    kanji = "一二三四五六七"
    d = Doc(Wd, H, "How I build", "How I build: problem, research, prototype, build, test, iterate, ship.")
    d.css.append(BASE_CSS)
    d.add(panel(d, Wd, H))
    x0, x1, ly = 92, Wd - 92, 82
    cyc, travel = 8.0, 5.6
    d.css.append(f".pulse{{animation:pulse {cyc}s cubic-bezier(.45,0,.55,1) infinite}}"
                 f"@keyframes pulse{{0%{{transform:translateX(0);opacity:0}}4%{{opacity:1}}{num(travel / cyc * 100, 2)}%{{transform:translateX({x1 - x0}px);opacity:1}}"
                 f"{num(travel / cyc * 100 + 5, 2)}%,100%{{transform:translateX({x1 - x0}px);opacity:0}}}}")
    d.add(f'<path d="M{x0} {ly}H{x1}" stroke="{BONE}" stroke-opacity=".16"/>')
    d.add(f'<g class="pulse"><rect x="{x0 - 16}" y="{ly - 1}" width="32" height="2" fill="{RED}"/><circle cx="{x0}" cy="{ly}" r="3" fill="{RED}"/></g>')
    n = len(steps)
    for i, st in enumerate(steps):
        x = x0 + (x1 - x0) * i / (n - 1)
        frac = i / (n - 1)
        t_hit = travel * (0.5 - math.sin(math.asin(1 - 2 * frac) / 3)) if 0 < frac < 1 else travel * frac
        p = t_hit / cyc * 100
        k = f"hit{i}"
        d.css.append(f"@keyframes {k}{{0%,{num(max(0, p - .5), 2)}%{{opacity:0}}{num(p, 2)}%{{opacity:1}}{num(min(99, p + 16), 2)}%,100%{{opacity:0}}}}.{k}{{animation:{k} {cyc}s linear infinite}}")
        d.add(f'<g class="fi" style="animation-delay:{num(i * .08)}s">{T(d, "min", kanji[i], x, 54, 21, fill=GREY, anchor="middle")}'
              f'<rect x="{num(x - 5)}" y="{ly - 5}" width="10" height="10" transform="rotate(45 {num(x)} {ly})" fill="{PANEL}" stroke="{BONE}" stroke-opacity=".6"/>'
              f'{T(d, "pm5", st, x, 116, 11.5, anchor="middle", ls=2.6)}</g>')
        d.add(f'<g class="{k}"><rect x="{num(x - 5)}" y="{ly - 5}" width="10" height="10" transform="rotate(45 {num(x)} {ly})" fill="{RED}"/></g>')
    return save(d, "process.svg")


# =============================================================================== FOOTER / TITLES / BUTTONS
def footer():
    Wd, H = 1200, 190
    d = Doc(Wd, H, "End of transmission", "End of transmission — 通信終了.")
    d.css.append(BASE_CSS)
    cx = Wd / 2
    d.css.append(f".rot{{animation:rot 12s linear infinite;transform-origin:{cx}px 62px}}@keyframes rot{{to{{transform:rotate(360deg)}}}}")
    d.add(f'<rect width="{Wd}" height="{H}" rx="16" fill="{INK}"/>')
    d.add(grid(d, "gf", Wd, H))
    d.defs.append(f'<radialGradient id="fsun" cx="{cx}" cy="62" r="120" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="{RED}" stop-opacity=".22"/><stop offset="1" stop-color="{RED}" stop-opacity="0"/></radialGradient>')
    d.add(f'<rect width="{Wd}" height="{H}" rx="16" fill="url(#fsun)"/>')
    d.add(f'<circle cx="{cx}" cy="62" r="11" fill="{RED}"/><g class="rot"><circle cx="{cx}" cy="62" r="24" fill="none" stroke="{RED}" stroke-opacity=".7" stroke-dasharray="30 8 4 8"/></g>')
    label = "END OF TRANSMISSION"
    t, tw, _ = d.text("pm5", label, cx, 124, 13, anchor="middle", ls=6, fill=BONE)
    d.add(t, f'<rect class="cur" x="{num(cx + tw / 2 + 8)}" y="112" width="9" height="14" fill="{RED}"/>')
    d.add(T(d, "jp", "通信終了", cx, 152, 13, fill=GREY, anchor="middle", ls=6))
    d.add(T(d, "pm", "FRANCOSDEV", 76, 152, 10.5, fill=DIM, ls=2.4), T(d, "pm", "23.5505°S 46.6333°W", Wd - 76, 152, 10.5, fill=DIM, anchor="end", ls=1.6))
    d.add(brackets(22, 22, Wd - 44, H - 44, L=16, col=BONE, op=.28))
    d.add(scanlines(d, Wd, H))
    return save(d, "footer.svg")


TITLES = [("profile", "01", "PROFILE", "プロフィール"), ("projects", "02", "PROJECTS", "プロジェクト"),
          ("stack", "03", "STACK", "技術"), ("process", "04", "PROCESS", "工程"),
          ("telemetry", "05", "TELEMETRY", "統計"), ("contact", "06", "CONTACT", "連絡")]


def titles():
    for slug, no, title, jp in TITLES:
        for theme in ("dark", "light"):
            Wd, H = 1000, 64
            d = Doc(Wd, H, f"{no} {title} {jp}", f"Section {no}: {title.title()}.")
            d.css.append(BASE_CSS)
            main = BONE if theme == "dark" else "#141417"
            sub = GREY if theme == "dark" else "#6B6B73"
            hair = "#2C2C33" if theme == "dark" else "#D9D9DF"
            y = 40
            n = T(d, "pm5", no, 2, y, 13, fill=RED, ls=1)
            tx = 86
            t, tw, _ = d.text("mich", title, tx, y + 1, 21, ls=6, fill=main)
            j, jw, _ = d.text("jp", jp, Wd - 2, y, 13.5, anchor="end", ls=4, fill=sub)
            d.add(f'<g class="fi">{n}<path d="M34 {y - 5}H70" stroke="{RED}" stroke-opacity=".8"/>{t}'
                  f'<path d="M{num(tx + tw + 22)} {y - 5}H{num(Wd - 2 - jw - 22)}" stroke="{hair}"/>{j}</g>')
            path = os.path.join(OUT, f"title-{slug}-{theme}.svg")
            d.save(path)
            ET.parse(path)
    print(f"  title-*.svg                    {len(TITLES) * 2} files")


def button(file, label, kind):
    Wd, H = 236, 54
    d = Doc(Wd, H, label, f"{label} button")
    d.add(f'<rect x=".5" y=".5" width="{Wd - 1}" height="{H - 1}" rx="6" fill="{PANEL}" stroke="{EDGE2}"/>')
    d.add(brackets(4, 4, Wd - 8, H - 8, L=8, col=RED, op=.9, sw=1.2))
    bx, by = 18, (H - 24) / 2
    d.add(f'<rect x="{bx}" y="{by}" width="24" height="24" rx="2" fill="{RED}"/>')
    if kind == "linkedin":
        d.add(T(d, "ps5", "in", bx + 12, by + 17.5, 15, fill=INK, anchor="middle"))
    else:
        d.add(f'<path d="M{bx + 5} {by + 7}h14v10h-14z M{bx + 5} {by + 7}l7 5.5 7-5.5" fill="none" stroke="{INK}" stroke-width="1.6" stroke-linejoin="round"/>')
    d.add(T(d, "pm5", label, bx + 38, H / 2 + 4.5, 13, ls=3.2))
    ax = Wd - 34
    d.add(f'<path d="M{ax} {H / 2 + 6}l10 -10 M{ax + 3} {H / 2 - 4}h7v7" fill="none" stroke="{GREY}" stroke-width="1.5" stroke-linecap="square"/>')
    save(d, file)


ASSETS = {"header": header, "dossier": dossier, "card-barops": card_barops, "card-mimo": card_mimo, "card-aura": card_aura, "stack": stack, "process": process, "footer": footer, "titles": titles, "buttons": lambda: (button("btn-linkedin.svg", "LINKEDIN", "linkedin"), button("btn-email.svg", "EMAIL", "email"))}

if __name__ == "__main__":
    for n in (sys.argv[1:] or list(ASSETS)):
        ASSETS[n]()
