"""Build the PartnerReady logo, mark and favicons from one geometric definition.

Development-only tool. It needs packages that are not runtime dependencies:

    python -m pip install fonttools brotli uharfbuzz pillow
    python scripts/build_brand_assets.py

The mark is a "P" whose counter is a document with a folded corner and a check.
Coordinates are in a 337 x 400 design space. The wordmark is converted to vector
outlines from the bundled Inter variable font, so the SVGs render identically
everywhere (including GitHub) without loading a font.
"""

import io
import math
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "static" / "fonts" / "inter-latin-var.woff2"
OUT = ROOT / "static" / "brand"

WINE, ROSE, BURGUNDY, YELLOW, WHITE = "#4C0519", "#E11D48", "#881337", "#FACC15", "#FFFFFF"

# --- Mark geometry (design units) -------------------------------------------
CX, CY = 172.0, 165.0          # centre of the bowl's arcs
R_OUT, R_IN = 155.0, 105.0      # outer and inner bowl radii (stroke 50)
LEFT, STEM_RIGHT, BOTTOM = 10.0, 117.0, 390.0
TOP, BOWL_BOTTOM = CY - R_OUT, CY + R_OUT
INNER_LEFT, INNER_TOP, INNER_BOTTOM = 60.0, CY - R_IN, CY + R_IN
CORNER = 40.0                   # outer top-left radius
PAGE_CORNER = 12.0              # page left corners
NOTCH_X, NOTCH_Y = 200.0, 100.0 # page corner removed for the folded flap
FLAP = [(208.0, 30.0), (208.0, 92.0), (270.0, 92.0)]  # flap; its hypotenuse is the fold
CHECK = [(82.0, 168.0), (141.0, 227.0), (240.0, 128.0)]
CHECK_WIDTH = 44.0
VIEW_W, VIEW_H = 337.0, 400.0


def arc_points(cx, cy, r, a0, a1, steps=48):
    return [
        (cx + r * math.cos(a0 + (a1 - a0) * i / steps), cy + r * math.sin(a0 + (a1 - a0) * i / steps))
        for i in range(steps + 1)
    ]


def outer_polygon():
    pts = [(LEFT, BOTTOM), (LEFT, TOP + CORNER)]
    pts += arc_points(LEFT + CORNER, TOP + CORNER, CORNER, math.pi, 1.5 * math.pi, 12)
    pts += arc_points(CX, CY, R_OUT, -0.5 * math.pi, 0.5 * math.pi)
    pts += [(STEM_RIGHT, BOWL_BOTTOM), (STEM_RIGHT, BOTTOM)]
    return pts


def page_polygon():
    notch_arc_x = CX + math.sqrt(R_IN**2 - (NOTCH_Y - CY) ** 2)
    a_notch = math.atan2(NOTCH_Y - CY, notch_arc_x - CX)
    pts = [(INNER_LEFT + PAGE_CORNER, INNER_TOP), (NOTCH_X, INNER_TOP), (NOTCH_X, NOTCH_Y)]
    pts += arc_points(CX, CY, R_IN, a_notch, 0.5 * math.pi)
    pts += [(INNER_LEFT + PAGE_CORNER, INNER_BOTTOM)]
    pts += arc_points(INNER_LEFT + PAGE_CORNER, INNER_BOTTOM - PAGE_CORNER, PAGE_CORNER, 0.5 * math.pi, math.pi, 8)
    pts += arc_points(INNER_LEFT + PAGE_CORNER, INNER_TOP + PAGE_CORNER, PAGE_CORNER, math.pi, 1.5 * math.pi, 8)
    return pts


def check_polygon(points=CHECK, width=CHECK_WIDTH):
    """Outline of a two-segment stroke with butt caps and a mitred joint."""
    (x0, y0), (x1, y1), (x2, y2) = points
    h = width / 2

    def normal(ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        n = math.hypot(dx, dy)
        return -dy / n * h, dx / n * h

    n1, n2 = normal(x0, y0, x1, y1), normal(x1, y1, x2, y2)

    def intersect(p, d, q, e):
        det = d[0] * e[1] - d[1] * e[0]
        t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / det
        return p[0] + d[0] * t, p[1] + d[1] * t

    d1, d2 = (x1 - x0, y1 - y0), (x2 - x1, y2 - y1)
    a = intersect((x0 + n1[0], y0 + n1[1]), d1, (x1 + n2[0], y1 + n2[1]), d2)
    b = intersect((x0 - n1[0], y0 - n1[1]), d1, (x1 - n2[0], y1 - n2[1]), d2)
    return [
        (x0 + n1[0], y0 + n1[1]), a, (x2 + n2[0], y2 + n2[1]),
        (x2 - n2[0], y2 - n2[1]), b, (x0 - n1[0], y0 - n1[1]),
    ]


def path(points, close=True):
    d = "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in points)
    return d + (" Z" if close else "")


def mark_paths(dx=0.0, dy=0.0, scale=1.0):
    shift = lambda pts: [(dx + x * scale, dy + y * scale) for x, y in pts]  # noqa: E731
    p_shape = " ".join(path(shift(poly)) for poly in (outer_polygon(), page_polygon(), FLAP))
    return p_shape, path(shift(check_polygon()))


def mark_svg(p_color, check_color, background=None, title="PartnerReady"):
    p_shape, check = mark_paths()
    pad = 0.0
    bg = ""
    view = f"0 0 {VIEW_W:.0f} {VIEW_H:.0f}"
    if background:
        size, pad = 512.0, 84.0
        scale = (size - 2 * pad) / VIEW_H
        dx = (size - VIEW_W * scale) / 2
        p_shape, check = mark_paths(dx, pad, scale)
        view = f"0 0 {size:.0f} {size:.0f}"
        bg = f'<rect width="{size:.0f}" height="{size:.0f}" rx="112" fill="{background}"/>'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" role="img" aria-label="{title}">'
        f"<title>{title}</title>{bg}"
        f'<path fill="{p_color}" fill-rule="evenodd" d="{p_shape}"/>'
        f'<path fill="{check_color}" d="{check}"/></svg>\n'
    )


