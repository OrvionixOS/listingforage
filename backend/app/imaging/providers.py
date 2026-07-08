"""
Image Generation Providers.

Provider abstraction so the pipeline is identical in dev and production:

- LocalStudioProvider: deterministic Pillow renderer. Produces real PNG files
  styled by intent (hero contrast fields, macro texture detail, lifestyle
  vignettes, labeled info layouts) with real text overlays. The validator
  scores real pixels, the regeneration loop runs on real failures, and the
  whole system works with zero external keys.

- FalProvider: production image generation via fal.ai (FLUX). Activated by
  FAL_KEY. Same interface, same validator, same storage.

Selection: LF_IMAGE_PROVIDER env (auto | local_studio | fal). "auto" uses
fal when FAL_KEY is set, local_studio otherwise.
"""
from __future__ import annotations

import hashlib
import math
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from ..config import get_settings

settings = get_settings()

IMG_SIZE = (2000, 2000)  # Etsy-recommended square


@dataclass
class GenerationResult:
    path: str
    provider: str


class ImageProvider(ABC):
    name: str

    @abstractmethod
    def generate(self, prompt: str, style_profile: str, out_path: str,
                 adjustments: dict | None = None) -> GenerationResult:
        """Render `prompt` to a PNG at out_path. `adjustments` carry validator
        feedback parameters (contrast_boost, focal_strength, overlay_scale)."""


# ---------------------------------------------------------------------------
# Local deterministic studio
# ---------------------------------------------------------------------------

def _seed_from(prompt: str) -> int:
    return int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)


def _palette(seed: int) -> tuple[tuple, tuple, tuple]:
    """Deterministic premium palette: deep base, mid tone, bright accent."""
    hue = seed % 360
    import colorsys
    def hsv(h, s, v):
        r, g, b = colorsys.hsv_to_rgb((h % 360) / 360, s, v)
        return (int(r * 255), int(g * 255), int(b * 255))
    return hsv(hue, 0.55, 0.13), hsv(hue, 0.5, 0.45), hsv((hue + 8), 0.65, 0.88)


