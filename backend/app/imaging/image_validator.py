"""
Image Validation System — scores REAL pixels, not intentions.

Every generated image is measured:
  - ctr_effectiveness    : global contrast + focal dominance (does it stop scroll?)
  - trust_level          : detail sharpness (Laplacian variance — macro fidelity proxy)
  - clarity_level        : structural legibility (edge organization vs noise)
  - mobile_visibility    : contrast retention at phone display size (~360px)
  - thumbnail_readability: focal survival + contrast at Etsy grid size (180px)

FAIL CONDITIONS (any → regenerate with adjusted parameters):
  - unclear product identity  (no dominant focal region)
  - weak lighting contrast    (flat luminance histogram)
  - missing focal point       (center-weighted saliency below threshold)
  - poor mobile readability   (thumbnail contrast collapse)
  - aesthetic-only output     (composite below floor for the slot's intent)

On failure the validator returns concrete prompt/render adjustments
(contrast_boost, focal_strength, overlay_scale) consumed by the provider.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from ..schemas import ImageIntent

# per-intent minimum composite scores — CTR slots must clear a higher bar
INTENT_FLOOR = {
    ImageIntent.CTR: 62, ImageIntent.TRUST: 55, ImageIntent.CLARITY: 55,
    ImageIntent.VALUE: 50, ImageIntent.CONTEXT: 50, ImageIntent.CONVERSION: 52,
}


@dataclass
class ImageScores:
    ctr_effectiveness: int
    trust_level: int
    clarity_level: int
    mobile_visibility: int
    thumbnail_readability: int
    composite: int
    failures: list[str] = field(default_factory=list)
    adjustments: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict:
        return {
            "ctr_effectiveness": self.ctr_effectiveness,
            "trust_level": self.trust_level,
            "clarity_level": self.clarity_level,
            "mobile_visibility": self.mobile_visibility,
            "thumbnail_readability": self.thumbnail_readability,
            "composite": self.composite,
            "failures": self.failures,
        }


def _gray(img: Image.Image, size: int | None = None) -> np.ndarray:
    if size:
        img = img.resize((size, size))
    return np.asarray(img.convert("L"), dtype=np.float64)


def _contrast_score(g: np.ndarray) -> float:
    """RMS contrast normalized: 0 flat → 100 punchy."""
    return float(min(g.std() / 64.0, 1.0) * 100)


def _laplacian_var(g: np.ndarray) -> float:
    """Sharpness/detail proxy — variance of the discrete Laplacian."""
    lap = (-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1]
           + g[1:-1, :-2] + g[1:-1, 2:])
    return float(lap.var())


def _focal_dominance(g: np.ndarray) -> float:
    """How much one region dominates attention: energy concentration of the
    top-decile luminance-deviation mass. 0 = uniform, 100 = one clear subject."""
    dev = np.abs(g - g.mean())
    thresh = np.quantile(dev, 0.9)
    mask = dev >= thresh
    if mask.sum() == 0:
        return 0.0
    ys, xs = np.nonzero(mask)
    spread = (xs.std() / g.shape[1] + ys.std() / g.shape[0]) / 2  # 0 tight → ~0.29 uniform
    return float(max(0.0, min(1.0, 1.35 - spread * 4.2)) * 100)


def _otsu_separation(g: np.ndarray) -> float:
    """Bimodality of the luminance histogram (Otsu between-class variance
    normalized by total variance). Legible layouts separate figure from ground
    into distinct levels (→1); mush and noise don't (→0)."""
    hist, _ = np.histogram(g, bins=64, range=(0, 255))
    p = hist / hist.sum()
    bins = np.arange(64)
    omega = np.cumsum(p)
    mu = np.cumsum(p * bins)
    mu_t = mu[-1]
    denom = omega * (1 - omega)
    denom[denom == 0] = 1e-9
    sigma_b = (mu_t * omega - mu) ** 2 / denom
    total_var = ((bins - mu_t) ** 2 * p).sum()
    return float(sigma_b.max() / (total_var + 1e-9))