# --- Wordmark ----------------------------------------------------------------
def static_instance(weight):
    font = TTFont(FONT)
    axes = {"wght": weight}
    if "opsz" in [a.axisTag for a in font["fvar"].axes]:
        axes["opsz"] = 28
    inst = instantiateVariableFont(font, axes)
    buf = io.BytesIO()
    inst.flavor = None
    inst.save(buf)
    return inst, buf.getvalue()


def text_path(text, weight, cap_height, x, baseline, tracking=0.0):
    font, data = static_instance(weight)
    upem = font["head"].unitsPerEm
    caps = font["OS/2"].sCapHeight
    scale = cap_height / caps
    face = hb.Face(data)
    hb_font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, {"kern": True, "liga": True})
    glyph_set, order = font.getGlyphSet(), font.getGlyphOrder()
    pen = SVGPathPen(glyph_set)
    cursor = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = order[info.codepoint]
        tx = x + (cursor + pos.x_offset) * scale
        glyph_set[name].draw(TransformPen(pen, (scale, 0, 0, -scale, tx, baseline - pos.y_offset * scale)))
        cursor += pos.x_advance + tracking * upem
    width = (cursor - tracking * upem) * scale
    return pen.getCommands(), width


def logo_svg(p_color, check_color, word_color, tag_color, title):
    p_shape, check = mark_paths()
    gap = 70.0
    word, word_w = text_path("PartnerReady", 800, 150.0, VIEW_W + gap, 255.0, tracking=-0.015)
    # Space the tagline to end before the "y" descender, as in the original lockup.
    _, before_y = text_path("PartnerRead", 800, 150.0, VIEW_W + gap, 255.0, tracking=-0.015)
    tagline, tag_cap, tag_x = "PARTNER DELIVERABLES CHECKER", 36.0, VIEW_W + gap + 4
    _, natural_w = text_path(tagline, 700, tag_cap, tag_x, 330.0)
    font, _ = static_instance(700)
    em = tag_cap / font["OS/2"].sCapHeight * font["head"].unitsPerEm
    tracking = (before_y - 14 - natural_w) / (len(tagline) - 1) / em
    tag, tag_w = text_path(tagline, 700, tag_cap, tag_x, 330.0, tracking=tracking)
    width = VIEW_W + gap + max(word_w, tag_w + 4) + 8
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {VIEW_H:.0f}" role="img" '
        f'aria-label="{title}"><title>{title}</title>'
        f'<path fill="{p_color}" fill-rule="evenodd" d="{p_shape}"/>'
        f'<path fill="{check_color}" d="{check}"/>'
        f'<path fill="{word_color}" d="{word}"/><path fill="{tag_color}" d="{tag}"/></svg>\n'
    )


# --- Raster favicons -------------------------------------------------------------
def raster_icon(size, background=ROSE, p_color=WHITE, check_color=YELLOW, radius=0.22, pad=0.165):
    s = 8  # supersample, then downscale for smooth edges
    big = size * s
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=int(big * radius), fill=background)
    scale = (big - 2 * big * pad) / VIEW_H
    dx, dy = (big - VIEW_W * scale) / 2, big * pad
    tf = lambda pts: [(dx + x * scale, dy + y * scale) for x, y in pts]  # noqa: E731
    draw.polygon(tf(outer_polygon()), fill=p_color)
    draw.polygon(tf(page_polygon()), fill=background)
    draw.polygon(tf(FLAP), fill=background)
    draw.polygon(tf(check_polygon()), fill=check_color)
    return img.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    full = "PartnerReady, partner deliverables checker"
    files = {
        "partnerready-mark.svg": mark_svg(WINE, ROSE),
        "partnerready-mark-white.svg": mark_svg(WHITE, YELLOW),
        "partnerready-mark-mono.svg": mark_svg("currentColor", "currentColor"),
        "favicon.svg": mark_svg(WHITE, YELLOW, background=ROSE),
        "partnerready-logo.svg": logo_svg(WINE, ROSE, WINE, BURGUNDY, full),
        "partnerready-logo-white.svg": logo_svg(WHITE, YELLOW, WHITE, WHITE, full),
        "partnerready-logo-mono.svg": logo_svg(*["currentColor"] * 4, full),
    }
    for name, svg in files.items():
        (OUT / name).write_text(svg, encoding="utf-8", newline="\n")
    for size, name in ((32, "favicon-32.png"), (180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")):
        raster_icon(size).save(OUT / name, optimize=True)
    print("\n".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
