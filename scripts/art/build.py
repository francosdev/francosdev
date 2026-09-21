"""
Builds every static SVG of the README ("the menu") into /assets.

    pip install fonttools uharfbuzz brotli
    python scripts/art/build.py              # everything
    python scripts/art/build.py header       # one asset (see ASSETS at the bottom)

All text is shaped with HarfBuzz and converted to vector outlines (fonts are fetched once,
SIL OFL licensed), so the images need nothing external to render — GitHub serves README
images with a strict CSP that blocks web fonts. Change copy here, re-run, commit /assets.
"""
import math
import os
import random
import sys

from svgkit import Doc, P, register_fonts, font, num, esc, icon, icon_svg, gold_gradient, glow_filter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "assets")
os.makedirs(OUT, exist_ok=True)
register_fonts()

GOLD_STOPS = [(0, "#7A5A24"), (0.22, "#C9A25A"), (0.45, "#FFF0C8"), (0.55, "#E6C27A"), (0.78, "#A67C36"), (1, "#6E5020")]


def lin_grad(doc, gid, stops, x1=0, y1=0, x2=0, y2=1, units="objectBoundingBox", extra=""):
    st = "".join(f'<stop offset="{num(o, 3)}" stop-color="{c}"' + (f' stop-opacity="{num(a, 3)}"' if a is not None else "") + "/>"
                 for o, c, *rest in stops for a in [rest[0] if rest else None])
    doc.defs.append(f'<linearGradient id="{gid}" gradientUnits="{units}" x1="{num(x1)}" y1="{num(y1)}" '
                    f'x2="{num(x2)}" y2="{num(y2)}">{st}{extra}</linearGradient>')
    return f"url(#{gid})"


def rad_grad(doc, gid, stops, cx=0.5, cy=0.5, r=0.5, units="objectBoundingBox", fx=None, fy=None):
    st = "".join(f'<stop offset="{num(o, 3)}" stop-color="{c}" stop-opacity="{num(a, 3)}"/>' for o, c, a in stops)
    f = (f' fx="{num(fx)}" fy="{num(fy)}"' if fx is not None else "")
    doc.defs.append(f'<radialGradient id="{gid}" gradientUnits="{units}" cx="{num(cx)}" cy="{num(cy)}" r="{num(r)}"{f}>{st}</radialGradient>')
    return f"url(#{gid})"


def noise_filter(doc, fid, opacity=0.06, freq=0.9, seed=3):
    doc.defs.append(
        f'<filter id="{fid}" x="0" y="0" width="100%" height="100%">'
        f'<feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="2" seed="{seed}" result="n"/>'
        f'<feColorMatrix in="n" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 {opacity} 0"/>'
        f'</filter>')
    return f"url(#{fid})"


def deco_corner(x, y, sx, sy, stroke, sw=1.2):
    """Gatsby-style stepped corner. (x, y) = inner corner point, sx/sy = +1/-1 orientation."""
    def L(o, a, b, w, op):
        return (f'<path d="M{num(x + sx * o)} {num(y + sy * b)} V{num(y + sy * o)} H{num(x + sx * b)}" '
                f'fill="none" stroke="{stroke}" stroke-width="{num(w)}" opacity="{op}"/>')
    parts = [L(0, 0, 46, sw * 1.1, 1), L(6, 0, 30, sw * .8, .75), L(12, 0, 18, sw * .7, .55)]
    cx, cy = x + sx * 22, y + sy * 22
    parts.append(f'<rect x="{num(cx - 2.6)}" y="{num(cy - 2.6)}" width="5.2" height="5.2" '
                 f'transform="rotate(45 {num(cx)} {num(cy)})" fill="{stroke}"/>')
    return "".join(parts)


def deco_frame(doc, w, h, inset=14, gap=8, stroke=None, corners=True, radius=0):
    stroke = stroke or f"url(#{doc.frame_grad})"
    out = [f'<rect x="{inset}" y="{inset}" width="{w - 2 * inset}" height="{h - 2 * inset}" rx="{radius}" fill="none" stroke="{stroke}" stroke-width="1.6"/>',
           f'<rect x="{inset + gap}" y="{inset + gap}" width="{w - 2 * (inset + gap)}" height="{h - 2 * (inset + gap)}" rx="{max(0, radius - gap)}" fill="none" stroke="{stroke}" stroke-width=".7" opacity=".7"/>']
    if corners:
        c = inset + gap + 6
        out.append(deco_corner(c, c, 1, 1, stroke))
        out.append(deco_corner(w - c, c, -1, 1, stroke))
        out.append(deco_corner(c, h - c, 1, -1, stroke))
        out.append(deco_corner(w - c, h - c, -1, -1, stroke))
    return "".join(out)


def deco_rule(cx, y, half, stroke, gap=14, sw=1):
    """ ─────◆───── with dots."""
    return (f'<line x1="{num(cx - half)}" y1="{num(y)}" x2="{num(cx - gap)}" y2="{num(y)}" stroke="{stroke}" stroke-width="{sw}"/>'
            f'<line x1="{num(cx + gap)}" y1="{num(y)}" x2="{num(cx + half)}" y2="{num(y)}" stroke="{stroke}" stroke-width="{sw}"/>'
            f'<rect x="{num(cx - 4)}" y="{num(y - 4)}" width="8" height="8" transform="rotate(45 {num(cx)} {num(y)})" fill="{stroke}"/>'
            f'<circle cx="{num(cx - half - 6)}" cy="{num(y)}" r="1.6" fill="{stroke}"/><circle cx="{num(cx + half + 6)}" cy="{num(y)}" r="1.6" fill="{stroke}"/>')


def base_doc(w, h, title, desc, bg=True, radius=18, frame=True, corners=True, shimmer=True):
    d = Doc(w, h, title, desc)
    d.frame_grad = "fg"
    stops = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in GOLD_STOPS)
    anim = ('<animateTransform attributeName="gradientTransform" type="translate" values="-1.2 0;1.2 0;1.2 0" '
            'keyTimes="0;.55;1" dur="9s" repeatCount="indefinite"/>') if shimmer else ""
    d.defs.append(f'<linearGradient id="fg" x1="0" y1="0" x2="1" y2=".25" spreadMethod="reflect">{stops}{anim}</linearGradient>')
    d.defs.append(f'<linearGradient id="gtext" x1="0" y1="0" x2="0" y2="1">'
                  f'<stop offset="0" stop-color="#FFF1CC"/><stop offset=".45" stop-color="#E6C27A"/><stop offset="1" stop-color="#A9802F"/></linearGradient>')
    if bg:
        d.add(f'<rect width="{w}" height="{h}" rx="{radius}" fill="{P["ink"]}"/>')
    d.frame = frame
    d.corners = corners
    d.radius = radius
    return d


def finish(d, name, frame_inset=12, gap=7):
    import xml.etree.ElementTree as ET
    if d.frame:
        d.add(deco_frame(d, d.w, d.h, inset=frame_inset, gap=gap, corners=d.corners, radius=max(0, d.radius - 8)))
    size = d.save(os.path.join(OUT, name))
    ET.parse(os.path.join(OUT, name))          # raises on any XML error
    print(f"  {name:28s} {size / 1024:7.1f} KB")
    return os.path.join(OUT, name)


