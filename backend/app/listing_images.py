"""
Etsy listing image RENDERER — style-adaptive premium galleries.

Turns the AI's 10-image plan into finished 2000x2000 PNGs by compositing the
seller's REAL product images onto branded layouts. The AESTHETIC ADAPTS to
each product: a Theme is derived from the brand palette colors AND the
product's style (Luxury, Minimal, Boho, Y2K, Modern, …), so a luxury metallic
pack gets glitter-bokeh + gold frames while a minimalist planner gets clean
solids + thin lines. No two products look the same unless they share a look.

Free, deterministic, key-free (Pillow only) — always renders, always uses the
seller's genuine designs. An optional AI-backdrop layer can be enabled in
production (LF_AI_BACKDROPS) for photographic slots; it falls back to the
procedural backdrop on any failure.
"""
from __future__ import annotations

import logging
import math
import os
import random
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import get_settings

log = logging.getLogger("listingforge.images")
settings = get_settings()


# --- optional AI photographic backdrop (free Pollinations, prod-only) ---------
# Blocked on restricted networks; enabled with LF_AI_BACKDROPS=1 where allowed.
# Any failure silently falls back to the procedural backdrop, so behavior is
# identical where the network can't reach it (dev/sandbox).

def _ai_backdrop(prompt: str, seed: int) -> Image.Image | None:
    if os.getenv("LF_AI_BACKDROPS", "").lower() not in ("1", "true", "yes"):
        return None
    try:
        import httpx
        url = ("https://image.pollinations.ai/prompt/"
               + quote(prompt[:300])
               + f"?width=1024&height=1024&nologo=true&model=flux&seed={seed % 100000}")
        r = httpx.get(url, timeout=45)
        if r.status_code == 200 and r.content[:3] in (b"\xff\xd8\xff", b"\x89PN"):
            return Image.open(BytesIO(r.content)).convert("RGB").resize((SIZE, SIZE))
    except Exception:
        log.info("AI backdrop unavailable; using procedural", exc_info=True)
    return None

SIZE = 2000
PAD = 150

FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation"]
_SANS_BOLD = ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"]
_SANS = ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"]
_SERIF = ["DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf"]


def _ft(names, size):
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


# --- color utils -------------------------------------------------------------

