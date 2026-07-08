"""
Image Quality Scoring Engine.

Every uploaded or generated image receives ten 0-100 scores, each with an
explanation of why it is what it is and a concrete recommendation. Built on
the deterministic vision metrics plus the Phase 3 pixel validator, so scores
are reproducible and free.
"""
from __future__ import annotations

from .image_validator import score_image
from .vision_analyzer import analyze_image


def _clamp(x: float) -> int:
    return int(max(0, min(100, round(x))))


def _entry(score: float, why: str, improve: str) -> dict:
    return {"score": _clamp(score), "why": why, "improve": improve}


def score_image_quality(path: str, intent: str = "CTR",
                        brand_palette: list[str] | None = None) -> dict:
    """Ten explained scores for one image."""
    v = analyze_image(path)
    px = score_image(path, intent)  # Phase 3 conversion validator
    s = px.to_dict()

    scores: dict[str, dict] = {}
    scores["ctr"] = _entry(
        s.get("ctr_effectiveness", 50),
        "Thumbnail-scale attention: contrast, focal strength, color pop.",
        "Boost subject-background contrast; tighten the focal point.")
    scores["trust"] = _entry(
        s.get("trust_level", 50),
        "Detail credibility: fine texture visible, honest exposure.",
        "Add a macro/zoom shot; avoid over-processing.")
    scores["professionalism"] = _entry(
        0.4 * (100 if v.focus_ok else 40) + 0.3 * (100 - v.background_clutter * 100)
        + 0.3 * (100 if v.exposure == "normal" else 55),
        f"Focus {'crisp' if v.focus_ok else 'soft'}, exposure {v.exposure}, "
        f"background clutter {v.background_clutter:.0%}.",
        "Shoot on a seamless background with even lighting; check focus at 100%.")
    scores["composition"] = _entry(
        55 * v.composition_thirds + 45 * min(v.negative_space / 0.5, 1.0),
        f"{v.composition_thirds:.0%} of visual weight sits near rule-of-thirds "
        f"points; {v.negative_space:.0%} breathing room.",
        "Recompose with the subject on a thirds intersection; leave negative space.")
    scores["lighting"] = _entry(
        (100 if v.exposure == "normal" else 50) - min(v.white_balance_shift * 250, 30)
        + min(v.contrast, 60) * 0.5,
        f"Exposure {v.exposure} (mean {v.exposure_mean}), white balance "
        f"{v.white_balance}, contrast {v.contrast}.",
        "Diffuse the key light, correct white balance to neutral, lift shadows.")
    scores["thumbnail"] = _entry(
        s.get("thumbnail_readability", 50),
        "Legibility when shrunk to Etsy search-result size.",
        "Simplify the frame; one dominant subject, minimal small text.")
    scores["mobile"] = _entry(
        s.get("mobile_visibility", 50),
        "Clarity on a ~180px phone tile where most Etsy browsing happens.",
        "Increase subject scale in frame; avoid thin details near edges.")
    scores["background"] = _entry(
        100 * (0.65 * v.background_uniformity + 0.35 * (1 - v.background_clutter)),
        f"Border uniformity {v.background_uniformity:.0%}, clutter "
        f"{v.background_clutter:.0%}.",
        "Use a clean seamless or context-appropriate backdrop; declutter edges.")
    brand_score, brand_why = 50.0, "No brand palette configured."
    if brand_palette:
        mine = {c.lower() for c in (v.primary_colors + v.secondary_colors)}
        theirs = {c.lower() for c in brand_palette}
        overlap = _palette_overlap(mine, theirs)
        brand_score = 40 + 60 * overlap
        brand_why = f"{overlap:.0%} palette proximity to your brand colors."
    scores["brand_consistency"] = _entry(
        brand_score, brand_why,
        "Bring brand palette into props, backdrop, or overlay accents.")

    overall = _clamp(
        0.2 * scores["ctr"]["score"] + 0.15 * scores["trust"]["score"]
        + 0.15 * scores["professionalism"]["score"] + 0.1 * scores["composition"]["score"]
        + 0.1 * scores["lighting"]["score"] + 0.1 * scores["thumbnail"]["score"]
        + 0.1 * scores["mobile"]["score"] + 0.1 * scores["background"]["score"])
    scores["overall"] = {
        "score": overall,
        "why": "Weighted blend: CTR 20%, trust 15%, professionalism 15%, "
               "composition/lighting/thumbnail/mobile/background 10% each.",
        "improve": _top_improvements(scores),
    }
    return {"path": str(path), "scores": scores,
            "defects": v.defects, "vision": {"sharpness": v.sharpness,
                                             "exposure": v.exposure,
                                             "colors": v.primary_colors}}


def _palette_overlap(a: set[str], b: set[str]) -> float:
    """Loose hex proximity: share of brand colors with a near match."""
    def rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) if len(h) == 6 else (0, 0, 0)
    if not a or not b:
        return 0.0
    hits = 0
    for bc in b:
        br = rgb(bc)
        if any(sum(abs(x - y) for x, y in zip(br, rgb(ac))) < 150 for ac in a):
            hits += 1
    return hits / len(b)


def _top_improvements(scores: dict, n: int = 3) -> list[str]:
    ranked = sorted(((k, v) for k, v in scores.items() if k != "overall"),
                    key=lambda kv: kv[1]["score"])
    return [f"{k}: {v['improve']}" for k, v in ranked[:n] if v["score"] < 75]
