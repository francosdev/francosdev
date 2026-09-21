"""
svgkit — tiny toolkit to build self-contained, animated SVGs for a GitHub README.

Every piece of text is shaped with HarfBuzz and converted to vector outlines, so the
SVGs render identically on every OS/browser (no web fonts, nothing external to load —
which matters because GitHub serves README images with a strict CSP).
Each glyph is stored once in <defs> and re-used with <use>, which keeps files small.
"""
import io
import os
import re
import json

import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")


def num(v, nd=2):
    """Compact number formatting for SVG attributes."""
    if isinstance(v, int):
        return str(v)
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))



_TOK = re.compile(r"[MLHVQCZmlhvqcz]|-?\d+(?:\.\d+)?")


def _fmt(nums):
    out = ""
    for i, n in enumerate(nums):
        s = str(n)
        if i and not s.startswith("-"):
            out += " "
        out += s
    return out


def compact_path(d):
    """Absolute integer path (from SVGPathPen) -> compact relative path."""
    toks = _TOK.findall(d)
    i = 0
    cx = cy = sx = sy = 0
    out = []
    cmd = None
    arity = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4, "C": 6, "Z": 0}
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz":
                out.append("z")
                cx, cy = sx, sy
                continue
        n = arity[cmd.upper()]
        vals = [int(round(float(v))) for v in toks[i:i + n]]
        i += n
        if cmd == "M":
            rel = [vals[0] - cx, vals[1] - cy]
            out.append("m" + _fmt(rel))
            cx, cy = vals
            sx, sy = cx, cy
            cmd = "L"
        elif cmd == "L":
            out.append("l" + _fmt([vals[0] - cx, vals[1] - cy]))
            cx, cy = vals
        elif cmd == "H":
            out.append("h" + _fmt([vals[0] - cx]))
            cx = vals[0]
        elif cmd == "V":
            out.append("v" + _fmt([vals[0] - cy]))
            cy = vals[0]
        elif cmd == "Q":
            out.append("q" + _fmt([vals[0] - cx, vals[1] - cy, vals[2] - cx, vals[3] - cy]))
            cx, cy = vals[2], vals[3]
        elif cmd == "C":
            out.append("c" + _fmt([vals[0] - cx, vals[1] - cy, vals[2] - cx, vals[3] - cy, vals[4] - cx, vals[5] - cy]))
            cx, cy = vals[4], vals[5]
    # first command must be absolute
    s = "".join(out)
    if s.startswith("m"):
        s = "M" + s[1:]
    return s


# --------------------------------------------------------------------------- fonts
class Font:
    def __init__(self, key, file, variations=None, features=None):
        self.key = key
        path = os.path.join(FONT_DIR, file)
        tt = TTFont(path)
        if "fvar" in tt:
            from fontTools.varLib.instancer import instantiateVariableFont
            axes = {a.axisTag: a.defaultValue for a in tt["fvar"].axes}
            axes.update(variations or {})
            tt = instantiateVariableFont(tt, axes)
        buf = io.BytesIO()
        tt.save(buf)
        data = buf.getvalue()
        self.tt = TTFont(io.BytesIO(data))
        face = hb.Face(data)
        self.hb = hb.Font(face)
        self.upem = face.upem
        self.gs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.features = features or {}
        hhea = self.tt["hhea"]
        os2 = self.tt["OS/2"]
        self.ascender = hhea.ascent
        self.descender = hhea.descent
        self.cap = getattr(os2, "sCapHeight", 0) or int(self.upem * 0.7)
        self.xh = getattr(os2, "sxHeight", 0) or int(self.upem * 0.5)
        self._d = {}
        self.cmap = self.tt.getBestCmap()

    def has(self, ch):
        return ord(ch) in self.cmap

    def glyph_d(self, gid):
        if gid not in self._d:
            pen = SVGPathPen(self.gs, ntos=lambda v: str(int(round(float(v)))))
            self.gs[self.order[gid]].draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
            self._d[gid] = compact_path(pen.getCommands())
        return self._d[gid]

    def shape(self, text, size, ls=0.0, features=None):
        """Returns ([(gid, x_px, y_px, cluster)], advance_px). ls = letter-spacing in px."""
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        feats = dict(self.features)
        feats.update(features or {})
        hb.shape(self.hb, buf, feats)
        s = size / self.upem
        x = 0.0
        out = []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            out.append((info.codepoint, x + pos.x_offset * s, -pos.y_offset * s, info.cluster))
            x += pos.x_advance * s + ls
        if out and ls:
            x -= ls
        return out, x

    def width(self, text, size, ls=0.0, features=None):
        return self.shape(text, size, ls, features)[1]


FONTS = {}


def font(key):
    return FONTS[key]


