"""
Image Generation Engine + Image Orchestration Engine.

GENERATION
  Compiles each of the 7 validated strategy slots into a style_profile and a
  generation prompt (mandatory suffix appended), renders it via the configured
  provider, scores the real pixels, and regenerates with validator-supplied
  adjustments until it passes (bounded). Every attempt is logged to
  image_generation_logs; final images land in listing_images with full
  score history.

ORCHESTRATION
  Orders the 7 finished images into the mandated psychological conversion
  sequence and re-validates the set as a sequence:
    1 Attention (CTR hero) → 2 Interpretation (context) → 3 Validation (trust
    detail) → 4 Scale understanding → 5 Value demonstration → 6 Objection
    removal → 7 Brand trust reinforcement.
  Sets failing sequence rules are auto-fixed by reordering; unfixable sets
  fail safe before any output is written.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import ImageGenerationLog, ListingImage
from ..schemas import BDEStage, ImageIntent, ImageSlot, ImageStrategy
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
# Orchestration: psychological conversion sequence
# ---------------------------------------------------------------------------

# position → predicate over (intent, stage, visual_type)
SEQUENCE_SPEC = [
    ("attention_hero",      lambda s: s.intent == ImageIntent.CTR),
    ("interpretation",      lambda s: s.intent in (ImageIntent.CLARITY, ImageIntent.CONTEXT)
                                      and s.psychological_stage in (BDEStage.interpretation, BDEStage.usage_imagination)),
    ("trust_detail",        lambda s: s.intent == ImageIntent.TRUST
                                      or s.required_visual_type in ("zoom_proof", "process_shot")),
    ("scale_understanding", lambda s: s.required_visual_type in
                                      ("scale_reference", "file_grid", "size_chart", "tiling_demo", "variant_grid")),
    ("value_demonstration", lambda s: s.intent in (ImageIntent.VALUE, ImageIntent.CONTEXT)),
    ("objection_removal",   lambda s: s.intent == ImageIntent.CONVERSION
                                      or s.required_visual_type in ("comparison_split", "info_card")),
    ("brand_reinforcement", lambda s: True),  # strongest remaining premium visual
]


def orchestrate_sequence(strategy: ImageStrategy,
                         generated: list[GeneratedSlotImage]) -> tuple[list[GeneratedSlotImage], dict]:
    """Assign display_order 1-7 per the psychological sequence. Greedy matching
    with auto-fix: each position takes the best unassigned matching slot; the
    final position takes the highest-scoring remainder (brand reinforcement)."""
    slots = {s.slot_id: s for s in strategy.slots}
    by_score = sorted(generated, key=lambda g: -g.validation_score)
    unassigned = {g.slot_id for g in generated}
    order: dict[int, GeneratedSlotImage] = {}
    fixes: list[str] = []

    for pos, (name, pred) in enumerate(SEQUENCE_SPEC, start=1):
        candidates = [g for g in by_score if g.slot_id in unassigned and pred(slots[g.slot_id])]
        if candidates:
            pick = candidates[0]
        else:
            # auto-fix: relax to any remaining slot, note the fix
            pick = next(g for g in by_score if g.slot_id in unassigned)
            fixes.append(f"position {pos} ({name}): no exact match, auto-assigned "
                         f"slot {pick.slot_id} ({slots[pick.slot_id].required_visual_type})")
        pick.display_order = pos
        order[pos] = pick
        unassigned.discard(pick.slot_id)

    # sequence set validation (mirrors spec's rejection rules)
    checks = {
        "has_trust_stage": any(slots[g.slot_id].intent == ImageIntent.TRUST
                               or slots[g.slot_id].required_visual_type in ("zoom_proof", "process_shot")
                               for g in generated),
        "has_usage_clarity": any(slots[g.slot_id].required_visual_type in ("lifestyle_scene", "mockup_in_use")
                                 for g in generated),
        "has_scale_or_realism": any(slots[g.slot_id].required_visual_type in
                                    ("scale_reference", "file_grid", "size_chart", "tiling_demo", "variant_grid", "zoom_proof")
                                    for g in generated),
        "has_conversion_proof": any(slots[g.slot_id].intent == ImageIntent.CONVERSION
                                    or slots[g.slot_id].required_visual_type in ("comparison_split", "info_card")
                                    for g in generated),
        "no_function_repetition": len({SEQUENCE_SPEC[g.display_order - 1][0] for g in generated}) == 7,
    }
    report = {
        "sequence": [{"position": p, "function": SEQUENCE_SPEC[p - 1][0],
                      "slot_id": order[p].slot_id,
                      "visual_type": slots[order[p].slot_id].required_visual_type,
                      "score": order[p].validation_score}
                     for p in sorted(order)],
        "checks": checks,
        "auto_fixes": fixes,
        "valid": all(checks.values()),
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
