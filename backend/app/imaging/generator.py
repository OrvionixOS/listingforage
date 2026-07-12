"""
Image Generation Engine + Image Orchestration Engine.

GENERATION
  Compiles each of the 10 validated strategy slots (the full Etsy gallery)
  into a style_profile and a generation prompt (mandatory suffix appended),
  renders it via the configured provider, scores the real pixels, and
  regenerates with validator-supplied adjustments until it passes (bounded).
  Every attempt is logged to image_generation_logs; final images land in
  listing_images with full score history.

ORCHESTRATION
  The 10-slot image strategy already carries a FIXED conversion role per slot
  (schemas.IMAGE_ROLE_BY_SLOT), so display order is simply slot_id order:
    1 Hero → 2 Overview → 3 Value breakdown → 4 Lifestyle mockup →
    5 Alternate use case → 6 Close-up detail → 7 How it works →
    8 Sizes/formats/compatibility → 9 Benefits/transformation → 10 Brand + CTA.
  This step re-validates the finished set carries every mandated role and
  fails safe (rather than shipping an incomplete gallery) if one is missing —
  the Phase-2 schema/validator should make that impossible upstream.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import ImageGenerationLog, ListingImage
from ..schemas import IMAGE_ROLE_BY_SLOT, ImageSlot, ImageStrategy
from .image_validator import ImageScores, score_image
from .providers import ImageProvider, get_provider

log = logging.getLogger("listingforge.imaging")
settings = get_settings()

MAX_RENDER_ATTEMPTS = 3

MANDATORY_SUFFIX = ("Optimized for Etsy conversion. Designed to reduce buyer "
                    "uncertainty and increase purchase confidence.")

# visual type → renderer style profile
STYLE_PROFILES = {
    "hero_macro": "hero_contrast",
    "zoom_proof": "macro_detail",
    "process_shot": "macro_detail",
    "lifestyle_scene": "lifestyle_scene",
    "mockup_in_use": "lifestyle_scene",
    "file_grid": "layout_grid",
    "variant_grid": "layout_grid",
    "size_chart": "layout_grid",
    "scale_reference": "layout_grid",
    "info_card": "info_card",
    "comparison_split": "comparison_split",
    "unboxing": "brand_premium",
}

# lens defaults per style when the strategy prompt lacks one (belt & braces —
# schema already mandates camera specs)
LENS_HINT = {
    "hero_contrast": "85mm, f/2.8", "macro_detail": "100mm macro, f/5.6",
    "lifestyle_scene": "35mm, f/4", "layout_grid": "50mm flat lay, f/8",
    "info_card": "50mm straight-on, f/8", "comparison_split": "50mm, f/8",
    "brand_premium": "85mm, f/2.8",
}


def compile_generation_prompt(slot: ImageSlot) -> tuple[str, str]:
    """Slot → (generation_prompt, style_profile). The strategy prompt already
    carries lighting/camera/environment/composition/product-focus/realism;
    this adds slot constraints and the mandatory conversion suffix."""
    style = STYLE_PROFILES.get(slot.required_visual_type, "hero_contrast")
    parts = [slot.prompt.render()]
    if slot.prompt_constraints:
        parts.append("CONSTRAINTS: " + "; ".join(slot.prompt_constraints))
    parts.append(f"LENS DEFAULT: {LENS_HINT[style]}")
    parts.append(MANDATORY_SUFFIX)
    return "\n".join(parts), style


@dataclass
class GeneratedSlotImage:
    slot_id: int
    image_id: str
    image_url: str
    generation_prompt: str
    style_profile: str
    validation_score: int
    scores: dict
    regeneration_count: int
    display_order: int | None = None


@dataclass
class ImageRunResult:
    images: list[GeneratedSlotImage] = field(default_factory=list)
    sequence_report: dict = field(default_factory=dict)


def generate_slot(db: Session, listing_id: str, slot: ImageSlot,
                  provider: ImageProvider, out_dir: Path) -> GeneratedSlotImage:
    prompt, style = compile_generation_prompt(slot)
    adjustments: dict = {}
    scores: ImageScores | None = None
    attempt = 0
    final_path = ""

    while attempt < MAX_RENDER_ATTEMPTS:
        attempt += 1
        path = out_dir / f"slot{slot.slot_id}_v{attempt}.png"
        provider.generate(prompt, style, str(path), adjustments)
        scores = score_image(str(path), slot.intent)
        db.add(ImageGenerationLog(
            listing_id=listing_id, slot_id=slot.slot_id, attempt_number=attempt,
            prompt=prompt if attempt == 1 else f"{prompt}\nADJUSTMENTS: {adjustments}",
            passed=scores.passed,
            failure_reason=None if scores.passed else "; ".join(scores.failures),
            score_json=scores.to_dict(),
        ))
        db.commit()
        final_path = str(path)
        if scores.passed:
            break
        # merge validator adjustments, escalating strength on repeat failures
        for k, v in scores.adjustments.items():
            if isinstance(v, (int, float)):
                adjustments[k] = max(adjustments.get(k, 0), v) + (0.15 if k in adjustments else 0)
            else:
                adjustments[k] = v
        log.warning("listing %s slot %d attempt %d failed: %s",
                    listing_id, slot.slot_id, attempt, scores.failures)

    if scores is None:
        raise RuntimeError(f"slot {slot.slot_id}: no render attempts executed")
    if not scores.passed:
        # keep best-effort image but surface failure loudly in the report
        log.error("slot %d did not pass after %d attempts; shipping best effort with failures %s",
                  slot.slot_id, attempt, scores.failures)

    # supersede any previous versions
    db.query(ListingImage).filter(
        ListingImage.listing_id == listing_id,
        ListingImage.slot_id == slot.slot_id,
        ListingImage.superseded.is_(False),
    ).update({"superseded": True})
    record = ListingImage(
        listing_id=listing_id, slot_id=slot.slot_id, image_url=final_path,
        prompt_used=prompt, style_profile=style,
        score_json=scores.to_dict(), validation_score=scores.composite,
        regeneration_count=attempt - 1, provider=provider.name,
    )
    db.add(record)
    db.commit()
    return GeneratedSlotImage(
        slot_id=slot.slot_id, image_id=record.id, image_url=final_path,
        generation_prompt=prompt, style_profile=style,
        validation_score=scores.composite, scores=scores.to_dict(),
        regeneration_count=attempt - 1,
    )


# ---------------------------------------------------------------------------
# Orchestration: fixed 10-role Etsy gallery sequence
# ---------------------------------------------------------------------------

def orchestrate_sequence(strategy: ImageStrategy,
                         generated: list[GeneratedSlotImage]) -> tuple[list[GeneratedSlotImage], dict]:
    """Display order is slot_id order — the strategy schema already enforces
    slot.role == IMAGE_ROLE_BY_SLOT[slot_id], so the gallery is already in the
    mandated psychological sequence. This re-verifies every role is present
    and fails safe rather than shipping an incomplete gallery."""
    slots = {s.slot_id: s for s in strategy.slots}
    order: dict[int, GeneratedSlotImage] = {}
    for g in generated:
        g.display_order = g.slot_id
        order[g.slot_id] = g

    present_roles = {slots[g.slot_id].role for g in generated}
    checks = {f"has_{role.value}": role in present_roles for role in IMAGE_ROLE_BY_SLOT.values()}
    report = {
        "sequence": [{"position": p, "role": slots[order[p].slot_id].role.value,
                      "slot_id": order[p].slot_id,
                      "visual_type": slots[order[p].slot_id].required_visual_type,
                      "score": order[p].validation_score}
                     for p in sorted(order)],
        "checks": checks,
        "auto_fixes": [],
        "valid": all(checks.values()) and len(order) == 10,
    }
    if not report["valid"]:
        failed = [k for k, v in checks.items() if not v]
        raise RuntimeError(f"Image sequence validation failed: {failed}. "
                           "The Phase-2 strategy validator should prevent this; regenerate the strategy.")
    return [order[p] for p in sorted(order)], report


def generate_all(db: Session, listing_id: str,
                 strategy: ImageStrategy) -> ImageRunResult:
    provider = get_provider()
    out_dir = Path(settings.storage_dir) / "generated" / listing_id
    generated = [generate_slot(db, listing_id, slot, provider, out_dir)
                 for slot in sorted(strategy.slots, key=lambda s: s.slot_id)]
    ordered, report = orchestrate_sequence(strategy, generated)
    # persist display order
    for g in ordered:
        db.query(ListingImage).filter(ListingImage.id == g.image_id).update(
            {"display_order": g.display_order})
    db.commit()
    return ImageRunResult(images=ordered, sequence_report=report)