# =============================================================================== HEADER
def header():
    W, H = 1200, 470
    d = base_doc(W, H, "Carlos Franco — Software Engineer · AI Product Builder",
                 "A neon bar sign reading Carlos Franco, with a neon martini glass and an 'Open to work' sign, "
                 "above the words Software Engineer and AI Product Builder.")
    # --- background: bricks + warm light + vignette
    d.defs.append('<pattern id="brick" width="72" height="30" patternUnits="userSpaceOnUse">'
                  f'<rect width="72" height="30" fill="#0E0B09"/>'
                  '<rect x="1" y="1" width="70" height="13" rx="1.5" fill="#15110D"/>'
                  '<rect x="-35" y="16" width="70" height="13" rx="1.5" fill="#15110D"/>'
                  '<rect x="37" y="16" width="70" height="13" rx="1.5" fill="#15110D"/></pattern>')
    d.add(f'<rect width="{W}" height="{H}" rx="18" fill="url(#brick)"/>')
    warm = rad_grad(d, "warm", [(0, "#FF9E4A", .20), (.45, "#FF8A3D", .07), (1, "#000", 0)], cx=.5, cy=.42, r=.62)
    d.add(f'<rect width="{W}" height="{H}" rx="18" fill="{warm}"/>')
    vig = rad_grad(d, "vig", [(0, "#000", 0), (.62, "#000", .25), (1, "#000", .88)], cx=.5, cy=.5, r=.75)
    d.add(f'<rect width="{W}" height="{H}" rx="18" fill="{vig}"/>')

    d.css.append("""
.on{animation:on 2.2s linear both}
.on2{animation:on 1.8s linear .7s both}
.on3{animation:on 1.6s linear 1.4s both}
@keyframes on{0%{opacity:0}8%{opacity:.85}11%{opacity:.1}18%{opacity:.9}22%{opacity:.2}30%{opacity:1}46%{opacity:.55}50%{opacity:1}100%{opacity:1}}
.buzz{animation:buzz 7s linear 3s infinite}
@keyframes buzz{0%,61%,63.5%,66%,100%{opacity:1}62%{opacity:.25}64.5%{opacity:.4}65%{opacity:.9}}
.breathe{animation:breathe 4.5s ease-in-out 2.4s infinite}
@keyframes breathe{0%,100%{opacity:.92}50%{opacity:1}}
.blink{animation:blink 5.3s steps(1) 2s infinite}
@keyframes blink{0%,70%,76%,100%{opacity:1}72%{opacity:.15}74%{opacity:1}75%{opacity:.2}}
.tw{animation:tw 9s linear 4s infinite}
.blink2{animation:blink 6.7s steps(1) 3.1s infinite}
@keyframes tw{0%,40%,44%,100%{opacity:1}41%{opacity:.1}42.5%{opacity:.8}43%{opacity:.05}}
.bokeh{animation:float linear infinite both}
@keyframes float{0%{transform:translateY(20px);opacity:0}15%{opacity:var(--o)}85%{opacity:var(--o)}100%{transform:translateY(-120px);opacity:0}}
.rise{animation:rise 1.2s cubic-bezier(.2,.7,.2,1) both}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
""")
    # --- bokeh
    rnd = random.Random(7)
    bok = []
    for i in range(14):
        x = rnd.uniform(60, W - 60)
        y = rnd.uniform(200, H - 40)
        r = rnd.uniform(2, 7)
        o = rnd.uniform(.12, .35)
        dur = rnd.uniform(11, 19)
        delay = -rnd.uniform(0, dur)
        col = rnd.choice(["#FFC37A", "#FFD9A0", "#FF9E5E"])
        bok.append(f'<circle class="bokeh" cx="{num(x)}" cy="{num(y)}" r="{num(r)}" fill="{col}" '
                   f'style="--o:{num(o)};animation-duration:{num(dur)}s;animation-delay:{num(delay)}s"/>')
    d.defs.append('<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2"/></filter>')
    d.add('<g filter="url(#soft)">' + "".join(bok) + "</g>")

    # --- top plate
    lbl, lw, _ = d.text("deco", "SÃO PAULO  ·  BAR & CODE", W / 2, 70, 14, anchor="middle", ls=5, fill="url(#gtext)")
    d.add(f'<g class="rise">{lbl}{deco_rule(W / 2, 64, lw / 2 + 90, "#8C6A2F", gap=lw / 2 + 22, sw=.8)}</g>')

    # --- neon name
    amber = glow_filter(d, "gAmber", "#FF9D3C", radii=(3, 9, 22), strength=.95, core_blur=.35)
    name = "Carlos Franco"
    size = 118
    f = font("neon")
    sc = size / f.upem
    tube, nw, _ = d.text("neon", name, W / 2 - 4, 250, size, anchor="middle", fill="#FFB25E",
                         attrs=f'stroke="#FFB25E" stroke-width="{num(3.2 / sc)}" stroke-linejoin="round"')
    core, _, _ = d.text("neon", name, W / 2 - 4, 250, size, anchor="middle", fill="#FFF6E4")
    d.add(f'<g class="on"><g class="buzz"><g filter="{amber}" class="breathe">{tube}</g>{core}</g></g>')

    # --- neon martini (left)
    cyan = glow_filter(d, "gCyan", P["neon_cyan"], radii=(2.5, 7, 16), strength=.9, core_blur=.3)
    green = glow_filter(d, "gGreen", "#7CFF6B", radii=(2, 6, 12), strength=.9, core_blur=.3)
    gx, gy = 175, 150
    glass = (f'M{gx - 62} {gy} L{gx + 62} {gy} L{gx} {gy + 78} Z '
             f'M{gx} {gy + 78} L{gx} {gy + 150} M{gx - 38} {gy + 156} Q{gx} {gy + 144} {gx + 38} {gy + 156}')
    liquid = f'M{gx - 47} {gy + 17} L{gx + 47} {gy + 17}'
    d.add(f'<g class="on2"><g class="tw">'
          f'<path d="{glass}" fill="none" stroke="{P["neon_cyan"]}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" filter="{cyan}"/>'
          f'<path d="{glass}" fill="none" stroke="#E9FDFF" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
          f'<path d="{liquid}" fill="none" stroke="{P["neon_cyan"]}" stroke-width="3" stroke-linecap="round" opacity=".7" filter="{cyan}"/>'
          f'</g>'
          f'<g class="blink2"><line x1="{gx + 44}" y1="{gy - 38}" x2="{gx + 6}" y2="{gy + 40}" stroke="#FFD58A" stroke-width="3" stroke-linecap="round" filter="{amber}"/>'
          f'<circle cx="{gx + 17}" cy="{gy + 18}" r="12" fill="none" stroke="#7CFF6B" stroke-width="4.5" filter="{green}"/>'
          f'<circle cx="{gx + 17}" cy="{gy + 18}" r="12" fill="none" stroke="#EFFFE9" stroke-width="1.6"/>'
          f'<circle cx="{gx + 21}" cy="{gy + 14}" r="3" fill="#FF6B5A" filter="{amber}"/></g></g>')

    # --- OPEN TO WORK sign (right), hanging
    red = glow_filter(d, "gRed", P["neon_red"], radii=(2.5, 7, 17), strength=.95, core_blur=.3)
    sx, sy, sw_, sh_ = 1046, 138, 178, 114
    x0, y0 = sx - sw_ / 2, sy
    chains = (f'<line x1="{x0 + 22}" y1="{y0}" x2="{x0 + 34}" y2="30" stroke="#5A4A30" stroke-width="1.3" stroke-dasharray="3 2"/>'
              f'<line x1="{x0 + sw_ - 22}" y1="{y0}" x2="{x0 + sw_ - 34}" y2="30" stroke="#5A4A30" stroke-width="1.3" stroke-dasharray="3 2"/>')
    plate = f'<rect x="{x0}" y="{y0}" width="{sw_}" height="{sh_}" rx="14" fill="#140B0C" opacity=".85" stroke="#2B1B1C"/>'
    border = f'<rect x="{x0 + 10}" y="{y0 + 10}" width="{sw_ - 20}" height="{sh_ - 20}" rx="10" fill="none"'
    t_open, _, _ = d.text("tilt", "OPEN", sx, y0 + 58, 44, anchor="middle", ls=4, fill=P["neon_red"],
                          attrs=f'stroke="{P["neon_red"]}" stroke-width="{num(1.2 / (44 / font("tilt").upem))}"')
    t_open_c, _, _ = d.text("tilt", "OPEN", sx, y0 + 58, 44, anchor="middle", ls=4, fill="#FFE9EA")
    t_work, _, _ = d.text("tilt", "TO WORK", sx, y0 + 90, 22, anchor="middle", ls=5.5, fill=P["neon_red"],
                          attrs=f'stroke="{P["neon_red"]}" stroke-width="{num(1 / (22 / font("tilt").upem))}"')
    t_work_c, _, _ = d.text("tilt", "TO WORK", sx, y0 + 90, 22, anchor="middle", ls=5.5, fill="#FFE9EA")
    d.add(f'<g transform="rotate(-3 {sx} 30)">{chains}{plate}'
          f'<g class="on3">'
          f'{border} stroke="{P["neon_red"]}" stroke-width="3.2" filter="{red}"/>{border} stroke="#FFD9DC" stroke-width="1.1"/>'
          f'<g filter="{red}">{t_open}</g>{t_open_c}'
          f'<g class="blink"><g filter="{red}">{t_work}</g>{t_work_c}</g>'
          f'</g></g>')

    # --- subtitle + tagline
    sub, sw, _ = d.text("deco", "SOFTWARE ENGINEER  ·  AI PRODUCT BUILDER", W / 2, 350, 22, anchor="middle", ls=6.5, fill="url(#gtext)")
    d.add(f'<g class="rise" style="animation-delay:1.1s">{sub}{deco_rule(W / 2, 306, 120, "#B08A45", gap=14, sw=1)}</g>')
    tag, _, _ = d.text("serifi", "Ten years behind the bar. Now I build software.", W / 2, 398, 23, anchor="middle", fill=P["cream"], attrs='opacity=".78"')
    d.add(f'<g class="rise" style="animation-delay:1.5s">{tag}</g>')
    return finish(d, "header.svg")



# =============================================================================== TERMINAL
def segs(d, parts, x, y, size, cls=None, attrs="", glyph_attrs=None):
    """parts: [(text, fontkey, color)] rendered back-to-back. Returns (svg, width)."""
    out = []
    cx = x
    for text, fk, col in parts:
        g, w, _ = d.text(fk, text, cx, y, size, fill=col, glyph_attrs=glyph_attrs)
        out.append(g)
        cx += w
    inner = "".join(out)
    if cls or attrs:
        inner = f'<g{(" class=%s" % chr(34) + cls + chr(34)) if cls else ""} {attrs}>{inner}</g>'
    return inner, cx - x


def check_icon(x, y, s, col):
    return (f'<path d="M{num(x)} {num(y - s * .45)} l{num(s * .36)} {num(s * .36)} l{num(s * .64)} {num(-s * .78)}" '
            f'fill="none" stroke="{col}" stroke-width="{num(s * .2)}" stroke-linecap="round" stroke-linejoin="round"/>')