GOOGLE_FONTS = "https://raw.githubusercontent.com/google/fonts/main/"
FONT_FILES = {
    "Sacramento-Regular.ttf": "ofl/sacramento/Sacramento-Regular.ttf",
    "TiltNeon[XROT,YROT].ttf": "ofl/tiltneon/TiltNeon%5BXROT,YROT%5D.ttf",
    "JosefinSans[wght].ttf": "ofl/josefinsans/JosefinSans%5Bwght%5D.ttf",
    "PlayfairDisplay[wght].ttf": "ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
    "PlayfairDisplay-Italic[wght].ttf": "ofl/playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf",
    "Inter[opsz,wght].ttf": "ofl/inter/Inter%5Bopsz,wght%5D.ttf",
    "JetBrainsMono[wght].ttf": "ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
    "CabinSketch-Bold.ttf": "ofl/cabinsketch/CabinSketch-Bold.ttf",
    "Caveat[wght].ttf": "ofl/caveat/Caveat%5Bwght%5D.ttf",
}


def fetch_fonts():
    """Downloads the (SIL Open Font License) fonts from the Google Fonts repo on first run."""
    import urllib.request
    os.makedirs(FONT_DIR, exist_ok=True)
    for name, rel in FONT_FILES.items():
        path = os.path.join(FONT_DIR, name)
        if not os.path.exists(path):
            print("  fetching font", name)
            urllib.request.urlretrieve(GOOGLE_FONTS + rel, path)


def register_fonts():
    fetch_fonts()
    spec = {
        "neon":   ("Sacramento-Regular.ttf", None),
        "tilt":   ("TiltNeon[XROT,YROT].ttf", None),
        "deco":   ("JosefinSans[wght].ttf", {"wght": 600}),
        "deco7":  ("JosefinSans[wght].ttf", {"wght": 700}),
        "serif":  ("PlayfairDisplay[wght].ttf", {"wght": 700}),
        "serifi": ("PlayfairDisplay-Italic[wght].ttf", {"wght": 500}),
        "sans":   ("Inter[opsz,wght].ttf", {"wght": 400, "opsz": 14}),
        "sans6":  ("Inter[opsz,wght].ttf", {"wght": 600, "opsz": 14}),
        "sans7":  ("Inter[opsz,wght].ttf", {"wght": 700, "opsz": 14}),
        "mono":   ("JetBrainsMono[wght].ttf", {"wght": 400}),
        "mono7":  ("JetBrainsMono[wght].ttf", {"wght": 700}),
        "chalk":  ("CabinSketch-Bold.ttf", None),
        "hand":   ("Caveat[wght].ttf", {"wght": 500}),
        "hand7":  ("Caveat[wght].ttf", {"wght": 700}),
    }
    for k, (f, v) in spec.items():
        if k not in FONTS:
            FONTS[k] = Font(k, f, v)


# --------------------------------------------------------------------------- document
class Doc:
    """Collects glyph defs + css + defs and serialises a standalone SVG."""

    def __init__(self, w, h, title, desc=""):
        self.w, self.h = w, h
        self.title, self.desc = title, desc
        self.used = {}          # (fontkey, gid) -> d
        self.defs = []
        self.css = []
        self.body = []
        self._id = 0

    def uid(self, prefix="i"):
        self._id += 1
        return f"{prefix}{self._id}"

    def add(self, *parts):
        self.body.extend(parts)

    # ---- text -------------------------------------------------------------
    def text(self, fkey, s, x, y, size, anchor="start", ls=0.0, fill=None, cls=None,
             attrs="", glyph_attrs=None, features=None, wrap=True):
        """Render text as outlined glyphs. Returns (svg, width, glyph list [(gx_px, char_index)]).
        glyph_attrs: optional callable(i, cluster, gx) -> extra attribute string per glyph."""
        f = font(fkey)
        glyphs, adv = f.shape(s, size, ls, features)
        if anchor == "middle":
            x0 = x - adv / 2
        elif anchor == "end":
            x0 = x - adv
        else:
            x0 = x
        sc = size / f.upem
        uses = []
        placed = []
        for i, (gid, gx, gy, cl) in enumerate(glyphs):
            d = f.glyph_d(gid)
            placed.append((x0 + gx, cl))
            if not d:
                continue
            self.used[(fkey, gid)] = d
            extra = glyph_attrs(i, cl, x0 + gx) if glyph_attrs else ""
            ux = num(gx / sc, 1)
            uy = num(gy / sc, 1) if gy else None
            uses.append(f'<use href="#{fkey}-{gid}" x="{ux}"' + (f' y="{uy}"' if uy else "") +
                        (f" {extra}" if extra else "") + "/>")
        a = ""
        if fill:
            a += f' fill="{fill}"'
        if cls:
            a += f' class="{cls}"'
        if attrs:
            a += " " + attrs
        g = f'<g transform="translate({num(x0)} {num(y)}) scale({num(sc, 5)})"{a}>' + "".join(uses) + "</g>"
        if not wrap:
            g = "".join(uses)
        return g, adv, placed

    def measure(self, fkey, s, size, ls=0.0):
        return font(fkey).width(s, size, ls)

    # ---- serialise ------------------------------------------------------------
    def svg(self, extra_root_attrs=""):
        glyph_defs = "".join(f'<path id="{k}-{g}" d="{d}"/>' for (k, g), d in sorted(self.used.items()))
        css = "\n".join(self.css)
        reduced = ("@media (prefers-reduced-motion: reduce){*{animation:none!important;"
                   "transition:none!important}}")
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 {num(self.w)} {num(self.h)}" width="{num(self.w)}" height="{num(self.h)}" '
            f'role="img" aria-labelledby="t d" {extra_root_attrs}>',
            f'<title id="t">{esc(self.title)}</title><desc id="d">{esc(self.desc)}</desc>',
            f"<style>{css}\n{reduced}</style>" if css else f"<style>{reduced}</style>",
            "<defs>" + glyph_defs + "".join(self.defs) + "</defs>",
            *self.body,
            "</svg>",
        ]
        out = "\n".join(parts)
        return out

    def save(self, path):
        data = self.svg()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(data)
        return len(data.encode("utf-8"))