def _hex_to_rgb(h):
    h = (h or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except (ValueError, IndexError):
        return (60, 60, 66)


def _lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _sat(c):
    return max(c) - min(c)


def _mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def _shade(c, f):
    if f < 1:
        return tuple(int(x * f) for x in c)
    return tuple(min(255, int(x + (255 - x) * (f - 1))) for x in c)


# --- Theme: the adaptive style system ----------------------------------------

STYLE_BUCKETS = {
    "luxe": {"luxury", "elegant", "glam", "premium", "editorial", "vintage"},
    "minimal": {"minimal", "modern", "scandinavian", "clean", "professional", "corporate"},
    "soft": {"boho", "watercolor", "rustic", "romantic", "cottagecore", "pastel", "floral"},
    "bold": {"y2k", "trendy", "playful", "retro", "bold", "kids", "fun", "vibrant", "pop"},
}


def _bucket_for(style: str, pal_accent) -> str:
    s = (style or "").lower()
    for bucket, words in STYLE_BUCKETS.items():
        if any(w in s for w in words):
            return bucket
    # infer from palette: very saturated warm gold → luxe; low sat → minimal
    if _sat(pal_accent) < 45:
        return "minimal"
    if pal_accent[0] > 150 and pal_accent[2] < 130 and _sat(pal_accent) > 60:
        return "luxe"
    return "soft"


class Theme:
    """All style decisions for one listing, derived from palette + product style."""

    def __init__(self, hexes: list[str], style: str):
        cols = [_hex_to_rgb(h) for h in hexes if h]
        if not cols:
            cols = [(198, 160, 92), (26, 24, 28), (244, 240, 232)]
        srt = sorted(cols, key=_lum)
        self.dark = srt[0]
        self.light = srt[-1]
        self.mid = srt[len(srt) // 2]
        warm = [c for c in cols if _sat(c) > 28]
        self.accent = max(warm, key=_sat) if warm else self.mid
        self.accent_light = _shade(self.accent, 1.35)
        self.accent_dark = _shade(self.accent, 0.6)
        self.bucket = _bucket_for(style, self.accent)
        self.serif = self.bucket in ("luxe", "soft")
        # whether the accent should render as a metallic gradient (luxe) or flat
        self.metallic = self.bucket == "luxe"
        # luxe/bold read best on dramatic dark grounds; minimal/soft on airy light
        self.prefer_dark = self.bucket in ("luxe", "bold")
        # ensure a light and a dark ground exist even from a monochrome palette
        if _lum(self.light) < 180:
            self.light = _shade(self.light, 1.0 + (200 - _lum(self.light)) / 160)
            self.light = _mix(self.light, (247, 245, 240), 0.55)
        if _lum(self.dark) > 90:
            self.dark = _shade(self.dark, 0.45)
        self.bg_base = self.dark if self.prefer_dark else self.light

    def title_color(self, bg=None):
        """A title color guaranteed to read against the given ground."""
        bg = bg if bg is not None else self.bg_base
        if abs(_lum(self.accent) - _lum(bg)) > 78 and _sat(self.accent) > 24:
            return self.accent
        return (247, 243, 236) if _lum(bg) < 130 else (30, 28, 32)

    # fonts
    def head(self, size):
        return _ft(_SERIF if self.serif else _SANS_BOLD, size)

    def body(self, size):
        return _ft(_SANS, size)

    def upper_titles(self):
        return self.bucket in ("luxe", "bold")

    def text_on(self, bg):
        return (250, 247, 240) if _lum(bg) < 140 else (28, 26, 30)

    # backdrops ---------------------------------------------------------------
    def backdrop(self, rng, dark=None):
        if dark is None:
            dark = self.prefer_dark
        base = self.dark if dark else self.light
        if self.bucket == "luxe":
            return self._bokeh(rng, base)
        if self.bucket == "minimal":
            return self._clean(base, dark)
        if self.bucket == "soft":
            return self._wash(rng, base, dark)
        return self._blocks(rng, base, dark)  # bold

    def _clean(self, base, dark):
        # near-flat with a whisper of vertical gradient
        top = base
        bot = _mix(base, self.mid, 0.12)
        img = Image.new("RGB", (SIZE, SIZE), top)
        d = ImageDraw.Draw(img)
        for y in range(SIZE):
            d.line([(0, y), (SIZE, y)], fill=_mix(top, bot, y / SIZE))
        return img

    def _wash(self, rng, base, dark):
        # soft diagonal watercolor-ish blend of palette tones
        img = Image.new("RGB", (SIZE, SIZE), base)
        ov = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        tones = [self.light, self.mid, self.accent_light, base]
        for _ in range(14):
            r = rng.randint(500, 1200)
            x, y = rng.randint(-200, SIZE), rng.randint(-200, SIZE)
            t = rng.choice(tones)
            od.ellipse([x - r, y - r, x + r, y + r], fill=(t[0], t[1], t[2], 60))
        ov = ov.filter(ImageFilter.GaussianBlur(180))
        return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

    def _blocks(self, rng, base, dark):
        # bright color-block background
        img = Image.new("RGB", (SIZE, SIZE), _mix(base, self.accent, 0.15 if dark else 0.08))
        d = ImageDraw.Draw(img)
        for _ in range(5):
            x, y = rng.randint(0, SIZE), rng.randint(0, SIZE)
            r = rng.randint(200, 600)
            t = rng.choice([self.accent, self.accent_light, self.mid])
            d.ellipse([x - r, y - r, x + r, y + r], fill=t)
        return img.filter(ImageFilter.GaussianBlur(4))

    def _bokeh(self, rng, base):
        img = Image.new("RGB", (SIZE, SIZE), base)
        arr = img.load()
        cx, cy = rng.choice([(SIZE, 0), (0, 0), (SIZE, SIZE)])
        glow = self.accent_light
        for y in range(SIZE):
            for x in range(0, SIZE, 4):
                t = max(0.0, 1.0 - math.hypot(x - cx, y - cy) / (SIZE * 1.25))
                t = t * t * 0.5
                col = _mix(base, glow, t)
                for xx in range(x, min(x + 4, SIZE)):
                    arr[xx, y] = col
        ov = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        for _ in range(90):
            r = rng.randint(10, 130)
            x, y = rng.randint(-40, SIZE), rng.randint(-40, SIZE)
            tone = rng.choice([self.accent, glow, self.light])
            od.ellipse([x - r, y - r, x + r, y + r], fill=(tone[0], tone[1], tone[2], rng.randint(20, 90)))
        ov = ov.filter(ImageFilter.GaussianBlur(6))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        d = ImageDraw.Draw(img)
        for _ in range(1300):
            x, y = rng.randint(0, SIZE), rng.randint(0, SIZE)
            s = rng.randint(1, 4)
            b = rng.randint(160, 255)
            hi = _shade(self.accent_light, 1.2)
            d.ellipse([x, y, x + s, y + s], fill=_mix((b, b, b), hi, 0.5))
        return img

    # accent fill (metallic gradient for luxe, flat elsewhere) ----------------
    def accent_tile(self, w, h):
        img = Image.new("RGB", (max(w, 1), max(h, 1)), self.accent)
        if not self.metallic:
            return img
        d = ImageDraw.Draw(img)
        stops = [(0.0, self.accent_dark), (0.32, self.accent_light), (0.5, self.accent),
                 (0.7, self.accent_light), (1.0, self.accent_dark)]
        for y in range(h):
            t = y / max(h - 1, 1)
            c = self.accent
            for i in range(len(stops) - 1):
                a, ca = stops[i]
                b, cb = stops[i + 1]
                if a <= t <= b:
                    c = _mix(ca, cb, (t - a) / max(b - a, 1e-6))
                    break
            d.line([(0, y), (w, y)], fill=c)
        return img

    def frames(self):
        # (enabled, thickness, double, radius) per bucket
        return {"luxe": (True, 14, True, 10), "minimal": (True, 4, False, 6),
                "soft": (False, 0, False, 24), "bold": (True, 18, False, 30)}[self.bucket]


# --- primitives (theme-aware) ------------------------------------------------

def _load(path):
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def _cover(img, w, h):
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    im = img.resize((int(iw * scale) + 1, int(ih * scale) + 1), Image.LANCZOS)
    x = (im.width - w) // 2
    y = (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def _round_mask(w, h, radius):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    return m


def _card(base, theme, img, box, radius=26, shadow=True, framed=True):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if shadow:
        sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([x0 + 8, y0 + 16, x1 + 8, y1 + 16], radius=radius, fill=(0, 0, 0, 85))
        sh = sh.filter(ImageFilter.GaussianBlur(20))
        base.paste(Image.alpha_composite(base.convert("RGBA"), sh).convert("RGB"), (0, 0))
    base.paste(_cover(img, w, h), (x0, y0), _round_mask(w, h, radius))
    if framed:
        enabled, thick, double, _r = theme.frames()
        if enabled:
            if theme.metallic:
                tile = theme.accent_tile(w, h)
                mask = Image.new("L", (w, h), 0)
                ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, outline=255, width=thick)
                base.paste(tile, (x0, y0), mask)
            else:
                ImageDraw.Draw(base).rounded_rectangle([x0, y0, x1 - 1, y1 - 1], radius=radius,
                                                       outline=theme.accent, width=thick)


def _panel(base, box, fill, radius=14, alpha=205):
    ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle(box, radius=radius, fill=(fill[0], fill[1], fill[2], alpha))
    base.paste(Image.alpha_composite(base.convert("RGBA"), ov).convert("RGB"), (0, 0))


def _accent_frame(base, theme, box, thickness=12, radius=6, inner_gap=20):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    tile = theme.accent_tile(w, h)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius + 8, outline=255, width=thickness)
    if theme.bucket == "luxe":
        md.rounded_rectangle([inner_gap, inner_gap, w - 1 - inner_gap, h - 1 - inner_gap],
                             radius=radius, outline=255, width=max(4, thickness // 3))
    base.paste(tile, (x0, y0), mask)


def _accent_text(base, theme, text, font, x, y, center_w=None):
    d = ImageDraw.Draw(base)
    tw = d.textlength(text, font=font)
    asc, desc = font.getmetrics()
    th = asc + desc
    if center_w is not None:
        x = x + (center_w - tw) / 2
    tile = theme.accent_tile(int(tw) + 4, th + 4)
    mask = Image.new("L", (int(tw) + 4, th + 4), 0)
    ImageDraw.Draw(mask).text((0, 0), text, font=font, fill=255)
    base.paste(tile, (int(x), int(y)), mask)
    return th


def _head_text(base, theme, text, font, x, y, bg=None):
    """Left-aligned heading word/line: metallic for luxe, contrast-safe solid otherwise."""
    if theme.metallic:
        return _accent_text(base, theme, text, font, x, y)
    ImageDraw.Draw(base).text((x, y), text, font=font, fill=theme.title_color(bg))
    asc, desc = font.getmetrics()
    return asc + desc


def _wrap(d, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if d.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _title(base, theme, text, font, y, max_w, max_lines=2, bg=None):
    """Centered heading. Metallic gradient for luxe; contrast-safe solid otherwise."""
    d = ImageDraw.Draw(base)
    if theme.upper_titles():
        text = text.upper()
    lines = _wrap(d, text, font, max_w)[:max_lines]
    asc, desc = font.getmetrics()
    lh = asc + desc + 18
    col = theme.title_color(bg)
    for i, ln in enumerate(lines):
        if theme.metallic:
            _accent_text(base, theme, ln, font, PAD, y + i * lh, center_w=SIZE - PAD * 2)
        else:
            tw = d.textlength(ln, font=font)
            d.text(((SIZE - tw) / 2, y + i * lh), ln, font=font, fill=col)
    return y + len(lines) * lh


def _center(base, text, font, y, fill, max_w=SIZE - PAD * 2, max_lines=2):
    d = ImageDraw.Draw(base)
    lines = _wrap(d, text, font, max_w)[:max_lines]
    asc, desc = font.getmetrics()
    lh = asc + desc + 16
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=font)
        d.text(((SIZE - tw) / 2, y + i * lh), ln, font=font, fill=fill)
    return y + len(lines) * lh


def _seed(*p):
    return random.Random("|".join(str(x) for x in p))


def _overlay(b):
    return (b.get("copyOverlay") or b.get("title") or "").strip()


_SWATCH_NAMES = ["Auric Drift", "Gilded Mist", "Baroque Glow", "Luxe Bloom", "Solar Veil",
                 "Ethereal Dust", "Molten Petal", "Copper Haze", "Golden Mirage", "Celestial",
                 "Silken Ember", "Amour Light", "Champagne", "Veins of Venus", "Rose Aura"]


# --- layouts (all theme-driven) ----------------------------------------------

def render_hero(b, imgs, theme, rng):
    img = theme.backdrop(rng)
    if imgs:
        cw = int(SIZE * 0.62)
        x = (SIZE - cw) // 2
        _card(img, theme, imgs[0], (x, int(SIZE * 0.09), x + cw, int(SIZE * 0.09) + cw), radius=30)
    _title(img, theme, _overlay(b) or "Digital Collection", theme.head(104), int(SIZE * 0.80),
           SIZE - PAD * 2)
    return img


def render_swatch_grid(b, imgs, theme, rng, left="SWATCH", right="DISPLAY"):
    img = theme.backdrop(rng)
    d = ImageDraw.Draw(img)
    pool = imgs or []
    n = min(8, max(len(pool), 4)) if pool else 8
    cols = 4 if n >= 4 else n
    rows = math.ceil(n / cols)
    gx0, gx1, top, bottom = 190, SIZE - 190, 300, SIZE - 120
    cw = (gx1 - gx0 - (cols - 1) * 34) // cols
    ch = (bottom - top - (rows - 1) * 44) // rows
    for i in range(n):
        r, c = divmod(i, cols)
        x0 = gx0 + c * (cw + 34)
        y0 = top + r * (ch + 44)
        if pool:
            _card(img, theme, pool[i % len(pool)], (x0, y0, x0 + cw, y0 + ch), radius=18)
        if theme.bucket in ("luxe", "bold"):  # binder-clip accent
            clip = 70
            cx = x0 + cw // 2 - clip // 2
            d.rounded_rectangle([cx, y0 - 40, cx + clip, y0 + 8], radius=10, fill=theme.accent)
    if theme.bucket in ("luxe", "bold"):
        for word, x in ((left, 70), (right, SIZE - 120)):
            f = theme.head(58)
            y = (SIZE - len(word) * 68) // 2
            for chc in word.upper():
                _head_text(img, theme, chc, f, x, y)
                y += 68
    return img


def render_numbered_grid(b, imgs, theme, rng):
    img = theme.backdrop(rng)
    d = ImageDraw.Draw(img)
    pool = imgs or []
    n = max(min(len(pool), 15) if pool else 10, 6)
    count = len(pool) if pool else 12
    big, lbl, sub = theme.head(150), theme.head(78), theme.body(40)
    _head_text(img, theme, str(count), big, PAD, 90)
    cw = d.textlength(str(count), font=big)
    _head_text(img, theme, "HIGH-RES FILES", lbl, PAD + int(cw) + 40, 150)
    d.text((PAD + int(cw) + 44, 250), "2000 x 2000PX  &  3600 x 3600PX", font=sub,
           fill=theme.title_color())
    cols = 5
    rows = math.ceil(n / cols)
    top, bottom = 420, SIZE - 90
    gw = (SIZE - PAD * 2 - (cols - 1) * 34) // cols
    gh = (bottom - top - (rows - 1) * 70) // rows
    for i in range(n):
        r, c = divmod(i, cols)
        x0 = PAD + c * (gw + 34)
        y0 = top + r * (gh + 70)
        if pool:
            _card(img, theme, pool[i % len(pool)], (x0, y0, x0 + gw, y0 + gh), radius=16)
        name = _SWATCH_NAMES[i % len(_SWATCH_NAMES)]
        nf = theme.head(30)
        tw = d.textlength(name, font=nf)
        d.text((x0 + (gw - tw) / 2, y0 + gh + 12), name, font=nf, fill=theme.title_color())
    return img


def render_info_panel(b, imgs, theme, rng, lines=None):
    img = theme.backdrop(rng)
    if lines is None:
        raw = " ".join(filter(None, [b.get("layout"), b.get("designDirection"), b.get("mockup")]))
        parts = [p.strip() for p in raw.replace("•", ".").split(".") if len(p.strip()) > 4][:3]
        lines = parts or ["300 DPI HIGH RESOLUTION", "COMMERCIAL USE INCLUDED", "INSTANT DOWNLOAD"]
    lines = (lines + ["", "", ""])[:3]
    top, gap = 300, 90
    bar_h = (SIZE - top - 180 - gap * 2) // 3
    for i, text in enumerate(lines):
        y0 = top + i * (bar_h + gap)
        box = (PAD, y0, SIZE - PAD, y0 + bar_h)
        panel_fill = theme.dark
        _panel(img, box, panel_fill, radius=8, alpha=210)
        if theme.frames()[0]:
            _accent_frame(img, theme, box, thickness=12, radius=6, inner_gap=20)
        if text:
            f = theme.head(70)
            _title(img, theme, text, f, y0 + (bar_h - f.getmetrics()[0] - f.getmetrics()[1]) // 2 - 10,
                   SIZE - PAD * 2 - 120, max_lines=2, bg=panel_fill)
    return img


_MOCKUP_SCENE = {
    "luxe": "elegant dark marble desk with soft gold light, minimal luxury flat lay, blurred background, professional product photography",
    "minimal": "clean bright white minimalist desk, soft daylight, scandinavian styling, blurred background, professional product photography",
    "soft": "warm neutral linen surface with dried flowers, soft natural light, boho styling, blurred background, professional product photography",
    "bold": "bright colorful modern desk flat lay, playful trendy styling, soft shadows, blurred background, professional product photography",
}


def render_mockup(b, imgs, theme, rng):
    # try a real photographic scene (free AI, prod-only); fall back to procedural
    scene = _ai_backdrop(_MOCKUP_SCENE.get(theme.bucket, _MOCKUP_SCENE["minimal"]),
                         seed=rng.randint(1, 99999))
    img = scene if scene is not None else theme.backdrop(rng)
    if imgs:
        cw, ch = int(SIZE * 0.62), int(SIZE * 0.40)
        cx, cy = (SIZE - cw) // 2, int(SIZE * 0.30)
        _card(img, theme, imgs[0], (cx, cy, cx + cw, cy + ch), radius=40, framed=False)
    title_bg = theme.dark if scene is None else (20, 20, 24)
    _title(img, theme, _overlay(b) or "See it in your work", theme.head(76), int(SIZE * 0.78),
           SIZE - PAD * 2, bg=title_bg)
    return img


def render_feature(b, imgs, theme, rng, dark=False):
    img = theme.backdrop(rng, dark=dark)
    d = ImageDraw.Draw(img)
    if imgs:
        cw = int(SIZE * 0.46)
        _card(img, theme, imgs[0], (PAD, (SIZE - cw) // 2, PAD + cw, (SIZE - cw) // 2 + cw), radius=26)
        tx = PAD + cw + 90
    else:
        tx = PAD
    tw = SIZE - tx - PAD
    y = int(SIZE * 0.20)
    title = _overlay(b) or "Premium quality"
    if theme.upper_titles():
        title = title.upper()
    bg = theme.dark if dark else theme.light
    for ln in _wrap(d, title, theme.head(70), tw)[:3]:
        _head_text(img, theme, ln, theme.head(70), tx, y, bg=bg)
        y += 94
    y += 30
    body = b.get("designDirection") or b.get("mockup") or ""
    if body:
        fg = theme.text_on(bg)
        for ln in _wrap(d, body, theme.body(42), tw)[:6]:
            d.text((tx, y), ln, font=theme.body(42), fill=fg)
            y += 60
    return img


def render_closeup(b, imgs, theme, rng):
    img = Image.new("RGB", (SIZE, SIZE), theme.dark)
    if imgs:
        src = imgs[-1] if len(imgs) > 1 else imgs[0]
        w, h = src.size
        cw, ch = int(w * 0.5), int(h * 0.5)
        crop = src.crop(((w - cw) // 2, (h - ch) // 2, (w + cw) // 2, (h + ch) // 2))
        img.paste(_cover(crop, SIZE, int(SIZE * 0.7)), (0, int(SIZE * 0.15)))
    band = _shade(theme.dark, 0.55)
    _panel(img, (0, int(SIZE * 0.80), SIZE, SIZE), band, radius=0, alpha=200)
    _title(img, theme, _overlay(b) or "100% HIGH RESOLUTION", theme.head(80), int(SIZE * 0.83),
           SIZE - PAD * 2, max_lines=1, bg=band)
    _center(img, "300 DPI  |  JPG & PNG FILES", theme.body(46), int(SIZE * 0.905),
            theme.text_on(band), max_lines=1)
    return img


def render_cta(b, imgs, theme, rng):
    img = theme.backdrop(rng)
    d = ImageDraw.Draw(img)
    if imgs:
        cw = int(SIZE * 0.44)
        x = (SIZE - cw) // 2
        _card(img, theme, imgs[0], (x, int(SIZE * 0.12), x + cw, int(SIZE * 0.12) + cw), radius=30)
    y = _title(img, theme, _overlay(b) or "Elevate your next design", theme.head(94),
               int(SIZE * 0.66), SIZE - PAD * 2)
    cta = (b.get("cta") or "Instant download • Commercial use").strip()
    bf = theme.body(46)
    bw = d.textlength(cta, font=bf) + 130
    bx, by = (SIZE - bw) / 2, y + 40
    d.rounded_rectangle([bx, by, bx + bw, by + 110], radius=55, fill=theme.accent)
    d.text((bx + 65, by + 28), cta, font=bf, fill=theme.text_on(theme.accent))
    return img


def _render_one(n, b, imgs, theme, listing_id):
    rng = _seed(listing_id, n)
    try:
        return {
            1: lambda: render_hero(b, imgs, theme, rng),
            2: lambda: render_swatch_grid(b, imgs, theme, rng, "SWATCH", "DISPLAY"),
            3: lambda: render_numbered_grid(b, imgs, theme, rng),
            4: lambda: render_closeup(b, imgs, theme, rng),
            5: lambda: render_mockup(b, imgs, theme, rng),
            6: lambda: render_info_panel(b, imgs, theme, rng),
            7: lambda: render_swatch_grid(b, imgs, theme, rng, "FULL", "COLLECTION"),
            8: lambda: render_feature(b, imgs, theme, rng, dark=False),
            9: lambda: render_info_panel(b, imgs, theme, rng,
                                         lines=["DOWNLOAD", "DROP INTO YOUR DESIGN", "CREATE SOMETHING BEAUTIFUL"]),
            10: lambda: render_cta(b, imgs, theme, rng),
        }.get(n, lambda: render_info_panel(b, imgs, theme, rng))()
    except Exception:
        log.exception("render failed for slot %s; fallback", n)
        return render_info_panel(b, imgs, theme, _seed(listing_id, n, "fb"))


def render_gallery(result: dict, product_image_paths: list[str], out_dir: str,
                   listing_id: str = "x", style: str = "") -> list[dict]:
    """Render all 10 listing images with a Theme adapted to this product's
    palette and style. Returns per-image metadata."""
    hexes = [(c or {}).get("hex") for c in ((result.get("brand") or {}).get("colors") or [])]
    style = style or ((result.get("attributes") or {}).get("styles") or [""])[0]
    theme = Theme([h for h in hexes if h], style)
    imgs = [im for im in (_load(p) for p in product_image_paths) if im is not None]
    briefs = sorted((result.get("images") or []), key=lambda x: x.get("n", 0)) or [{"n": i} for i in range(1, 11)]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    meta = []
    for brief in briefs:
        n = int(brief.get("n", len(meta) + 1))
        canvas = _render_one(n, brief, imgs, theme, listing_id)
        if canvas.size != (SIZE, SIZE):
            canvas = canvas.resize((SIZE, SIZE))
        fname = f"image_{n:02d}.png"
        canvas.save(out / fname, "PNG")
        meta.append({"n": n, "title": brief.get("title", f"Image {n}"),
                     "purpose": brief.get("purpose", ""), "file": fname, "url": None})
    return meta