def terminal():
    W, H = 1000, 398
    d = base_doc(W, H, "Terminal: whoami — Carlos Franco",
                 "An animated terminal. whoami: Carlos Franco, software engineer in training at FIAP, Sao Paulo. "
                 "career.log: 10 years in luxury hospitality (bartender, head bartender, head of bar); 2024 founded "
                 "Vica Experiencias, an events and bar brand; 2026 designed a cocktail menu awarded Best Drinks Menu; "
                 "now building AI products and full-stack software. ./hire: available for internships and junior roles.",
                 frame=False, radius=16)
    d.body.clear()
    size, lh, x0 = 17.5, 31, 34
    cw = font("mono").width("M", size)
    G, C, C2, M, A = P["gold"], P["cream"], P["cream2"], P["muted"], P["amber"]
    d.css.append("""
.k{animation:k .01s linear both}
.ln{animation:ln .35s ease-out both}
@keyframes k{from{opacity:0}to{opacity:1}}
@keyframes ln{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.cur{opacity:0}
.fin{animation:k .01s linear both}
.bl{animation:bl 1.05s steps(1) infinite}
@keyframes bl{0%{opacity:1}50%{opacity:0}}
""")
    # window
    d.add(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="16" fill="#0E0C0A" stroke="#3A3122"/>')
    glow = rad_grad(d, "tglow", [(0, "#FFB25E", .10), (1, "#000", 0)], cx=.5, cy=0, r=.7)
    d.add(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="16" fill="{glow}"/>')
    d.add(f'<path d="M.5 42 H{W - .5}" stroke="#2A2419"/>')
    for i, c in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        d.add(f'<circle cx="{24 + i * 20}" cy="21" r="6" fill="{c}"/>')
    t, _, _ = d.text("mono", "carlos@francosdev: ~ — zsh", W / 2, 26, 13, anchor="middle", fill=M)
    d.add(t)

    lines = []   # (kind, parts, t)
    PROMPT = [("~ ", "mono7", G), ("❯ ", "mono7", A)]
    script = [
        ("cmd", "whoami", []),
        ("out", [("Carlos Franco", "mono7", C), (" — software engineer in training @ ", "mono", C2), ("FIAP", "mono7", G), (" · São Paulo, BR", "mono", C2)]),
        ("cmd", "cat career.log", []),
        ("out", [("[10 yrs] ", "mono", M), ("luxury hospitality · bartender → head bartender → head of bar", "mono", C2)]),
        ("out", [("[2024]   ", "mono", M), ("founded ", "mono", C2), ("Vica Experiências", "mono7", G), (", an events & bar brand", "mono", C2)]),
        ("out", [("[2026]   ", "mono", M), ("designed a cocktail menu awarded ", "mono", C2), ("Best Drinks Menu", "mono7", G)]),
        ("out", [("[now]    ", "mono", M), ("building ", "mono", C2), ("AI products", "mono7", C), (" & ", "mono", C2), ("full-stack software", "mono7", C)]),
        ("cmd", "./hire carlos --role intern,junior", [("--role", G), ("intern,junior", A)]),
        ("ok",  [("available", "mono7", P["green"]), (" · open to internships & junior roles. let's talk.", "mono", C2)]),
        ("end", None),
    ]
    tt = 0.6            # timeline cursor (s)
    y = 84
    for item in script:
        kind = item[0]
        if kind == "cmd":
            cmd, hl = item[1], item[2]
            pg, pw = segs(d, PROMPT, x0, y, size)
            d.add(f'<g class="ln" style="animation-delay:{num(tt - .25)}s">{pg}</g>')
            # colourise flags
            colors = [C] * len(cmd)
            for word, col in hl:
                i = cmd.find(word)
                for j in range(i, i + len(word)):
                    colors[j] = col
            cps = 0.075 if len(cmd) < 10 else (0.055 if len(cmd) < 20 else 0.042)
            start = tt
            runs = []
            # split into colour runs but keep global char index for delays
            i = 0
            while i < len(cmd):
                j = i
                while j < len(cmd) and colors[j] == colors[i]:
                    j += 1
                runs.append((i, cmd[i:j], colors[i]))
                i = j
            cx = x0 + pw
            for (i0, txt, col) in runs:
                def ga(gi, cl, gx, i0=i0):
                    return f'class="k" style="animation-delay:{num(start + (i0 + cl + 1) * cps, 3)}s"'
                g, w, _ = d.text("mono", txt, cx, y, size, fill=col, glyph_attrs=ga)
                d.add(g)
                cx += w
            n = len(cmd)
            t_end = start + n * cps
            hold = 0.45
            win = t_end + hold - start
            kf = f"mv{len(lines)}"
            d.css.append(f"@keyframes {kf}{{0%{{transform:translateX(0);opacity:1}}"
                         f"{num((n * cps) / win * 100, 2)}%{{transform:translateX({num(n * cw, 2)}px);opacity:1}}"
                         f"100%{{transform:translateX({num(n * cw, 2)}px);opacity:1}}}}")
            d.add(f'<rect class="cur" x="{num(x0 + pw)}" y="{num(y - size * .82)}" width="{num(cw * .92)}" height="{num(size * 1.05)}" '
                  f'fill="{A}" style="animation:{kf} {num(win, 3)}s steps({n},end) {num(start, 3)}s"/>')
            tt = t_end + hold
            lines.append(kind)
        elif kind in ("out", "ok"):
            parts = item[1]
            xx = x0
            pre = ""
            if kind == "ok":
                pre = check_icon(x0 + 2, y - 5, 14, P["green"])
                xx = x0 + 24
            g, w = segs(d, parts, xx, y, size)
            d.add(f'<g class="ln" style="animation-delay:{num(tt, 3)}s">{pre}{g}</g>')
            tt += 0.16 if kind == "out" else 0.3
            lines.append(kind)
        elif kind == "end":
            tt += 0.25
            pg, pw = segs(d, PROMPT, x0, y, size)
            d.add(f'<g class="fin" style="animation-delay:{num(tt, 3)}s">{pg}'
                  f'<rect class="bl" x="{num(x0 + pw)}" y="{num(y - size * .82)}" width="{num(cw * .92)}" height="{num(size * 1.05)}" fill="{A}"/></g>')
        y += lh
        if kind == "cmd":
            tt += 0.05
    print("    terminal timeline ends at", round(tt, 2), "s")
    return finish(d, "terminal.svg")


# =============================================================================== PROJECT CARDS
def pill(d, x_right, y, text, col, pulse=True):
    tw = d.measure("sans7", text, 11, ls=1.6)
    w = tw + 34
    x = x_right - w
    t, _, _ = d.text("sans7", text, x + 24, y + 4, 11, ls=1.6, fill=col)
    ring = (f'<circle class="pulse" cx="{num(x + 13)}" cy="{num(y)}" r="4" fill="none" stroke="{col}" stroke-width="1.5"/>'
            if pulse else "")
    return (f'<rect x="{num(x)}" y="{num(y - 12)}" width="{num(w)}" height="24" rx="12" fill="{col}" fill-opacity=".08" stroke="{col}" stroke-opacity=".45"/>'
            f'{ring}<circle cx="{num(x + 13)}" cy="{num(y)}" r="3.6" fill="{col}"/>{t}')


def card_frame(d, W, H, accent):
    return (f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="16" fill="none" stroke="#3A3122"/>'
            f'<rect x="7.5" y="7.5" width="{W - 15}" height="{H - 15}" rx="11" fill="none" stroke="url(#fg)" stroke-width=".8" opacity=".55"/>')


CARD_CSS = """
.pulse{animation:pulse 2.4s ease-out infinite;transform-box:fill-box;transform-origin:center}
@keyframes pulse{0%{transform:scale(1);opacity:.9}100%{transform:scale(3.2);opacity:0}}
.fade{animation:fade 1s ease-out both}
@keyframes fade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
"""


def project_card(file, meta, illo):
    W, H = 1000, 330
    d = base_doc(W, H, meta["title"] + " — " + meta["subtitle"], meta["desc"], frame=False, radius=16)
    d.css.append(CARD_CSS)
    # left illustration panel
    px, py, ps = 24, 24, 282
    d.defs.append(f'<clipPath id="panel"><rect x="{px}" y="{py}" width="{ps}" height="{ps}" rx="12"/></clipPath>')
    d.add(f'<g clip-path="url(#panel)">{illo(d, px, py, ps)}</g>')
    d.add(f'<rect x="{px + .5}" y="{py + .5}" width="{ps - 1}" height="{ps - 1}" rx="12" fill="none" stroke="#FFFFFF" stroke-opacity=".08"/>')
    # text block
    x = 336
    lab, _, _ = d.text("deco", meta["label"], x, 60, 13, ls=3.2, fill=P["gold2"])
    d.add(lab)
    d.add(pill(d, W - 30, 55, meta["status"], meta["status_col"]))
    t, tw, _ = d.text("serif", meta["title"], x - 2, 118, 50, fill=P["cream"])
    d.add(t)
    if meta.get("title_note"):
        n, _, _ = d.text("serifi", meta["title_note"], x + tw + 14, 118, 22, fill=P["gold"], attrs='opacity=".85"')
        d.add(n)
    s, _, _ = d.text("sans", meta["subtitle"], x, 150, 17, fill=P["cream2"])
    d.add(s)
    d.add(f'<line x1="{x}" y1="172" x2="{x + 64}" y2="172" stroke="{P["gold2"]}" stroke-width="1.5"/>'
          f'<rect x="{x + 70}" y="169" width="6" height="6" transform="rotate(45 {x + 73} 172)" fill="{P["gold2"]}"/>')
    sp, _, _ = d.text("deco", "SPEC", x, 200, 11.5, ls=3, fill=P["muted"])
    d.add(sp)
    yy = 200
    for amt, ing in meta["spec"]:
        a, _, _ = d.text("mono7", amt, x + 150, yy, 14.5, anchor="end", fill=P["gold"])
        i, _, _ = d.text("mono", ing, x + 166, yy, 14.5, fill=P["cream"])
        d.add(a, i)
        yy += 24
    m, _, _ = d.text("serifi", meta["method"], x, yy + 14, 16, fill=P["muted"])
    d.add(m)
    d.add(card_frame(d, W, H, meta["status_col"]))
    return finish(d, file)


def stars(rnd, n, x, y, w, h, col="#FFF3D7", rmin=.6, rmax=1.6, cls="tw4"):
    out = []
    for i in range(n):
        sx, sy = x + rnd.uniform(0, w), y + rnd.uniform(0, h)
        r = rnd.uniform(rmin, rmax)
        dur = rnd.uniform(2.2, 5.5)
        out.append(f'<circle class="{cls}" cx="{num(sx)}" cy="{num(sy)}" r="{num(r)}" fill="{col}" '
                   f'style="animation-duration:{num(dur)}s;animation-delay:{num(-rnd.uniform(0, dur))}s"/>')
    return "".join(out)


def sparkle(cx, cy, r, col, extra=""):
    k = r * .28
    return (f'<path d="M{num(cx)} {num(cy - r)} Q{num(cx + k)} {num(cy - k)} {num(cx + r)} {num(cy)} Q{num(cx + k)} {num(cy + k)} {num(cx)} {num(cy + r)} '
            f'Q{num(cx - k)} {num(cy + k)} {num(cx - r)} {num(cy)} Q{num(cx - k)} {num(cy - k)} {num(cx)} {num(cy - r)}Z" fill="{col}" {extra}/>')


def bottle_path(kind, x, y, w, h):
    """Bottle silhouettes. (x, y) = bottom-left, grows upward. Returns path d."""
    if kind == "whisky":      # square shoulders
        nw, nh, sh = w * .28, h * .26, h * .12
        return (f"M{num(x)} {num(y)} V{num(y - h + nh + sh)} Q{num(x)} {num(y - h + nh)} {num(x + w * .3)} {num(y - h + nh)} "
                f"H{num(x + w / 2 - nw / 2)} V{num(y - h)} H{num(x + w / 2 + nw / 2)} V{num(y - h + nh)} H{num(x + w * .7)} "
                f"Q{num(x + w)} {num(y - h + nh)} {num(x + w)} {num(y - h + nh + sh)} V{num(y)} Z")
    if kind == "gin":         # tall, round shoulders
        nw, nh = w * .26, h * .3
        return (f"M{num(x)} {num(y)} V{num(y - h * .55)} C{num(x)} {num(y - h * .7)} {num(x + w / 2 - nw / 2)} {num(y - h + nh + 6)} "
                f"{num(x + w / 2 - nw / 2)} {num(y - h + nh)} V{num(y - h)} H{num(x + w / 2 + nw / 2)} V{num(y - h + nh)} "
                f"C{num(x + w / 2 + nw / 2)} {num(y - h + nh + 6)} {num(x + w)} {num(y - h * .7)} {num(x + w)} {num(y - h * .55)} V{num(y)} Z")
    if kind == "round":       # liqueur flask
        nw, nh = w * .24, h * .28
        cy = y - (h - nh) / 2
        rx, ry = w / 2, (h - nh) / 2
        return (f"M{num(x + w / 2 - nw / 2)} {num(y - h + nh)} V{num(y - h)} H{num(x + w / 2 + nw / 2)} V{num(y - h + nh)} "
                f"A{num(rx)} {num(ry)} 0 1 1 {num(x + w / 2 - nw / 2)} {num(y - h + nh)} Z")
    if kind == "slim":        # vodka
        nw, nh = w * .3, h * .22
        return (f"M{num(x)} {num(y)} V{num(y - h + nh + 14)} L{num(x + w / 2 - nw / 2)} {num(y - h + nh)} V{num(y - h)} "
                f"H{num(x + w / 2 + nw / 2)} V{num(y - h + nh)} L{num(x + w)} {num(y - h + nh + 14)} V{num(y)} Z")
    if kind == "bitters":     # small dasher bottle
        nw, nh = w * .34, h * .34
        return (f"M{num(x)} {num(y)} V{num(y - h * .5)} Q{num(x)} {num(y - h + nh)} {num(x + w / 2 - nw / 2)} {num(y - h + nh)} "
                f"V{num(y - h)} H{num(x + w / 2 + nw / 2)} V{num(y - h + nh)} Q{num(x + w)} {num(y - h + nh)} {num(x + w)} {num(y - h * .5)} V{num(y)} Z")
    raise ValueError(kind)


def illo_barops(d, x, y, s):
    d.css.append("""
.lvl{animation:lvl 7s ease-in-out infinite;transform-box:fill-box;transform-origin:bottom}
@keyframes lvl{0%,8%{transform:scaleY(1)}55%{transform:scaleY(.22)}62%{transform:scaleY(.22)}70%,100%{transform:scaleY(1)}}
.spin{animation:spin 2.6s linear infinite;transform-box:fill-box;transform-origin:center}
@keyframes spin{to{transform:rotate(360deg)}}
.cell{animation:cell 3.5s steps(1) infinite}
@keyframes cell{0%{opacity:.15}50%,100%{opacity:1}}
.tick{animation:tick 7s linear infinite}
@keyframes tick{0%,62%{opacity:0}66%,92%{opacity:1}100%{opacity:0}}
""")
    bg = lin_grad(d, "bbg", [(0, "#2A1A0C"), (1, "#0F0B07")])
    glow = rad_grad(d, "bglow", [(0, "#FFB25E", .35), (1, "#000", 0)], cx=.5, cy=.62, r=.55)
    out = [f'<rect x="{x}" y="{y}" width="{s}" height="{s}" fill="{bg}"/>',
           f'<rect x="{x}" y="{y}" width="{s}" height="{s}" fill="{glow}"/>']
    # spreadsheet grid (back)
    gx, gy, cw, ch = x + 24, y + 26, 22, 12
    for r in range(4):
        for c in range(5):
            delay = (r * 5 + c) * .14
            out.append(f'<rect class="cell" x="{gx + c * (cw + 3)}" y="{gy + r * (ch + 3)}" width="{cw}" height="{ch}" rx="2" '
                       f'fill="{"#E6C27A" if c == 0 else "#6BE39A"}" fill-opacity="{.28 if c else .4}" style="animation-delay:{num(delay)}s"/>')
    # shelf
    sy = y + 212
    out.append(f'<rect x="{x + 18}" y="{sy}" width="{s - 36}" height="7" rx="2" fill="#6E5020"/>'
               f'<rect x="{x + 18}" y="{sy}" width="{s - 36}" height="2" fill="#E6C27A" opacity=".7"/>')
    bottles = [("whisky", x + 34, 62, 118, "#D98A2B", 0), ("gin", x + 108, 50, 150, "#BFE3E0", 1.7),
               ("round", x + 170, 70, 104, "#7BC26B", 3.3)]
    for i, (k, bx, bw, bh, liq, delay) in enumerate(bottles):
        pth = bottle_path(k, bx, sy, bw, bh)
        cid = f"bc{i}"
        d.defs.append(f'<clipPath id="{cid}"><path d="{pth}"/></clipPath>')
        out.append(f'<path d="{pth}" fill="#FFFFFF" fill-opacity=".06" stroke="#FFFFFF" stroke-opacity=".35" stroke-width="1.4"/>')
        top = sy - bh * .62
        out.append(f'<g clip-path="url(#{cid})"><rect class="lvl" x="{bx}" y="{num(top)}" width="{bw}" height="{num(sy - top)}" '
                   f'fill="{liq}" fill-opacity=".78" style="animation-delay:{delay}s"/></g>')
        out.append(f'<rect x="{num(bx + bw * .18)}" y="{num(sy - bh * .42)}" width="{num(bw * .64)}" height="{num(bh * .2)}" rx="3" fill="#F4ECDC" opacity=".9"/>'
                   f'<rect x="{num(bx + bw * .28)}" y="{num(sy - bh * .36)}" width="{num(bw * .44)}" height="3" rx="1.5" fill="#8C6A2F"/>'
                   f'<rect x="{num(bx + bw * .34)}" y="{num(sy - bh * .31)}" width="{num(bw * .32)}" height="2.5" rx="1.2" fill="#C9A25A"/>')
        out.append(f'<path d="M{num(bx + 7)} {num(sy - bh * .55)} V{num(sy - 10)}" stroke="#FFFFFF" stroke-opacity=".28" stroke-width="3" stroke-linecap="round"/>')
    # sync badge
    cx, cy = x + 240, y + 46
    out.append(f'<circle cx="{cx}" cy="{cy}" r="22" fill="#0F0B07" stroke="#6BE39A" stroke-opacity=".6"/>'
               f'<g class="spin"><path d="M{cx - 11} {cy - 2} A11 11 0 0 1 {cx + 9} {cy - 7}" fill="none" stroke="#6BE39A" stroke-width="2.4" stroke-linecap="round"/>'
               f'<path d="M{cx + 9} {cy - 13} L{cx + 10} {cy - 6} L{cx + 3} {cy - 6}" fill="none" stroke="#6BE39A" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
               f'<path d="M{cx + 11} {cy + 2} A11 11 0 0 1 {cx - 9} {cy + 7}" fill="none" stroke="#6BE39A" stroke-width="2.4" stroke-linecap="round"/>'
               f'<path d="M{cx - 9} {cy + 13} L{cx - 10} {cy + 6} L{cx - 3} {cy + 6}" fill="none" stroke="#6BE39A" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></g>')
    return "".join(out)


def illo_mimo(d, x, y, s):
    d.css.append("""
.tw4{animation:tw4 3s ease-in-out infinite}
@keyframes tw4{0%,100%{opacity:.25}50%{opacity:1}}
.halo{animation:halo 4s ease-in-out infinite;transform-box:fill-box;transform-origin:center}
@keyframes halo{0%,100%{transform:scale(1);opacity:.55}50%{transform:scale(1.12);opacity:.95}}
.up{animation:up 3.6s ease-out infinite}
@keyframes up{0%{transform:translateY(0);opacity:0}20%{opacity:1}100%{transform:translateY(-70px);opacity:0}}
.page{animation:page 6s ease-in-out infinite;transform-box:fill-box;transform-origin:left}
@keyframes page{0%,40%{transform:scaleX(1)}50%{transform:scaleX(-1)}90%,100%{transform:scaleX(-1)}}
""")
    rnd = random.Random(11)
    bg = lin_grad(d, "mbg", [(0, "#1B1433"), (1, "#0D0A1A")])
    out = [f'<rect x="{x}" y="{y}" width="{s}" height="{s}" fill="{bg}"/>', stars(rnd, 34, x + 6, y + 6, s - 12, s * .62)]
    # moon with double halo (like the app's home screen)
    mx, my = x + s * .62, y + s * .33
    hal = rad_grad(d, "mh", [(0, "#d4a853", .45), (.6, "#d4a853", .12), (1, "#d4a853", 0)])
    out.append(f'<circle class="halo" cx="{num(mx)}" cy="{num(my)}" r="58" fill="{hal}"/>'
               f'<circle class="halo" cx="{num(mx)}" cy="{num(my)}" r="40" fill="none" stroke="#d4a853" stroke-opacity=".35" style="animation-delay:-2s"/>')
    d.defs.append(f'<mask id="crescent"><rect x="{x}" y="{y}" width="{s}" height="{s}" fill="#000"/>'
                  f'<circle cx="{num(mx)}" cy="{num(my)}" r="30" fill="#fff"/><circle cx="{num(mx + 13)}" cy="{num(my - 9)}" r="26" fill="#000"/></mask>')
    out.append(f'<circle cx="{num(mx)}" cy="{num(my)}" r="30" fill="#E9C46A" mask="url(#crescent)"/>')
    for i in range(4):
        sx, sy = x + rnd.uniform(30, s - 30), y + rnd.uniform(20, s * .5)
        out.append(sparkle(sx, sy, rnd.uniform(4, 7), "#FFF3D7", f'class="tw4" style="animation-delay:{num(-i * .8)}s"'))
    # open book
    bx, by = x + s / 2, y + s * .83
    out.append(f'<path d="M{num(bx - 98)} {num(by - 4)} Q{num(bx - 50)} {num(by - 24)} {num(bx)} {num(by - 6)} Q{num(bx + 50)} {num(by - 24)} {num(bx + 98)} {num(by - 4)} '
               f'V{num(by + 12)} Q{num(bx + 50)} {num(by - 6)} {num(bx)} {num(by + 12)} Q{num(bx - 50)} {num(by - 6)} {num(bx - 98)} {num(by + 12)} Z" fill="#a67fd8"/>')
    out.append(f'<path d="M{num(bx - 92)} {num(by - 8)} Q{num(bx - 48)} {num(by - 30)} {num(bx)} {num(by - 10)} V{num(by + 6)} Q{num(bx - 48)} {num(by - 12)} {num(bx - 92)} {num(by + 4)} Z" fill="#fff3d7"/>'
               f'<path d="M{num(bx + 92)} {num(by - 8)} Q{num(bx + 48)} {num(by - 30)} {num(bx)} {num(by - 10)} V{num(by + 6)} Q{num(bx + 48)} {num(by - 12)} {num(bx + 92)} {num(by + 4)} Z" fill="#F2E3C0"/>')
    for i, dx in enumerate((-60, -46, -32)):
        out.append(f'<path d="M{num(bx + dx)} {num(by - 14 + i * 1.5)} q20 -6 40 0" stroke="#c4839a" stroke-opacity=".6" stroke-width="2" fill="none"/>')
    out.append(f'<path class="page" d="M{num(bx)} {num(by - 10)} Q{num(bx + 44)} {num(by - 30)} {num(bx + 86)} {num(by - 10)} V{num(by + 4)} Q{num(bx + 44)} {num(by - 14)} {num(bx)} {num(by + 6)} Z" fill="#FFF8E8" opacity=".95"/>')
    for i in range(7):
        sx = bx + rnd.uniform(-60, 60)
        out.append(f'<g class="up" style="animation-delay:{num(i * .5)}s">{sparkle(sx, by - 20, rnd.uniform(3, 5.5), rnd.choice(["#d4a853", "#FFF3D7", "#a67fd8"]))}</g>')
    return "".join(out)


def illo_aura(d, x, y, s):
    d.css.append("""
.ecg{stroke-dasharray:60 540;animation:ecg 2.8s linear infinite}
@keyframes ecg{from{stroke-dashoffset:600}to{stroke-dashoffset:0}}
.needle{animation:needle 6s ease-in-out infinite;transform-origin:var(--nx) var(--ny)}
@keyframes needle{0%,100%{transform:rotate(-48deg)}45%{transform:rotate(-8deg)}55%{transform:rotate(-14deg)}}
.orbit{animation:orbit 9s linear infinite;transform-origin:var(--ox) var(--oy)}
@keyframes orbit{to{transform:rotate(360deg)}}
.win{animation:tw4 2.6s ease-in-out infinite}
""")
    rnd = random.Random(5)
    bg = lin_grad(d, "abg", [(0, "#101426"), (1, "#070A14")])
    out = [f'<rect x="{x}" y="{y}" width="{s}" height="{s}" fill="{bg}"/>', stars(rnd, 40, x + 4, y + 4, s - 8, s * .7, col="#CFEFFF")]
    # planet (earth) far, orbit + satellite
    ex, ey = x + 62, y + 70
    out.append(f'<circle cx="{ex}" cy="{ey}" r="20" fill="#4DE6FF" fill-opacity=".2" stroke="#4DE6FF" stroke-opacity=".7"/>'
               f'<path d="M{ex - 14} {ey - 4} q8 -8 16 -2 q6 5 12 -2" stroke="#4DE6FF" stroke-opacity=".7" fill="none"/>')
    out.append(f'<ellipse cx="{ex}" cy="{ey}" rx="36" ry="12" fill="none" stroke="#4DE6FF" stroke-opacity=".25" transform="rotate(-18 {ex} {ey})"/>')
    out.append(f'<g class="orbit" style="--ox:{ex}px;--oy:{ey}px"><circle cx="{ex + 36}" cy="{ey}" r="3" fill="#FF5C7C"/></g>')
    # moon surface + habitat dome
    out.append(f'<ellipse cx="{x + s / 2}" cy="{y + s + 150}" rx="{s}" ry="205" fill="#1C2233"/>'
               f'<ellipse cx="{x + s / 2}" cy="{y + s + 150}" rx="{s}" ry="205" fill="none" stroke="#4DE6FF" stroke-opacity=".25"/>')
    for (cx_, cy_, r_) in ((x + 40, y + 262, 9), (x + 230, y + 256, 6), (x + 120, y + 272, 5)):
        out.append(f'<ellipse cx="{cx_}" cy="{cy_}" rx="{r_}" ry="{r_ * .35}" fill="#0D1120"/>')
    hx, hy = x + 176, y + 236
    out.append(f'<path d="M{hx - 44} {hy} A44 40 0 0 1 {hx + 44} {hy} Z" fill="#20283D" stroke="#9FEFFF" stroke-opacity=".55"/>')
    for i, wx in enumerate((-22, 0, 22)):
        out.append(f'<circle class="win" cx="{hx + wx}" cy="{hy - 16}" r="4" fill="#FFD27A" style="animation-delay:{-i * .7}s"/>')
    out.append(f'<rect x="{hx + 44}" y="{hy - 8}" width="30" height="8" rx="2" fill="#20283D" stroke="#9FEFFF" stroke-opacity=".4"/>')
    # ECG line
    base = y + 150
    pts = [(0, 0), (40, 0), (52, -6), (62, 6), (72, 0), (86, 0), (94, -34), (104, 30), (114, -10), (124, 0), (150, 0), (162, -8), (174, 0), (282, 0)]
    dpath = "M" + " L".join(f"{num(x + px_)} {num(base + py_)}" for px_, py_ in pts)
    out.append(f'<path d="{dpath}" fill="none" stroke="#4DE6FF" stroke-opacity=".22" stroke-width="2"/>'
               f'<path class="ecg" d="{dpath}" fill="none" stroke="#4DE6FF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" pathLength="600"/>')
    # ICE gauge
    gx, gy, r = x + 214, y + 86, 34
    def arc(a0, a1, col):
        p0 = (gx + r * math.cos(math.radians(a0)), gy - r * math.sin(math.radians(a0)))
        p1 = (gx + r * math.cos(math.radians(a1)), gy - r * math.sin(math.radians(a1)))
        return (f'<path d="M{num(p0[0])} {num(p0[1])} A{r} {r} 0 0 1 {num(p1[0])} {num(p1[1])}" fill="none" stroke="{col}" '
                f'stroke-width="7" stroke-linecap="butt"/>')
    out.append(arc(180, 118, "#2EE59D") + arc(116, 62, "#FFC857") + arc(60, 0, "#FF5C7C"))
    out.append(f'<g class="needle" style="--nx:{gx}px;--ny:{gy}px"><line x1="{gx}" y1="{gy}" x2="{gx}" y2="{gy - r + 4}" stroke="#F4ECDC" stroke-width="2.4" stroke-linecap="round"/></g>'
               f'<circle cx="{gx}" cy="{gy}" r="4" fill="#F4ECDC"/>')
    t, _, _ = d.text("mono7", "ICE", gx, gy + 18, 11, anchor="middle", ls=2, fill="#9FEFFF")
    out.append(t)
    return "".join(out)


def card_barops():
    return project_card("card-barops.svg", {
        "title": "BarOps", "subtitle": "Bar operations platform, built behind a real bar",
        "desc": "Project card for BarOps: a bar operations and inventory platform built with React, Vite, Google Apps Script "
                "and Google Sheets. In production.",
        "label": "Nº 01 · HOUSE SIGNATURE", "status": "IN PRODUCTION", "status_col": P["green"],
        "spec": [("50 ml", "React 19 + Vite"), ("25 ml", "Google Apps Script API"),
                 ("15 ml", "Google Sheets, as the database"), ("2 dashes", "jsPDF · SheetJS exports")],
        "method": "Built on the bar floor. Stress-tested in real service.",
    }, illo_barops)


def card_mimo():
    return project_card("card-mimo.svg", {
        "title": "Mimo", "title_note": "histórias que abraçam",
        "subtitle": "AI bedtime stories where the child is the hero",
        "desc": "Project card for Mimo: a React Native and Expo app that generates personalized children's stories with an LLM. In development.",
        "label": "Nº 02 · BEDTIME SPECIAL", "status": "IN DEVELOPMENT", "status_col": P["amber"],
        "spec": [("50 ml", "React Native + Expo"), ("20 ml", "Llama 3.3 70B via Groq"),
                 ("10 ml", "AsyncStorage"), ("1 pinch", "hand-built animations")],
        "method": "Stirred slowly. No streaks, no push notifications.",
    }, illo_mimo)


def card_aura():
    return project_card("card-aura.svg", {
        "title": "AURA", "subtitle": "Emotional OS for space crews, before stress becomes crisis",
        "desc": "Project card for AURA: an emotional monitoring system for space crews, built with Python, JavaScript, "
                "IBM Watson and Oracle SQL. Live demo available. Team project.",
        "label": "Nº 03 · OFF-WORLD SERVE", "status": "LIVE DEMO", "status_col": "#4DE6FF",
        "spec": [("40 ml", "Python · 69 automated tests"), ("30 ml", "HTML · CSS · vanilla JS"),
                 ("20 ml", "IBM Watson + Node-RED"), ("1 dash", "Oracle SQL")],
        "method": "Served in a lunar habitat. Team of three · FIAP Global Solution.",
    }, illo_aura)


# =============================================================================== BACK BAR (stack)
def lum(hexcol):
    h = hexcol.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def custom_icon(kind, x, y, size, col):
    s = size / 24
    if kind == "db":
        return (f'<g transform="translate({num(x)} {num(y)}) scale({num(s, 4)})" fill="none" stroke="{col}" stroke-width="2.2">'
                f'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></g>')
    if kind == "cup":
        return (f'<g transform="translate({num(x)} {num(y)}) scale({num(s, 4)})" fill="none" stroke="{col}" stroke-width="2" stroke-linecap="round">'
                f'<path d="M4 11h13v4a6 6 0 0 1-6 6h-1a6 6 0 0 1-6-6z" fill="{col}" fill-opacity=".25"/><path d="M17 12.5h1.5a2.5 2.5 0 0 1 0 5H16.5"/>'
                f'<path d="M8 2.5c-1.2 1.4 1.2 2.6 0 4.2M11.5 2.5c-1.2 1.4 1.2 2.6 0 4.2M15 2.5c-1.2 1.4 1.2 2.6 0 4.2"/></g>')
    if kind == "ai":
        return (f'<g transform="translate({num(x)} {num(y)}) scale({num(s, 4)})" fill="{col}">'
                f'<path d="M10 2l1.9 5.6L17.5 9.5l-5.6 1.9L10 17l-1.9-5.6L2.5 9.5l5.6-1.9z"/>'
                f'<path d="M18.5 13l.9 2.6 2.6.9-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9z"/></g>')
    raise ValueError(kind)


def backbar():
    W = 1000
    shelves = [
        ("SPIRITS", "languages", 128, 58, ["whisky", "gin", "slim", "whisky", "round"], [
            ("JavaScript", "javascript", None), ("TypeScript", "typescript", None), ("Python", "python", None),
            ("Java", ("cup", "#F29111"), "#ED8B00"), ("SQL", ("db", "#E6C27A"), "#C98B3A")]),
        ("LIQUEURS", "front-end & mobile", 118, 54, ["gin", "round", "slim", "whisky", "gin", "slim"], [
            ("React", "react", None), ("React Native", "expo", "#DDE3EA"), ("Vite", "vite", None),
            ("Tailwind", "tailwindcss", None), ("HTML5", "html5", None), ("CSS", "css", None)]),
        ("MIXERS", "back-end, cloud & AI", 112, 54, ["whisky", "slim", "gin", "round", "slim"], [
            ("Node.js", "nodedotjs", None), ("Apps Script", "googleappsscript", None), ("Google Cloud", "googlecloud", None),
            ("LLMs & Agents", ("ai", "#E6C27A"), "#B98AF0"), ("Netlify", "netlify", None)]),
        ("BAR TOOLS", "tooling", 92, 50, ["bitters", "bitters", "bitters", "bitters"], [
            ("Git", "git", None), ("GitHub", "github", "#C8CCD2"), ("Docker", "docker", None), ("Figma", "figma", None)]),
    ]
    row_h = 184
    top = 26
    H = top + row_h * len(shelves) + 46
    d = base_doc(W, H, "The Back Bar — Carlos Franco's tech stack",
                 "A backlit bar shelf where every bottle is a technology. Spirits (languages): JavaScript, TypeScript, Python, "
                 "Java, SQL. Liqueurs (front-end and mobile): React, React Native with Expo, Vite, Tailwind CSS, HTML5, CSS. "
                 "Mixers (back-end, cloud and AI): Node.js, Google Apps Script, Google Cloud, LLMs and AI agents, Netlify. "
                 "Bar tools: Git, GitHub, Docker, Figma.", radius=18, corners=False)
    d.css.append("""
.led{animation:led 5s ease-in-out infinite}
@keyframes led{0%,100%{opacity:.85}50%{opacity:1}}
.glint{animation:glint 7s ease-in-out infinite}
@keyframes glint{0%{transform:translateX(-160px)}45%,100%{transform:translateX(900px)}}
.pop{animation:pop .7s cubic-bezier(.2,.9,.3,1.3) both;transform-box:fill-box;transform-origin:bottom}
@keyframes pop{from{opacity:0;transform:translateY(14px) scale(.96)}to{opacity:1;transform:none}}
""")
    # mirror back wall
    mir = lin_grad(d, "mir", [(0, "#1A1612"), (.5, "#120F0C"), (1, "#0C0A08")], x1=0, y1=0, x2=1, y2=1)
    d.add(f'<rect x="206" y="28" width="{W - 234}" height="{H - 56}" rx="8" fill="{mir}" stroke="#2A2419"/>')
    for i, xx in enumerate((300, 560, 820)):
        d.add(f'<path d="M{xx} 29 L{xx + 60} 29 L{xx - 80} {H - 29} L{xx - 140} {H - 29} Z" fill="#FFFFFF" opacity="{.018 + i * .006}"/>')
    ledg = lin_grad(d, "ledg", [(0, "#FFB25E", 0), (.7, "#FFB25E", .10), (1, "#FFC47A", .42)])
    glintg = lin_grad(d, "glintg", [(0, "#FFFFFF", 0), (.5, "#FFFFFF", .55), (1, "#FFFFFF", 0)], x1=0, y1=0, x2=1, y2=0)
    for si, (cat, sub, bh, bw, kinds, items) in enumerate(shelves):
        sy = top + row_h * (si + 1) - 20          # shelf surface y
        # category (left column)
        c1, _, _ = d.text("deco7", cat, 36, sy - bh / 2 - 6, 15, ls=3.2, fill="url(#gtext)")
        c2, _, _ = d.text("serifi", sub, 36, sy - bh / 2 + 16, 14.5, fill=P["muted"])
        n1, _, _ = d.text("mono", f"0{si + 1}", 36, sy - bh / 2 - 30, 11, fill=P["gold3"])
        d.add(n1, c1, c2)
        # backlight + plank
        d.add(f'<rect class="led" x="210" y="{sy - 120}" width="{W - 234}" height="120" fill="{ledg}" style="animation-delay:{-si * 1.3}s"/>')
        d.add(f'<rect x="208" y="{sy}" width="{W - 230}" height="9" rx="2" fill="#4A3618"/>'
              f'<rect x="208" y="{sy}" width="{W - 230}" height="2.2" fill="#FFD89A" opacity=".85"/>'
              f'<rect x="208" y="{sy + 9}" width="{W - 230}" height="10" fill="#000" opacity=".35"/>')
        n = len(items)
        x_left, x_right = 232, W - 44
        slot = (x_right - x_left) / n
        clip_paths = []
        for i, ((label, ic, liq), kind) in enumerate(zip(items, kinds)):
            cx = x_left + slot * (i + .5)
            bx = cx - bw / 2
            pth = bottle_path(kind, bx, sy, bw, bh)
            clip_paths.append(pth)
            if isinstance(ic, tuple):
                icol = ic[1]
                liq = liq or icol
            else:
                meta = icon(ic)
                icol = "#" + meta["hex"]
                liq = liq or icol
            icol_on_black = icol if lum(icol) > .22 else "#E9E4DA"
            cid = d.uid("bt")
            d.defs.append(f'<clipPath id="{cid}"><path d="{pth}"/></clipPath>')
            delay = .15 + si * .35 + i * .08
            g = [f'<path d="{pth}" fill="#0B0A09" fill-opacity=".55"/>',
                 f'<g clip-path="url(#{cid})"><rect x="{num(bx)}" y="{num(sy - bh * .66)}" width="{bw}" height="{num(bh * .66)}" fill="{liq}" fill-opacity=".62"/>'
                 f'<rect x="{num(bx)}" y="{num(sy - bh * .66)}" width="{bw}" height="3" fill="#FFFFFF" fill-opacity=".35"/></g>',
                 f'<path d="{pth}" fill="none" stroke="#FFFFFF" stroke-opacity=".38" stroke-width="1.3"/>',
                 f'<path d="M{num(bx + 6)} {num(sy - bh * .5)} V{num(sy - 8)}" stroke="#FFFFFF" stroke-opacity=".25" stroke-width="3" stroke-linecap="round"/>']
            # cap
            capw = bw * (.34 if kind == "bitters" else .3)
            g.append(f'<rect x="{num(cx - capw / 2 - 1)}" y="{num(sy - bh - 7)}" width="{num(capw + 2)}" height="10" rx="2" fill="#8C6A2F"/>'
                     f'<rect x="{num(cx - capw / 2 - 1)}" y="{num(sy - bh - 7)}" width="{num(capw + 2)}" height="2.5" rx="1" fill="#F2D59A"/>')
            # label
            lw_, lh_ = bw * .84, 34 if kind != "bitters" else 30
            ly = sy - bh * (.46 if kind != "round" else .37) - lh_ / 2
            if kind == "bitters":
                ly = sy - bh * .38 - lh_ / 2
            g.append(f'<rect x="{num(cx - lw_ / 2)}" y="{num(ly)}" width="{num(lw_)}" height="{lh_}" rx="4" fill="#0B0A09" stroke="#C9A25A" stroke-width="1"/>')
            isz = 20 if kind != "bitters" else 17
            if isinstance(ic, tuple):
                g.append(custom_icon(ic[0], cx - isz / 2, ly + (lh_ - isz) / 2, isz, icol_on_black))
            else:
                g.append(icon_svg(ic, cx - isz / 2, ly + (lh_ - isz) / 2, isz, fill=icol_on_black))
            d.add(f'<g class="pop" style="animation-delay:{num(delay)}s">' + "".join(g) + "</g>")
            nm, _, _ = d.text("deco", label.upper(), cx, sy + 30, 10.5, anchor="middle", ls=1.6, fill=P["cream2"])
            d.add(nm)
        # glint over this shelf's bottles
        gid = d.uid("gl")
        d.defs.append(f'<clipPath id="{gid}">' + "".join(f'<path d="{p}"/>' for p in clip_paths) + "</clipPath>")
        d.add(f'<g clip-path="url(#{gid})"><rect class="glint" x="150" y="{sy - bh - 10}" width="46" height="{bh + 12}" '
              f'fill="{glintg}" transform="skewX(-18)" style="animation-delay:{num(1.2 + si * .9)}s"/></g>')
    return finish(d, "backbar.svg")


# =============================================================================== METHOD
def step_icon(kind, cx, cy, col):
    def A(sw=2):
        return f'fill="none" stroke="{col}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"'
    a = A()
    a15 = A(1.5)
    if kind == "ear":       # speech bubble with ?
        return (f'<path d="M{cx - 12} {cy - 10} h24 a3 3 0 0 1 3 3 v13 a3 3 0 0 1 -3 3 h-13 l-7 6 v-6 h-4 a3 3 0 0 1 -3 -3 v-13 a3 3 0 0 1 3 -3z" {a}/>'
                f'<path d="M{cx - 3.5} {cy - 3} a3.5 3.5 0 1 1 4.5 3.3 c-1 .4 -1 1.2 -1 2.2" {a}/><circle cx="{cx}" cy="{cy + 7.5}" r="1.2" fill="{col}"/>')
    if kind == "search":
        return f'<circle cx="{cx - 3}" cy="{cy - 3}" r="9" {a}/><path d="M{cx + 4} {cy + 4} l8 8" {a}/>'
    if kind == "sketch":
        return (f'<path d="M{cx - 12} {cy + 12} l3 -9 l14 -14 l6 6 l-14 14 z" {a}/><path d="M{cx + 1} {cy - 8} l6 6" {a}/>'
                f'<path d="M{cx - 13} {cy + 15} h26" {a} stroke-dasharray="3 3"/>')
    if kind == "shaker":
        return (f'<path d="M{cx - 9} {cy - 6} h18 l-3 20 h-12 z" {a}/><path d="M{cx - 8} {cy - 6} q8 -6 16 0" {a}/>'
                f'<path d="M{cx - 4} {cy - 10} q4 -8 8 0" {a}/><path d="M{cx - 1} {cy - 15} h2" {a}/>'
                f'<path d="M{cx - 16} {cy - 2} l-3 -2 M{cx + 16} {cy - 2} l3 -2 M{cx - 16} {cy + 5} h-4 M{cx + 16} {cy + 5} h4" {a15}/>')
    if kind == "taste":
        return (f'<path d="M{cx - 10} {cy + 12} l14 -14" {a}/><ellipse cx="{cx + 7}" cy="{cy - 5}" rx="5" ry="7.5" transform="rotate(45 {cx + 7} {cy - 5})" {a}/>'
                f'<path d="M{cx - 12} {cy - 12} l4 4 M{cx - 4} {cy - 15} v4" {a15}/>')
    if kind == "iterate":
        return (f'<path d="M{cx + 10} {cy - 5} a11 11 0 0 0 -19 -3" {a}/><path d="M{cx - 10} {cy - 10} v8 h8" {a}/>'
                f'<path d="M{cx - 10} {cy + 5} a11 11 0 0 0 19 3" {a}/><path d="M{cx + 10} {cy + 10} v-8 h-8" {a}/>')
    if kind == "serve":     # coupe glass with sparkle
        return (f'<path d="M{cx - 13} {cy - 9} h26 q-1 12 -13 13 q-12 -1 -13 -13z" {a}/><path d="M{cx} {cy + 4} v11 M{cx - 7} {cy + 15} h14" {a}/>'
                + sparkle(cx + 13, cy - 15, 4.5, col))
    raise ValueError(kind)


def method():
    W, H = 1000, 236
    steps = [("PROBLEM", "listen to the guest", "ear"), ("RESEARCH", "know the menu", "search"),
             ("PROTOTYPE", "first pour", "sketch"), ("BUILD", "shake it", "shaker"),
             ("TEST", "taste it", "taste"), ("ITERATE", "adjust the balance", "iterate"), ("SHIP", "serve it", "serve")]
    d = base_doc(W, H, "How I build: problem, research, prototype, build, test, iterate, ship",
                 "Seven steps drawn as bar service: listen to the guest (problem), know the menu (research), first pour "
                 "(prototype), shake it (build), taste it (test), adjust the balance (iterate), serve it (ship).",
                 radius=18, corners=False)
    n = len(steps)
    x0, x1, cy = 92, W - 92, 92
    xs = [x0 + (x1 - x0) * i / (n - 1) for i in range(n)]
    cycle, travel = 9.0, 6.4
    d.css.append(f"""
.dot{{animation:dot {cycle}s cubic-bezier(.45,.05,.55,.95) infinite}}
@keyframes dot{{0%{{transform:translateX(0);opacity:0}}3%{{opacity:1}}{num(travel / cycle * 100, 2)}%{{transform:translateX({num(x1 - x0)}px);opacity:1}}{num(travel / cycle * 100 + 6, 2)}%,100%{{transform:translateX({num(x1 - x0)}px);opacity:0}}}}
.trail{{animation:trail {cycle}s cubic-bezier(.45,.05,.55,.95) infinite;transform-origin:{x0}px {cy}px}}
@keyframes trail{{0%{{transform:scaleX(0);opacity:1}}{num(travel / cycle * 100, 2)}%{{transform:scaleX(1);opacity:1}}{num(travel / cycle * 100 + 8, 2)}%,100%{{transform:scaleX(1);opacity:0}}}}
""")
    d.add(f'<line x1="{x0}" y1="{cy}" x2="{x1}" y2="{cy}" stroke="#3A3122" stroke-width="2"/>')
    trail = lin_grad(d, "trailg", [(0, "#E6C27A", .15), (1, "#FFD08A", .95)], x1=0, y1=0, x2=1, y2=0)
    d.add(f'<rect class="trail" x="{x0}" y="{cy - 1.5}" width="{x1 - x0}" height="3" rx="1.5" fill="{trail}"/>')
    amber = glow_filter(d, "gA", "#FFA646", radii=(2, 6, 12), strength=.9, core_blur=0)
    d.add(f'<g class="dot"><circle cx="{x0}" cy="{cy}" r="6" fill="#FFE2B0" filter="{amber}"/></g>')
    for i, (name, sub, ic) in enumerate(steps):
        x = xs[i]
        # each station lights when the dot passes (approximate with the same easing: sample by fraction)
        frac = i / (n - 1)
        # invert the ease-in-out cubic-bezier approx: use smoothstep inverse approximation
        t_hit = travel * (0.5 - math.sin(math.asin(1 - 2 * frac) / 3)) if 0 < frac < 1 else travel * frac
        p = t_hit / cycle * 100
        k = f"lit{i}"
        d.css.append(f"@keyframes {k}{{0%,{num(max(0, p - 1), 2)}%{{opacity:0}}{num(p, 2)}%{{opacity:1}}{num(min(99, p + 14), 2)}%{{opacity:.0}}100%{{opacity:0}}}}"
                     f".{k}{{animation:{k} {cycle}s linear infinite}}")
        d.add(f'<circle cx="{num(x)}" cy="{cy}" r="31" fill="#0E0C0A" stroke="#5A4A30" stroke-width="1.5"/>')
        d.add(f'<g class="{k}"><circle cx="{num(x)}" cy="{cy}" r="31" fill="#FFB25E" fill-opacity=".10" stroke="#FFD08A" stroke-width="2" filter="{amber}"/></g>')
        d.add(step_icon(ic, x, cy, P["gold"]))
        nm, _, _ = d.text("deco7", name, x, cy + 62, 13.5, anchor="middle", ls=2.6, fill=P["cream"])
        sb, _, _ = d.text("serifi", sub, x, cy + 84, 14.5, anchor="middle", fill=P["muted"])
        num_, _, _ = d.text("mono", f"0{i + 1}", x, cy - 44, 10.5, anchor="middle", fill=P["gold3"])
        d.add(nm, sb, num_)
    return finish(d, "method.svg")


# =============================================================================== SPECIALS (chalkboard)
def chalk_filter(d, fid, seed=4):
    d.defs.append(
        f'<filter id="{fid}" x="-3%" y="-10%" width="106%" height="120%">'
        f'<feTurbulence type="fractalNoise" baseFrequency=".95" numOctaves="3" seed="{seed}" result="n"/>'
        f'<feDisplacementMap in="SourceGraphic" in2="n" scale="1.7" xChannelSelector="R" yChannelSelector="G" result="r"/>'
        f'<feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  1.9 0 0 0 -.12" result="s"/>'
        f'<feComposite in="r" in2="s" operator="in"/></filter>')
    return f"url(#{fid})"


def specials():
    W, H = 480, 660
    d = base_doc(W, H, "Today's specials — what Carlos is currently learning",
                 "A chalkboard menu. Today's specials, currently learning: Software Architecture, AI Engineering, "
                 "Cloud Infrastructure, Cybersecurity, Product Development.", frame=False, radius=16, bg=False)
    d.css.append("""
.w{animation:w .01s linear both}
@keyframes w{from{opacity:0}to{opacity:1}}
.ul{stroke-dasharray:400;animation:ul 1.2s ease-out both}
@keyframes ul{from{stroke-dashoffset:400}to{stroke-dashoffset:0}}
""")
    wood = lin_grad(d, "wood", [(0, "#6B4424"), (.35, "#4A2E17"), (.7, "#5C3A1D"), (1, "#3A2311")], x1=0, y1=0, x2=1, y2=1)
    d.add(f'<rect width="{W}" height="{H}" rx="16" fill="{wood}"/>')
    d.defs.append('<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".02 .6" numOctaves="3" seed="8"/>'
                  '<feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .35 0"/></filter>')
    d.add(f'<rect width="{W}" height="{H}" rx="16" filter="url(#grain)"/>')
    d.add(f'<rect x="16" y="16" width="{W - 32}" height="{H - 32}" rx="6" fill="#1B2520"/>')
    slate = rad_grad(d, "slate", [(0, "#2A3830", .9), (1, "#101612", 1)], cx=.45, cy=.4, r=.8)
    d.add(f'<rect x="16" y="16" width="{W - 32}" height="{H - 32}" rx="6" fill="{slate}"/>')
    d.defs.append('<filter id="dust" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".8" numOctaves="2" seed="2"/>'
                  '<feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .09 0"/></filter>'
                  '<filter id="smudge"><feGaussianBlur stdDeviation="18"/></filter>')
    d.add(f'<rect x="16" y="16" width="{W - 32}" height="{H - 32}" rx="6" filter="url(#dust)"/>')
    d.add('<g filter="url(#smudge)" fill="#FFFFFF" opacity=".05"><ellipse cx="150" cy="200" rx="120" ry="30"/><ellipse cx="330" cy="430" rx="110" ry="26"/><ellipse cx="260" cy="120" rx="90" ry="18"/></g>')
    d.add(f'<rect x="16.5" y="16.5" width="{W - 33}" height="{H - 33}" rx="6" fill="none" stroke="#000" stroke-opacity=".5" stroke-width="3"/>')
    chalk = chalk_filter(d, "chalk")
    CH = "#F2F0E8"
    t = [0.3]
    body = []

    def write(fk, s, x, y, size, col, anchor="start", cps=0.016):
        t0 = t[0]
        g, w, _ = d.text(fk, s, x, y, size, anchor=anchor, fill=col,
                         glyph_attrs=lambda i, cl, gx: f'class="w" style="animation-delay:{num(t0 + cl * cps, 3)}s"')
        t[0] = t0 + len(s) * cps + .08
        body.append(g)
        return w

    write("chalk", "Today’s Specials", W / 2, 84, 40, CH, anchor="middle", cps=.04)
    body.append(f'<path class="ul" d="M92 100 q60 -6 120 0 t120 -2 t60 4" fill="none" stroke="{CH}" stroke-width="2.6" stroke-linecap="round" opacity=".85" style="animation-delay:{num(t[0])}s"/>')
    write("hand", "— currently learning —", W / 2, 132, 23, "#F2D98A", anchor="middle")
    items = [("Software Architecture", "slow-cooked, served with trade-offs", "#F7B2C4"),
             ("AI Engineering", "LLMs & agents, shaken with evals", "#A8D8F0"),
             ("Cloud Infrastructure", "built to scale, poured on demand", "#F2D98A"),
             ("Cybersecurity", "no secrets in the bundle. ever.", "#B8E6B0"),
             ("Product Development", "from the guest’s table to the roadmap", "#D3B8F0")]
    y = 198
    for name, desc, col in items:
        body.append(sparkle(48, y - 9, 6, col, 'opacity=".9"'))
        write("hand7", name, 64, y, 30, CH)
        write("hand", desc, 64, y + 28, 21.5, col)
        y += 84
    write("hand", "* ask the bartender about the Negroni", 44, H - 44, 18, "#CFC9B8")
    # doodle: little coupe glass
    gx, gy = W - 86, H - 104
    body.append(f'<g fill="none" stroke="{CH}" stroke-width="2.2" stroke-linecap="round" opacity=".8">'
                f'<path d="M{gx - 24} {gy} h48 q-2 22 -24 24 q-22 -2 -24 -24z"/><path d="M{gx} {gy + 24} v22 M{gx - 13} {gy + 46} h26"/>'
                f'<circle cx="{gx + 16}" cy="{gy - 8}" r="7"/><path d="M{gx + 11} {gy - 13} l10 10 M{gx + 9} {gy - 8} h14"/></g>')
    d.add(f'<g filter="{chalk}">' + "".join(body) + "</g>")
    return finish(d, "specials.svg")


# =============================================================================== FOOTER
def bar_wall(d, W, H, glow_cy=.45):
    d.defs.append('<pattern id="brick" width="72" height="30" patternUnits="userSpaceOnUse">'
                  '<rect width="72" height="30" fill="#0E0B09"/>'
                  '<rect x="1" y="1" width="70" height="13" rx="1.5" fill="#15110D"/>'
                  '<rect x="-35" y="16" width="70" height="13" rx="1.5" fill="#15110D"/>'
                  '<rect x="37" y="16" width="70" height="13" rx="1.5" fill="#15110D"/></pattern>')
    d.add(f'<rect width="{W}" height="{H}" rx="18" fill="url(#brick)"/>')
    warm = rad_grad(d, "warm", [(0, "#FF9E4A", .20), (.45, "#FF8A3D", .07), (1, "#000", 0)], cx=.5, cy=glow_cy, r=.62)
    d.add(f'<rect width="{W}" height="{H}" rx="18" fill="{warm}"/>')
    vig = rad_grad(d, "vig", [(0, "#000", 0), (.62, "#000", .25), (1, "#000", .88)], cx=.5, cy=.5, r=.75)
    d.add(f'<rect width="{W}" height="{H}" rx="18" fill="{vig}"/>')


def coupe(cx, cy, s=1.0):
    return (f'M{num(cx - 46 * s)} {num(cy)} H{num(cx + 46 * s)} Q{num(cx + 44 * s)} {num(cy + 38 * s)} {num(cx)} {num(cy + 42 * s)} '
            f'Q{num(cx - 44 * s)} {num(cy + 38 * s)} {num(cx - 46 * s)} {num(cy)} Z M{num(cx)} {num(cy + 42 * s)} V{num(cy + 104 * s)} '
            f'M{num(cx - 30 * s)} {num(cy + 110 * s)} Q{num(cx)} {num(cy + 100 * s)} {num(cx + 30 * s)} {num(cy + 110 * s)}')


def footer():
    W, H = 1200, 330
    d = base_doc(W, H, "Cheers — thanks for stopping by",
                 "Two neon coupe glasses clinking, above the words: thanks for stopping by. Let's build something together.")
    d.body.clear()
    bar_wall(d, W, H, glow_cy=.4)
    d.css.append("""
.gl{animation:gl 5s cubic-bezier(.5,0,.3,1) infinite;transform-box:view-box}
.gr{animation:gr 5s cubic-bezier(.5,0,.3,1) infinite;transform-box:view-box}
@keyframes gl{0%,70%,100%{transform:rotate(0)}25%{transform:rotate(9.6deg)}32%,45%{transform:rotate(8.4deg)}}
@keyframes gr{0%,70%,100%{transform:rotate(0)}25%{transform:rotate(-9.6deg)}32%,45%{transform:rotate(-8.4deg)}}
.burst{animation:burst 5s ease-out infinite;transform-box:fill-box;transform-origin:center}
@keyframes burst{0%,24%{opacity:0;transform:scale(.2)}28%{opacity:1;transform:scale(1)}42%,100%{opacity:0;transform:scale(1.6)}}
.bokeh{animation:float linear infinite both}
@keyframes float{0%{transform:translateY(20px);opacity:0}15%{opacity:var(--o)}85%{opacity:var(--o)}100%{transform:translateY(-120px);opacity:0}}
.on{animation:on 2s linear both}
@keyframes on{0%{opacity:0}10%{opacity:.8}14%{opacity:.1}22%{opacity:1}40%{opacity:.5}46%{opacity:1}100%{opacity:1}}
""")
    rnd = random.Random(3)
    bok = []
    for i in range(12):
        x, y, r = rnd.uniform(60, W - 60), rnd.uniform(120, H - 30), rnd.uniform(2, 6)
        o, dur = rnd.uniform(.12, .32), rnd.uniform(11, 18)
        bok.append(f'<circle class="bokeh" cx="{num(x)}" cy="{num(y)}" r="{num(r)}" fill="#FFC37A" style="--o:{num(o)};animation-duration:{num(dur)}s;animation-delay:{num(-rnd.uniform(0, dur))}s"/>')
    d.defs.append('<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2"/></filter>')
    d.add('<g filter="url(#soft)">' + "".join(bok) + "</g>")
    cyan = glow_filter(d, "gC", P["neon_cyan"], radii=(2.5, 7, 16), strength=.9, core_blur=.3)
    amber = glow_filter(d, "gAm", "#FF9D3C", radii=(2.5, 7, 16), strength=.9, core_blur=.3)
    # pivot points at the base of each stem so the rims meet when tilted
    lx, rx, gy = 540, 660, 60
    L = coupe(lx, gy, .95)
    R = coupe(rx, gy, .95)
    d.add(f'<g class="on"><g class="gl" style="transform-origin:{lx}px {gy + 110}px">'
          f'<path d="{L}" fill="none" stroke="{P["neon_cyan"]}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" filter="{cyan}"/>'
          f'<path d="{L}" fill="none" stroke="#E9FDFF" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
          f'<path d="M{lx - 38} {gy + 12} Q{lx} {gy + 20} {lx + 38} {gy + 12}" fill="none" stroke="{P["neon_cyan"]}" stroke-width="2.4" opacity=".6"/></g>'
          f'<g class="gr" style="transform-origin:{rx}px {gy + 110}px">'
          f'<path d="{R}" fill="none" stroke="#FFB25E" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" filter="{amber}"/>'
          f'<path d="{R}" fill="none" stroke="#FFF3DE" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
          f'<path d="M{rx - 38} {gy + 12} Q{rx} {gy + 20} {rx + 38} {gy + 12}" fill="none" stroke="#FFB25E" stroke-width="2.4" opacity=".6"/></g></g>')
    bx, by = W / 2, gy - 8
    burst = "".join(sparkle(bx + dx, by + dy, r, c) for dx, dy, r, c in
                    ((0, -26, 9, "#FFF3D7"), (-26, -10, 6, "#9FF3FF"), (26, -12, 6, "#FFD08A"), (-14, -38, 4, "#FFFFFF"), (16, -40, 4.5, "#FFFFFF")))
    d.add(f'<g class="burst">{burst}</g>')
    t1, _, _ = d.text("serifi", "Thanks for stopping by the bar.", W / 2, 232, 30, anchor="middle", fill=P["cream"])
    t2, tw, _ = d.text("deco", "LET’S BUILD SOMETHING TOGETHER", W / 2, 272, 14, anchor="middle", ls=5.5, fill="url(#gtext)")
    d.add(t1, t2, deco_rule(W / 2, 294, 70, "#8C6A2F", gap=10, sw=.8))
    return finish(d, "footer.svg")


# =============================================================================== SECTION TITLES / DIVIDER / BUTTONS
TITLES = [
    ("aperitif", "01", "Apéritif", "ABOUT ME"),
    ("signature", "02", "Signature Serves", "FEATURED PROJECTS"),
    ("backbar", "03", "The Back Bar", "TECH STACK"),
    ("method", "04", "The Method", "HOW I BUILD"),
    ("tab", "05", "The Tab & Today’s Specials", "GITHUB STATS · CURRENTLY LEARNING"),
    ("lastcall", "06", "Last Call", "LET’S TALK"),
]


def titles():
    for slug, no, title, sub in TITLES:
        for theme in ("dark", "light"):
            W, H = 1000, 124
            d = Doc(W, H, f"{title} — {sub.title()}", f"Section {no}: {title}. {sub.title()}.")
            main = P["cream"] if theme == "dark" else "#1C1712"
            gold = "#D4AE62" if theme == "dark" else "#8C6A2F"
            muted = "#8C6A2F" if theme == "dark" else "#A88445"
            d.css.append(".rise{animation:rise 1s cubic-bezier(.2,.7,.2,1) both}"
                         "@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}")
            n, _, _ = d.text("deco7", f"Nº {no}", W / 2, 26, 12.5, anchor="middle", ls=4, fill=gold)
            t, tw, _ = d.text("serif", title, W / 2, 80, 44, anchor="middle", fill=main)
            s, sw, _ = d.text("deco", sub, W / 2, 110, 12.5, anchor="middle", ls=5.2, fill=gold)
            half = tw / 2 + 30
            orn = (f'<line x1="{num(W / 2 - half - 120)}" y1="64" x2="{num(W / 2 - half)}" y2="64" stroke="{muted}" stroke-width="1"/>'
                   f'<line x1="{num(W / 2 + half)}" y1="64" x2="{num(W / 2 + half + 120)}" y2="64" stroke="{muted}" stroke-width="1"/>'
                   f'<rect x="{num(W / 2 - half - 4)}" y="60" width="8" height="8" transform="rotate(45 {num(W / 2 - half)} 64)" fill="{gold}"/>'
                   f'<rect x="{num(W / 2 + half - 4)}" y="60" width="8" height="8" transform="rotate(45 {num(W / 2 + half)} 64)" fill="{gold}"/>'
                   f'<circle cx="{num(W / 2 - half - 128)}" cy="64" r="2" fill="{gold}"/><circle cx="{num(W / 2 + half + 128)}" cy="64" r="2" fill="{gold}"/>')
            d.add(f'<g class="rise">{n}{orn}{t}{s}</g>')
            p = os.path.join(OUT, f"title-{slug}-{theme}.svg")
            d.save(p)
            import xml.etree.ElementTree as ET
            ET.parse(p)
    print(f"  title-*.svg                  {len(TITLES) * 2} files")


def divider():
    W, H = 1000, 36
    d = Doc(W, H, "divider", "Art-deco divider")
    c = "#B08A45"
    d.add(f'<line x1="200" y1="18" x2="470" y2="18" stroke="{c}" stroke-opacity=".6"/><line x1="530" y1="18" x2="800" y2="18" stroke="{c}" stroke-opacity=".6"/>'
          f'<rect x="494" y="12" width="12" height="12" transform="rotate(45 500 18)" fill="none" stroke="{c}" stroke-width="1.4"/>'
          f'<rect x="497" y="15" width="6" height="6" transform="rotate(45 500 18)" fill="{c}"/>'
          f'<circle cx="480" cy="18" r="2" fill="{c}"/><circle cx="520" cy="18" r="2" fill="{c}"/>'
          f'<circle cx="192" cy="18" r="1.6" fill="{c}"/><circle cx="808" cy="18" r="1.6" fill="{c}"/>')
    d.save(os.path.join(OUT, "divider.svg"))
    print("  divider.svg")


def button(file, label, kind, W=250):
    H = 62
    d = Doc(W, H, label, f"{label} button")
    d.defs.append(f'<linearGradient id="fg" x1="0" y1="0" x2="1" y2="1">' + "".join(
        f'<stop offset="{o}" stop-color="{c}"/>' for o, c in GOLD_STOPS) + "</linearGradient>")
    d.add(f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="{(H - 2) / 2}" fill="#0B0A09" stroke="url(#fg)" stroke-width="1.6"/>'
          f'<rect x="5.5" y="5.5" width="{W - 11}" height="{H - 11}" rx="{(H - 11) / 2}" fill="none" stroke="#FFFFFF" stroke-opacity=".06"/>')
    ix, iy = 40, H / 2
    if kind == "linkedin":
        d.add(f'<rect x="{ix - 13}" y="{iy - 13}" width="26" height="26" rx="5" fill="#E6C27A"/>')
        t, _, _ = d.text("sans7", "in", ix, iy + 6.5, 17, anchor="middle", fill="#0B0A09", ls=-.3)
        d.add(t)
    elif kind == "email":
        d.add(f'<rect x="{ix - 14}" y="{iy - 10}" width="28" height="20" rx="3" fill="none" stroke="#E6C27A" stroke-width="2"/>'
              f'<path d="M{ix - 13} {iy - 8} l13 10 l13 -10" fill="none" stroke="#E6C27A" stroke-width="2" stroke-linejoin="round"/>')
    t, tw, _ = d.text("sans6", label, ix + 26, iy + 6, 18, fill=P["cream"])
    d.add(t)
    d.add(f'<path d="M{W - 40} {iy} h14 m-5 -5 l5 5 l-5 5" fill="none" stroke="#E6C27A" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>')
    d.save(os.path.join(OUT, file))
    print(f"  {file}")


ASSETS = {"header": header, "terminal": terminal, "card-barops": card_barops, "card-mimo": card_mimo, "card-aura": card_aura, "backbar": backbar, "method": method, "specials": specials, "footer": footer, "titles": titles, "divider": divider, "buttons": lambda: (button("btn-linkedin.svg", "LinkedIn", "linkedin"), button("btn-email.svg", "Email me", "email"))}

if __name__ == "__main__":
    names = sys.argv[1:] or list(ASSETS)
    for n in names:
        ASSETS[n]()