# --------------------------------------------------------------------------- icons
_ICONS = None


def icon(name):
    global _ICONS
    if _ICONS is None:
        with open(os.path.join(HERE, "icons.json")) as fh:
            _ICONS = json.load(fh)
    return _ICONS[name]


def icon_svg(name, x, y, size, fill=None, attrs=""):
    """simple-icons are 24x24 paths."""
    ic = icon(name)
    s = size / 24
    col = fill or ("#" + ic["hex"])
    return (f'<path transform="translate({num(x)} {num(y)}) scale({num(s, 4)})" '
            f'd="{ic["path"]}" fill="{col}" {attrs}/>')


# --------------------------------------------------------------------------- palette
P = {
    "ink":      "#0B0A09",   # bar-at-night black
    "ink2":     "#12100D",
    "panel":    "#15120E",
    "line":     "#2A2419",
    "gold":     "#E6C27A",
    "gold2":    "#C9A25A",
    "gold3":    "#8C6A2F",
    "cream":    "#F4ECDC",
    "cream2":   "#CFC5B2",
    "muted":    "#948A78",
    "amber":    "#FFB347",
    "neon_red": "#FF3B4E",
    "neon_cyan": "#3FE4FF",
    "neon_pink": "#FF4FA3",
    "green":    "#6BE39A",
}


def gold_gradient(doc, gid, x1=0, y1=0, x2=0, y2=1, units="objectBoundingBox", shimmer=False, dur=6):
    stops = [
        (0, "#7A5A24"), (0.22, "#C9A25A"), (0.45, "#FFF0C8"), (0.55, "#E6C27A"),
        (0.78, "#A67C36"), (1, "#6E5020"),
    ]
    st = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
    anim = ""
    if shimmer:
        anim = (f'<animateTransform attributeName="gradientTransform" type="translate" '
                f'values="-1 0;1 0;1 0" keyTimes="0;0.6;1" dur="{dur}s" repeatCount="indefinite"/>')
    doc.defs.append(
        f'<linearGradient id="{gid}" gradientUnits="{units}" x1="{num(x1)}" y1="{num(y1)}" '
        f'x2="{num(x2)}" y2="{num(y2)}" spreadMethod="pad">{st}{anim}</linearGradient>')
    return f"url(#{gid})"


def glow_filter(doc, fid, color, radii=(2, 6, 14), strength=1.0, core_blur=0.4):
    """Neon glow: colored halos stacked under a crisp source."""
    blurs = []
    merges = []
    for i, r in enumerate(radii):
        blurs.append(f'<feGaussianBlur in="SourceAlpha" stdDeviation="{r}" result="b{i}"/>'
                     f'<feFlood flood-color="{color}" flood-opacity="{num(min(1, strength * (1.0 - i * 0.18)))}" result="c{i}"/>'
                     f'<feComposite in="c{i}" in2="b{i}" operator="in" result="g{i}"/>')
        merges.append(f'<feMergeNode in="g{i}"/>')
    merges.reverse()
    core = (f'<feGaussianBlur in="SourceGraphic" stdDeviation="{core_blur}" result="core"/>'
            if core_blur else "")
    doc.defs.append(
        f'<filter id="{fid}" x="-30%" y="-60%" width="160%" height="220%" color-interpolation-filters="sRGB">'
        + "".join(blurs) + core + "<feMerge>" + "".join(merges) +
        (f'<feMergeNode in="core"/>' if core_blur else '<feMergeNode in="SourceGraphic"/>') +
        "</feMerge></filter>")
    return f"url(#{fid})"