def _edge_organization(g: np.ndarray) -> float:
    """Structural legibility: STRONG edges (95th-percentile gradient) plus
    figure/ground separation (Otsu bimodality). A clean grid with few but
    crisp, high-contrast edges scores high; low-contrast mush scores low —
    edge *quantity* is deliberately not rewarded."""
    gx = np.abs(np.diff(g, axis=1))
    gy = np.abs(np.diff(g, axis=0))
    strong = float(np.quantile(np.concatenate([gx.ravel(), gy.ravel()]), 0.95))
    edge_strength = min(strong / 55.0, 1.0)
    bimodality = min(_otsu_separation(g) / 0.65, 1.0)
    return float((0.5 * edge_strength + 0.5 * bimodality) * 100)


def score_image(path: str, intent: ImageIntent) -> ImageScores:
    img = Image.open(path)
    g_full = _gray(img, 512)
    g_thumb = _gray(img, 180)
    g_mobile = _gray(img, 360)

    contrast = _contrast_score(g_full)
    focal = _focal_dominance(g_full)
    sharp = min(_laplacian_var(g_full) / 900.0, 1.0) * 100
    clarity = _edge_organization(g_full)
    mobile = 0.6 * _contrast_score(g_mobile) + 0.4 * _focal_dominance(g_mobile)
    thumb = 0.5 * _contrast_score(g_thumb) + 0.5 * _focal_dominance(g_thumb)

    ctr = 0.45 * contrast + 0.4 * focal + 0.15 * thumb
    trust = 0.6 * sharp + 0.25 * contrast + 0.15 * clarity
    composite = round(0.3 * ctr + 0.2 * trust + 0.2 * clarity + 0.15 * mobile + 0.15 * thumb)

    failures: list[str] = []
    adjustments: dict = {}

    # Intent classes: FOCAL intents need one dominant subject; LAYOUT intents
    # (grids, info cards, comparisons) are deliberately multi-focal and are
    # judged on structural legibility instead.
    focal_intents = {ImageIntent.CTR, ImageIntent.TRUST, ImageIntent.CONTEXT}

    if contrast < 22:
        failures.append("weak lighting contrast: flat luminance histogram")
        adjustments["contrast_boost"] = 0.35
    if intent in focal_intents and focal < 30:
        failures.append("missing focal point: no dominant subject region")
        adjustments["focal_strength"] = 0.4
    if intent not in focal_intents and clarity < 35:
        failures.append("weak structural legibility: layout reads as noise")
        adjustments["contrast_boost"] = max(adjustments.get("contrast_boost", 0), 0.3)
    if intent == ImageIntent.CTR and focal < 42:
        failures.append("unclear product identity at grid scale")
        adjustments["focal_strength"] = max(adjustments.get("focal_strength", 0), 0.5)
    # thumbnail readability: focal survival matters for focal intents;
    # contrast survival matters for all
    thumb_floor = 30 if intent in focal_intents else 22
    if thumb < thumb_floor:
        failures.append("poor thumbnail readability at 180px")
        adjustments["contrast_boost"] = max(adjustments.get("contrast_boost", 0), 0.3)
        adjustments["overlay_scale"] = 1.25
    mobile_floor = 32 if intent in focal_intents else 24
    if mobile < mobile_floor:
        failures.append("poor mobile readability at phone scale")
        adjustments["contrast_boost"] = max(adjustments.get("contrast_boost", 0), 0.25)
    floor = INTENT_FLOOR.get(intent, 50)
    if composite < floor and not failures:
        failures.append(
            f"aesthetic-only output: composite {composite} below the {intent.value} "
            f"conversion floor of {floor}")
        adjustments["contrast_boost"] = 0.25
        adjustments["focal_strength"] = 0.3

    return ImageScores(
        ctr_effectiveness=round(ctr), trust_level=round(trust),
        clarity_level=round(clarity), mobile_visibility=round(mobile),
        thumbnail_readability=round(thumb), composite=composite,
        failures=failures, adjustments=adjustments,
    )
