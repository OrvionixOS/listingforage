"""
Etsy listing image RENDERER.

The engine already plans the 10-image set (roles, copy overlays, layouts). This
module turns that plan into actual finished 2000x2000 PNG files by compositing
the seller's real uploaded product images onto branded, conversion-focused
layouts — hero, showcase grid, feature breakdown, close-up, device mockup,
file-info card, value/comparison card, brand card, how-it-works, final CTA.

No external image model needed: it uses the seller's genuine product images
(so the gallery is honest) plus their brand palette and the AI's per-image
copy overlays. Deterministic, key-free, runs anywhere Pillow runs.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import get_settings

log = logging.getLogger("listingforge.images")
settings = get_settings()

SIZE = 2000
PAD = 140

FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/liberation",
]
_BOLD = ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"]
_REG = ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"]
_SERIF = ["DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf"]


def _font(names: list[str], size: int) -> ImageFont.FreeTypeFont:
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def font_bold(size): return _font(_BOLD, size)
def font_reg(size): return _font(_REG, size)
def font_serif(size): return _font(_SERIF, size)


# --- palette -----------------------------------------------------------------

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = (h or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except (ValueError, IndexError):
        return (40, 40, 44)


def _luminance(c: tuple[int, int, int]) -> float:
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


class Palette:
    def __init__(self, hexes: list[str]):
        cols = [_hex_to_rgb(h) for h in hexes if h] or [(38, 38, 44)]
        cols_sorted = sorted(cols, key=_luminance)
        self.dark = cols_sorted[0]
        self.light = cols_sorted[-1]
        # accent = most saturated / mid-tone
        self.accent = max(cols, key=lambda c: (max(c) - min(c)))
        self.mid = cols_sorted[len(cols_sorted) // 2]

    def on(self, bg: tuple[int, int, int]) -> tuple[int, int, int]:
        return (250, 249, 246) if _luminance(bg) < 140 else (28, 27, 30)


def _brand_palette(result: dict) -> Palette:
    colors = [(c or {}).get("hex") for c in ((result.get("brand") or {}).get("colors") or [])]
    return Palette([c for c in colors if c])


# --- primitives --------------------------------------------------------------

def _canvas(color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", (SIZE, SIZE), color)


def _soft_bg(pal: Palette, dark: bool = False) -> Image.Image:
    """Vertical gradient wash between two palette tones."""
    top = pal.dark if dark else pal.light
    bot = tuple(int(t * 0.86 + m * 0.14) for t, m in zip(top, pal.mid))
    img = Image.new("RGB", (SIZE, SIZE), top)
    d = ImageDraw.Draw(img)
    for y in range(SIZE):
        t = y / SIZE
        col = tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3))
        d.line([(0, y), (SIZE, y)], fill=col)
    return img


def _load(path: str) -> Image.Image | None:
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def _fit(img: Image.Image, box_w: int, box_h: int) -> Image.Image:
    im = img.copy()
    im.thumbnail((box_w, box_h), Image.LANCZOS)
    return im


def _rounded_shadow(base: Image.Image, im: Image.Image, x: int, y: int, radius: int = 28):
    """Paste im at (x,y) with a rounded mask and a soft drop shadow."""
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w, h], radius=radius, fill=255)
    # shadow
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle([x + 10, y + 18, x + w + 10, y + h + 18], radius=radius, fill=(0, 0, 0, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(26))
    base.paste(Image.new("RGB", base.size, (0, 0, 0)), (0, 0), sh)
    base.paste(im, (x, y), mask)


def _wrap(draw, text, font, max_w) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _text_block(draw, text, font, x, y, max_w, fill, line_gap=14, center=False, max_lines=None):
    lines = _wrap(draw, text, font, max_w)
    if max_lines:
        lines = lines[:max_lines]
    asc, desc = font.getmetrics()
    lh = asc + desc + line_gap
    for i, ln in enumerate(lines):
        lx = x + (max_w - draw.textlength(ln, font=font)) / 2 if center else x
        draw.text((lx, y + i * lh), ln, font=font, fill=fill)
    return y + len(lines) * lh


def _pill(draw, x, y, text, font, fg, bg, pad_x=34, pad_y=18):
    w = draw.textlength(text, font=font)
    asc, desc = font.getmetrics()
    h = asc + desc
    draw.rounded_rectangle([x, y, x + w + pad_x * 2, y + h + pad_y * 2], radius=(h + pad_y * 2) // 2, fill=bg)
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=fg)
    return x + w + pad_x * 2


def _badge_number(draw, n: int, pal: Palette, x=PAD, y=PAD):
    r = 46
    draw.ellipse([x, y, x + r * 2, y + r * 2], fill=pal.accent)
    f = font_bold(46)
    tw = draw.textlength(str(n), font=f)
    asc, desc = f.getmetrics()
    draw.text((x + r - tw / 2, y + r - (asc + desc) / 2), str(n), font=f, fill=pal.on(pal.accent))


# --- per-role layouts --------------------------------------------------------
# Each takes (brief dict, product images, palette) → PIL Image.

def _overlay_text(brief: dict) -> str:
    return (brief.get("copyOverlay") or brief.get("title") or "").strip()


def render_hero(brief, imgs, pal):
    # dark, premium hero so the product and title both pop
    top = pal.dark
    bot = tuple(int(t * 0.7 + m * 0.3) for t, m in zip(top, pal.mid))
    img = Image.new("RGB", (SIZE, SIZE), top)
    dd = ImageDraw.Draw(img)
    for y in range(SIZE):
        t = y / SIZE
        dd.line([(0, y), (SIZE, y)], fill=tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3)))
    d = ImageDraw.Draw(img)
    hero = imgs[0] if imgs else None
    if hero:
        fitted = _fit(hero, SIZE - PAD * 2, int(SIZE * 0.62))
        x = (SIZE - fitted.width) // 2
        _rounded_shadow(img, fitted, x, int(SIZE * 0.11), radius=40)
    overlay = _overlay_text(brief)
    if overlay:
        _text_block(d, overlay, font_serif(100), PAD, int(SIZE * 0.80),
                    SIZE - PAD * 2, pal.on(top), center=True, max_lines=2)
    return img


def render_grid(brief, imgs, pal, title_default="Everything included"):
    img = _soft_bg(pal)
    d = ImageDraw.Draw(img)
    title = _overlay_text(brief) or title_default
    _text_block(d, title, font_bold(76), PAD, PAD, SIZE - PAD * 2, pal.on(pal.light), center=True, max_lines=2)
    grid = imgs[:9] if len(imgs) >= 4 else imgs
    n = len(grid)
    cols = 1 if n <= 1 else (2 if n <= 4 else 3)
    rows = max(1, (n + cols - 1) // cols)
    top = int(SIZE * 0.24)
    avail_h = SIZE - top - PAD
    cell_w = (SIZE - PAD * 2 - (cols - 1) * 40) // cols
    cell_h = (avail_h - (rows - 1) * 40) // rows
    for i, im in enumerate(grid):
        r, c = divmod(i, cols)
        fitted = _fit(im, cell_w, cell_h)
        cx = PAD + c * (cell_w + 40) + (cell_w - fitted.width) // 2
        cy = top + r * (cell_h + 40) + (cell_h - fitted.height) // 2
        _rounded_shadow(img, fitted, cx, cy, radius=24)
    return img


def render_feature_card(brief, imgs, pal, dark=True):
    bg = pal.dark if dark else pal.light
    img = _canvas(bg)
    d = ImageDraw.Draw(img)
    fg = pal.on(bg)
    if imgs:
        fitted = _fit(imgs[0], int(SIZE * 0.46), SIZE - PAD * 2)
        _rounded_shadow(img, fitted, PAD, (SIZE - fitted.height) // 2, radius=30)
        tx = PAD + int(SIZE * 0.46) + 90
    else:
        tx = PAD
    tw = SIZE - tx - PAD
    y = int(SIZE * 0.16)
    _pill(d, tx, y, (brief.get("purpose") or "Features").upper()[:22], font_bold(34),
          pal.on(pal.accent), pal.accent)
    y += 130
    title = _overlay_text(brief) or "Key features"
    y = _text_block(d, title, font_bold(72), tx, y, tw, fg, max_lines=3)
    y += 30
    body = brief.get("designDirection") or brief.get("mockup") or ""
    if body:
        _text_block(d, body, font_reg(40), tx, y, tw, tuple(int(c * 0.5 + fg[i] * 0.5) for i, c in enumerate(bg)), max_lines=6)
    return img


def render_closeup(brief, imgs, pal):
    img = _canvas(pal.dark)
    d = ImageDraw.Draw(img)
    if imgs:
        src = imgs[-1] if len(imgs) > 1 else imgs[0]
        # zoom crop: center 55%
        w, h = src.size
        cw, ch = int(w * 0.55), int(h * 0.55)
        crop = src.crop(((w - cw) // 2, (h - ch) // 2, (w + cw) // 2, (h + ch) // 2))
        fitted = _fit(crop, SIZE - PAD * 2, int(SIZE * 0.66))
        x = (SIZE - fitted.width) // 2
        _rounded_shadow(img, fitted, x, int(SIZE * 0.10), radius=32)
    fg = pal.on(pal.dark)
    _pill(d, PAD, int(SIZE * 0.80), "PREMIUM QUALITY DETAIL", font_bold(38), pal.on(pal.accent), pal.accent)
    ov = _overlay_text(brief)
    if ov:
        _text_block(d, ov, font_reg(46), PAD, int(SIZE * 0.80) + 120, SIZE - PAD * 2, fg, max_lines=2)
    return img


def render_mockup(brief, imgs, pal):
    """Device/lifestyle frame: product image inside a rounded 'screen'."""
    img = _soft_bg(pal, dark=True)
    d = ImageDraw.Draw(img)
    if imgs:
        frame_w, frame_h = int(SIZE * 0.68), int(SIZE * 0.5)
        fx, fy = (SIZE - frame_w) // 2, int(SIZE * 0.16)
        d.rounded_rectangle([fx - 26, fy - 26, fx + frame_w + 26, fy + frame_h + 26],
                            radius=60, fill=(20, 20, 24))
        inner = _fit(imgs[0], frame_w, frame_h)
        ix = fx + (frame_w - inner.width) // 2
        iy = fy + (frame_h - inner.height) // 2
        m = Image.new("L", inner.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, inner.width, inner.height], radius=24, fill=255)
        img.paste(inner, (ix, iy), m)
    fg = pal.on(pal.dark)
    ov = _overlay_text(brief) or "See it in action"
    _text_block(d, ov, font_serif(78), PAD, int(SIZE * 0.76), SIZE - PAD * 2, fg, center=True, max_lines=2)
    return img


def render_info_card(brief, imgs, pal, heading="What you receive"):
    img = _soft_bg(pal)
    d = ImageDraw.Draw(img)
    fg = pal.on(pal.light)
    _badge_number(d, brief.get("n", 0), pal)
    y = int(SIZE * 0.14)
    y = _text_block(d, _overlay_text(brief) or heading, font_bold(84), PAD, y, SIZE - PAD * 2, fg, max_lines=2)
    y += 60
    # bullet lines from designDirection / layout / mockup
    raw = " ".join(filter(None, [brief.get("layout"), brief.get("designDirection"), brief.get("mockup")]))
    points = [p.strip() for p in raw.replace("•", ".").split(".") if len(p.strip()) > 6][:5]
    if not points:
        points = ["Instant digital download", "High-resolution files", "Ready to use"]
    bf = font_reg(48)
    for p in points:
        d.ellipse([PAD, y + 18, PAD + 24, y + 42], fill=pal.accent)
        y = _text_block(d, p, bf, PAD + 60, y, SIZE - PAD * 2 - 60, fg, max_lines=2) + 26
    return img


def render_cta(brief, imgs, pal):
    img = _canvas(pal.accent)
    d = ImageDraw.Draw(img)
    fg = pal.on(pal.accent)
    if imgs:
        fitted = _fit(imgs[0], int(SIZE * 0.5), int(SIZE * 0.42))
        x = (SIZE - fitted.width) // 2
        _rounded_shadow(img, fitted, x, int(SIZE * 0.12), radius=36)
    y = int(SIZE * 0.62)
    headline = _overlay_text(brief) or "Get yours today"
    y = _text_block(d, headline, font_serif(104), PAD, y, SIZE - PAD * 2, fg, center=True, max_lines=2)
    y += 40
    cta = (brief.get("cta") or "Instant download • Ready in minutes").strip()
    bx = (SIZE - (d.textlength(cta, font=font_bold(46)) + 120)) / 2
    _pill(d, int(bx), y, cta, font_bold(46), pal.on(pal.dark), pal.dark, pad_x=60, pad_y=28)
    return img


# role (by slot number) → renderer
def _render_one(n: int, brief: dict, imgs, pal) -> Image.Image:
    try:
        if n == 1:
            return render_hero(brief, imgs, pal)
        if n == 2:
            return render_grid(brief, imgs, pal, "Everything included")
        if n == 3:
            return render_feature_card(brief, imgs, pal, dark=True)
        if n == 4:
            return render_closeup(brief, imgs, pal)
        if n == 5:
            return render_mockup(brief, imgs, pal)
        if n == 6:
            return render_info_card(brief, imgs, pal, "What you receive")
        if n == 7:
            return render_grid(brief, imgs, pal, "Incredible value")
        if n == 8:
            return render_feature_card(brief, imgs, pal, dark=False)
        if n == 9:
            return render_info_card(brief, imgs, pal, "How it works")
        return render_cta(brief, imgs, pal)
    except Exception:
        log.exception("image render failed for slot %s; using fallback", n)
        return render_info_card(brief, imgs, pal)


def render_gallery(result: dict, product_image_paths: list[str], out_dir: str) -> list[dict]:
    """Render all 10 listing images to out_dir. Returns per-image metadata."""
    pal = _brand_palette(result)
    imgs = [im for im in (_load(p) for p in product_image_paths) if im is not None]
    briefs = sorted((result.get("images") or []), key=lambda b: b.get("n", 0))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    meta = []
    for brief in briefs:
        n = int(brief.get("n", len(meta) + 1))
        canvas = _render_one(n, brief, imgs, pal)
        fname = f"image_{n:02d}.png"
        canvas.save(out / fname, "PNG")
        meta.append({
            "n": n,
            "title": brief.get("title", f"Image {n}"),
            "purpose": brief.get("purpose", ""),
            "file": fname,
            "url": None,  # filled in by the route with the served path
        })
    return meta
