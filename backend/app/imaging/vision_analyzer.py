"""
Computer Vision Analysis Engine.

Two layers:
  1. Deterministic pixel analysis (Pillow + numpy, always available, free):
     resolution, sharpness/focus, exposure, white balance, contrast,
     background quality + clutter, composition (rule of thirds, negative
     space), primary/secondary colors, texture energy, watermark heuristic,
     defect heuristic.
  2. Optional semantic pass (Anthropic vision, when ANTHROPIC_API_KEY is set
     and the `vision_semantic` feature flag is on): product category,
     materials, branding/packaging visibility, scale references.

Output is structured JSON (VisionReport) that flows into the Context Manager,
where the Buyer Decision Engine and Image Strategy Engine consume it.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

log = logging.getLogger("listingforge.vision")

MIN_RESOLUTION = 800          # Etsy recommends 2000px; hard floor here
SHARPNESS_FLOOR = 12.0        # gradient-energy floor below which = blurry
EXPOSURE_DARK, EXPOSURE_BRIGHT = 55, 205


@dataclass
class ImageVision:
    path: str
    width: int = 0
    height: int = 0
    resolution_ok: bool = True
    sharpness: float = 0.0          # gradient energy (higher = crisper)
    focus_ok: bool = True
    exposure_mean: float = 0.0
    exposure: str = "normal"        # under | normal | over
    contrast: float = 0.0
    white_balance_shift: float = 0.0  # 0 = neutral; >0.12 = noticeable cast
    white_balance: str = "neutral"
    background_uniformity: float = 0.0  # 0..1 (1 = clean seamless bg)
    background_clutter: float = 0.0     # edge density in border band 0..1
    composition_thirds: float = 0.0     # saliency mass near thirds points 0..1
    negative_space: float = 0.0         # fraction of low-detail area 0..1
    primary_colors: list[str] = field(default_factory=list)
    secondary_colors: list[str] = field(default_factory=list)
    texture_energy: float = 0.0
    watermark_suspected: bool = False
    defects: list[str] = field(default_factory=list)
    # semantic (AI) fields — filled only when the semantic pass runs
    product_category_guess: str = ""
    materials_guess: list[str] = field(default_factory=list)
    lighting_quality: str = ""
    branding_visible: bool | None = None
    packaging_visible: bool | None = None
    scale_reference_present: bool | None = None


def _gray(arr: np.ndarray) -> np.ndarray:
    return arr.mean(axis=2) if arr.ndim == 3 else arr


def _gradient_energy(g: np.ndarray) -> float:
    gx = np.abs(np.diff(g, axis=1)).mean()
    gy = np.abs(np.diff(g, axis=0)).mean()
    return float(gx + gy)


def _hex(rgb) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(int(c) for c in rgb))


def _dominant_colors(img: Image.Image, n: int = 6) -> list[str]:
    small = img.convert("RGB").resize((64, 64))
    pal = small.quantize(colors=n, method=Image.Quantize.MEDIANCUT).convert("RGB")
    counts: dict[tuple, int] = {}
    for px in pal.getdata():
        counts[px] = counts.get(px, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return [_hex(c) for c, _ in ranked[:n]]


def analyze_image(path: str) -> ImageVision:
    """Deterministic pixel-level analysis of a single image."""
    v = ImageVision(path=str(path))
    try:
        img = Image.open(path).convert("RGB")
    except Exception as exc:
        v.defects.append(f"unreadable image: {exc}")
        v.resolution_ok = v.focus_ok = False
        return v

    v.width, v.height = img.size
    v.resolution_ok = min(img.size) >= MIN_RESOLUTION

    work = img.resize((256, 256))
    arr = np.asarray(work, dtype=np.float32)
    g = _gray(arr)

    v.sharpness = round(_gradient_energy(g), 2)
    v.focus_ok = v.sharpness >= SHARPNESS_FLOOR
    v.exposure_mean = round(float(g.mean()), 1)
    v.exposure = ("under" if v.exposure_mean < EXPOSURE_DARK
                  else "over" if v.exposure_mean > EXPOSURE_BRIGHT else "normal")
    v.contrast = round(float(g.std()), 1)

    means = arr.reshape(-1, 3).mean(axis=0)
    total = means.sum() or 1.0
    v.white_balance_shift = round(float(np.abs(means / total - 1 / 3).max()), 3)
    if v.white_balance_shift > 0.12:
        dom = ["red", "green", "blue"][int(np.argmax(means))]
        v.white_balance = f"{dom} cast"

    # background: 12% border band
    b = 30  # of 256
    border = np.concatenate([g[:b].ravel(), g[-b:].ravel(),
                             g[:, :b].ravel(), g[:, -b:].ravel()])
    v.background_uniformity = round(float(1.0 - min(border.std() / 64.0, 1.0)), 3)
    bx = np.abs(np.diff(g[:b], axis=1)).mean() + np.abs(np.diff(g[-b:], axis=1)).mean()
    v.background_clutter = round(float(min(bx / 40.0, 1.0)), 3)

    # composition: gradient saliency mass near rule-of-thirds intersections
    gx = np.abs(np.diff(g, axis=1))[:255, :255]
    gy = np.abs(np.diff(g, axis=0))[:255, :255]
    sal = gx + gy
    total_sal = sal.sum() or 1.0
    mass = 0.0
    for ty in (85, 170):
        for tx in (85, 170):
            mass += sal[max(ty - 32, 0):ty + 32, max(tx - 32, 0):tx + 32].sum()
    v.composition_thirds = round(float(min(mass / total_sal, 1.0)), 3)
    v.negative_space = round(float((sal < np.percentile(sal, 60)).mean()), 3)

    colors = _dominant_colors(img)
    v.primary_colors, v.secondary_colors = colors[:3], colors[3:]
    v.texture_energy = round(v.sharpness * (1 - v.negative_space), 2)

    # watermark heuristic: semi-transparent repeated structure ≈ mid-band
    # brightness ridges with low saturation in center region
    hsv = np.asarray(work.convert("HSV"), dtype=np.float32)
    center_sat = hsv[64:192, 64:192, 1].mean()
    center_edges = _gradient_energy(g[64:192, 64:192])
    v.watermark_suspected = bool(center_edges > 28 and center_sat < 40
                                 and v.background_uniformity > 0.75)

    if not v.resolution_ok:
        v.defects.append(f"resolution {v.width}x{v.height} below {MIN_RESOLUTION}px minimum")
    if not v.focus_ok:
        v.defects.append(f"soft focus (sharpness {v.sharpness} < {SHARPNESS_FLOOR})")
    if v.exposure != "normal":
        v.defects.append(f"{v.exposure}exposed (mean {v.exposure_mean})")
    if v.contrast < 22:
        v.defects.append(f"weak contrast ({v.contrast})")
    if v.background_clutter > 0.55:
        v.defects.append("cluttered background")
    return v


def semantic_pass(paths: list[str]) -> dict:
    """Optional AI semantic attributes via Anthropic vision. Best-effort."""
    import base64

    from pydantic import BaseModel

    from ..config import get_settings

    if not get_settings().anthropic_api_key or not paths:
        return {}

    from ..pipeline.llm import structured_call

    class Semantic(BaseModel):
        product_category_guess: str
        materials_guess: list[str]
        lighting_quality: str
        branding_visible: bool
        packaging_visible: bool
        scale_reference_present: bool

    try:
        p = Path(paths[0])
        b64 = base64.b64encode(p.read_bytes()).decode()
        media = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        result, _ = structured_call(
            "You are a product photography analyst. Answer strictly about what is visible.",
            [{"type": "image", "source": {"type": "base64", "media_type": media, "data": b64}},
             {"type": "text", "text": "Analyze this product photo."}],
            Semantic, max_tokens=600, temperature=0.0)
        return result.model_dump()
    except Exception:
        log.warning("semantic vision pass failed; continuing with pixel metrics",
                    exc_info=True)
        return {}


def analyze_product_images(paths: list[str], use_semantic: bool = True) -> dict:
    """Full VisionReport for a set of uploaded product images."""
    images = [asdict(analyze_image(p)) for p in paths]
    report = {
        "image_count": len(images),
        "images": images,
        "aggregate": {},
    }
    if images:
        ok = [i for i in images if not i["defects"]]
        report["aggregate"] = {
            "clean_images": len(ok),
            "avg_sharpness": round(sum(i["sharpness"] for i in images) / len(images), 2),
            "avg_background_uniformity": round(
                sum(i["background_uniformity"] for i in images) / len(images), 3),
            "dominant_palette": images[0]["primary_colors"],
            "all_defects": sorted({d for i in images for d in i["defects"]}),
        }
    if use_semantic and paths:
        try:
            from ..feature_flags import is_enabled
            do_semantic = is_enabled("vision_semantic")
        except Exception:
            do_semantic = True
        if do_semantic:
            sem = semantic_pass(paths)
            if sem and images:
                images[0].update(sem)
                report["aggregate"]["semantic"] = sem
    return report