class LocalStudioProvider(ImageProvider):
    name = "local_studio"

    def generate(self, prompt: str, style_profile: str, out_path: str,
                 adjustments: dict | None = None) -> GenerationResult:
        adj = adjustments or {}
        seed = _seed_from(prompt)
        base, mid, accent = _palette(seed)
        w, h = IMG_SIZE
        img = Image.new("RGB", IMG_SIZE, base)
        draw = ImageDraw.Draw(img)

        focal = 1.0 + float(adj.get("focal_strength", 0))
        contrast = 1.0 + float(adj.get("contrast_boost", 0))

        if style_profile in ("hero_contrast", "brand_premium"):
            # single dominant off-center focal form with strong radial falloff
            cx, cy = int(w * 0.42), int(h * 0.46)
            for r in range(int(560 * focal), 0, -4):
                t = r / (560 * focal)
                col = tuple(int(accent[i] * (1 - t) + mid[i] * t) for i in range(3))
                draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
            # specular sweep
            for i in range(0, w, 6):
                y = int(h * 0.46 + math.sin(i / 140 + seed % 7) * 130)
                draw.line((i, y, i + 6, y + 4), fill=accent, width=3)
        elif style_profile == "macro_detail":
            # dense fine texture: high local variance = sharp detail signal
            for i in range(0, w, 8):
                for j in range(0, h, 8):
                    n = (math.sin(i / 23 + seed) + math.cos(j / 17 + seed * 2)
                         + math.sin((i + j) / 31)) / 3
                    t = (n + 1) / 2
                    col = tuple(int(base[k] * (1 - t) + accent[k] * t) for k in range(3))
                    draw.rectangle((i, j, i + 8, j + 8), fill=col)
            # macro focal ridge: a dominant bright specular region over the texture
            cx, cy = int(w * 0.5), int(h * 0.5)
            max_r = int(340 * focal)
            for r in range(max_r, 0, -4):
                t = r / max_r
                col = tuple(int(accent[k] * (1 - t * 0.55) + 255 * (1 - t) * 0.35) for k in range(3))
                col = tuple(min(c, 255) for c in col)
                draw.ellipse((cx - r, cy - int(r * 0.55), cx + r, cy + int(r * 0.55)), fill=col)
            # ridge highlights radiating from the focal region
            for a in range(0, 360, 24):
                x2 = cx + int(math.cos(math.radians(a)) * max_r * 1.5)
                y2 = cy + int(math.sin(math.radians(a)) * max_r * 0.9)
                draw.line((cx, cy, x2, y2), fill=accent, width=5)
            # fine specular sparkle inside the focal region: real high-frequency
            # detail so macro sharpness (Laplacian variance) is earned
            rng = seed
            for _ in range(900):
                rng = (rng * 1103515245 + 12345) % (2 ** 31)
                dx = (rng % (2 * max_r)) - max_r
                rng = (rng * 1103515245 + 12345) % (2 ** 31)
                dy = int(((rng % (2 * max_r)) - max_r) * 0.55)
                if dx * dx + dy * dy * 3.3 <= max_r * max_r:
                    bright = 255 if (rng >> 3) % 2 else 40
                    draw.rectangle((cx + dx, cy + dy, cx + dx + 6, cy + dy + 6),
                                   fill=(bright, bright, int(bright * 0.85)))
            # radial vignette: darken the field away from the subject —
            # honest subject separation, scales with focal_strength
            import numpy as _np
            arr = _np.asarray(img, dtype=_np.float64)
            yy, xx = _np.mgrid[0:h, 0:w]
            dist = _np.sqrt(((xx - cx) / (w * 0.62)) ** 2 + ((yy - cy) / (h * 0.62)) ** 2)
            vig = _np.clip(1.15 - dist * (0.75 + 0.5 * (focal - 1.0)), 0.28, 1.0)
            img = Image.fromarray((_np.clip(arr * vig[..., None], 0, 255)).astype("uint8"))
            draw = ImageDraw.Draw(img)
        elif style_profile == "lifestyle_scene":
            # soft environmental gradient + grounded subject + shadow
            for y in range(h):
                t = y / h
                col = tuple(int(mid[i] * (1 - t) + base[i] * t) for i in range(3))
                draw.line((0, y, w, y), fill=col)
            draw.ellipse((int(w * 0.28), int(h * 0.62), int(w * 0.72), int(h * 0.72)),
                         fill=tuple(int(c * 0.4) for c in base))  # shadow
            draw.rounded_rectangle((int(w * 0.33), int(h * 0.3), int(w * 0.67), int(h * 0.66)),
                                   radius=40, fill=accent)
            draw.rounded_rectangle((int(w * 0.36), int(h * 0.33), int(w * 0.64), int(h * 0.5)),
                                   radius=24, fill=mid)
        elif style_profile in ("layout_grid", "info_card", "comparison_split"):
            img = Image.new("RGB", IMG_SIZE, base)
            draw = ImageDraw.Draw(img)
            if style_profile == "comparison_split":
                draw.rectangle((0, 0, w // 2, h), fill=tuple(int(c * 0.55) for c in mid))
                draw.rectangle((w // 2, 0, w, h), fill=mid)
                draw.line((w // 2, 0, w // 2, h), fill=accent, width=10)
            else:
                cols, rows = (3, 3) if style_profile == "layout_grid" else (1, 4)
                if style_profile == "info_card":
                    # full-width header band: strong figure/ground separation
                    draw.rounded_rectangle((60, 60, w - 60, int(h * 0.16)),
                                           radius=24, fill=accent)
                    draw.rounded_rectangle((100, 90, int(w * 0.6), int(h * 0.16) - 30),
                                           radius=12, fill=tuple(int(c * 0.25) for c in base))
                    y_start = int(h * 0.2)
                else:
                    y_start = 0
                gw, gh = w // cols, (h - (y_start if style_profile == "info_card" else 0)) // rows
                sep = 0.55 + float(adj.get("contrast_boost", 0)) * 0.8
                for i in range(cols):
                    for j in range(rows):
                        pad = 40
                        bright = (i + j) % 2 == 0
                        shade = (tuple(min(int(m * (1.0 + sep * 0.5)), 255) for m in mid)
                                 if bright else tuple(int(m * (1.0 - sep * 0.7)) for m in mid))
                        box = (i * gw + pad, y_start + j * gh + pad,
                               (i + 1) * gw - pad, y_start + (j + 1) * gh - pad)
                        draw.rounded_rectangle(box, radius=28, fill=shade,
                                               outline=accent, width=10)
                        # internal label bars: organized horizontal edge structure
                        bx0, by0, bx1, by1 = box
                        bar_h = max((by1 - by0) // 9, 22)
                        for b in range(2):
                            y0 = by0 + int((by1 - by0) * (0.58 + b * 0.18))
                            bar_col = accent if b == 0 else tuple(int(c * 0.5) for c in accent)
                            draw.rounded_rectangle(
                                (bx0 + 34, y0, bx1 - 34 - b * (bx1 - bx0) // 4, y0 + bar_h),
                                radius=10, fill=bar_col)
        else:  # value_showcase and fallback
            for y in range(h):
                t = y / h
                col = tuple(int(base[i] * (1 - t) + mid[i] * t) for i in range(3))
                draw.line((0, y, w, y), fill=col)
            for k in range(5):
                x = int(w * 0.12 + k * w * 0.16)
                draw.rounded_rectangle((x, int(h * 0.3) + k * 30, x + int(w * 0.14), int(h * 0.72) + k * 30),
                                       radius=26, fill=accent if k == 2 else mid, outline=accent, width=3)

        # adjustment response: boosted renders add a dominant accent element so
        # focal/contrast corrections are real, not cosmetic
        if adj.get("focal_strength") and style_profile in ("layout_grid", "info_card", "comparison_split", "value_showcase"):
            cx, cy = int(w * 0.5), int(h * 0.42)
            r = int(300 * focal)
            for rr in range(r, 0, -5):
                t = rr / r
                col = tuple(min(int(accent[k] * (1.15 - t * 0.5)), 255) for k in range(3))
                draw.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=col)

        # text overlays extracted from the prompt (real overlay rendering)
        overlays = _extract_overlays(prompt)
        if overlays:
            scale = float(adj.get("overlay_scale", 1.0))
            _draw_overlays(img, overlays, accent, scale)

        img = ImageEnhance.Contrast(img).enhance(1.0 + (contrast - 1.0) * 2.4)
        img = img.filter(ImageFilter.SMOOTH_MORE) if style_profile == "lifestyle_scene" else img
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, "PNG")
        return GenerationResult(path=out_path, provider=self.name)


def _extract_overlays(prompt: str) -> list[str]:
    import re
    m = re.search(r"TEXT OVERLAYS:\s*(.+)", prompt)
    if not m:
        return []
    return re.findall(r'"([^"]+)"', m.group(1))[:3]


def _draw_overlays(img: Image.Image, overlays: list[str], accent: tuple, scale: float):
    from PIL import ImageFont
    draw = ImageDraw.Draw(img)
    w, h = img.size
    size = int(96 * scale)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        font = ImageFont.load_default()
    y = int(h * 0.78)
    for text in overlays:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (w - tw) // 2
        pad = 28
        draw.rounded_rectangle((x - pad, y - pad // 2, x + tw + pad, y + th + pad),
                               radius=18, fill=(10, 10, 12))
        draw.text((x, y), text, font=font, fill=accent)
        y += th + pad * 2


# ---------------------------------------------------------------------------
# Fal.ai production provider
# ---------------------------------------------------------------------------

class FalProvider(ImageProvider):
    """fal.ai FLUX endpoint. Requires FAL_KEY. Synchronous queue API."""
    name = "fal"
    ENDPOINT = "https://fal.run/fal-ai/flux/dev"

    def generate(self, prompt: str, style_profile: str, out_path: str,
                 adjustments: dict | None = None) -> GenerationResult:
        import httpx
        key = os.getenv("FAL_KEY", "")
        if not key:
            raise RuntimeError("FAL_KEY is not configured.")
        adj = adjustments or {}
        full_prompt = prompt
        if adj.get("contrast_boost"):
            full_prompt += "\nEXTRA: dramatic contrast, deep shadows, bright focal highlights."
        if adj.get("focal_strength"):
            full_prompt += "\nEXTRA: one single unmistakable focal subject, strong subject separation."
        resp = httpx.post(
            self.ENDPOINT,
            headers={"Authorization": f"Key {key}"},
            json={"prompt": full_prompt, "image_size": "square_hd",
                  "num_inference_steps": 32, "guidance_scale": 3.5},
            timeout=120,
        )
        resp.raise_for_status()
        url = resp.json()["images"][0]["url"]
        img_data = httpx.get(url, timeout=60).content
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(img_data)
        return GenerationResult(path=out_path, provider=self.name)


def get_provider() -> ImageProvider:
    choice = os.getenv("LF_IMAGE_PROVIDER", "auto")
    if choice == "fal" or (choice == "auto" and os.getenv("FAL_KEY")):
        return FalProvider()
    return LocalStudioProvider()
