"""
AI Orchestration Layer — end-to-end pipeline enforcement.

Enforced flow:
  1. Input ingestion + deterministic signal extraction
  2. Product analysis (incl. "who buys this and why")
  3. Buyer Decision Engine (analysis + computed stage scores)
  4. Digital Product Category classification (multi-signal, confidence fallback)
  5. Listing strategy generation (titles, SEO, description architecture)
  6. Competitor intelligence (market positioning + how this listing wins)
  7. Pricing strategy (price point, psychological pricing, bundles/upsells)
  8. Image strategy generation → Image Strategy Validator
     (auto-regenerate with validator feedback until valid, bounded) — the
     complete 10-image Etsy gallery
  9. Conversion scoring
  10. Output format enforcement

With a DB session, three more steps generate the actual 10 gallery images,
pixel-validate them, and sequence them (steps 11-13 below).

Guarantees:
- Every step's output is schema-validated before the next step runs.
- The image strategy is regenerated with precise validator feedback until it
  passes, up to MAX_IMAGE_ATTEMPTS; a still-invalid strategy fails safe with a
  full validation report rather than shipping a weak listing.
- Final assembly re-verifies all required output keys (fail-safe: a missing
  step raises before anything is persisted as 'complete').
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..schemas import FINAL_OUTPUT_REQUIRED_KEYS, ListingOutput
from . import (buyer_decision_engine, category_classifier,
               competitor_intelligence, image_strategy, listing_strategy,
               output_formatter, pricing_strategy, product_analysis, scoring,
               signals, validator)

log = logging.getLogger("listingforge.pipeline")

MAX_IMAGE_ATTEMPTS = 3

PIPELINE_STEPS = (
    "input_ingestion", "product_analysis", "buyer_decision_engine",
    "category_classification", "listing_strategy", "competitor_intelligence",
    "pricing_strategy", "image_strategy_validated",
    "conversion_scoring", "output_formatting",
)

# Phase 3 steps appended when a DB session is provided (image generation needs
# persistence for version history and generation logs):
PHASE3_STEPS = ("image_generation", "image_validation", "image_orchestration")


class PipelineError(RuntimeError):
    """Raised when a step fails or the pipeline cannot produce a valid listing."""
    def __init__(self, step: str, message: str):
        self.step = step
        super().__init__(f"[{step}] {message}")


@dataclass
class PipelineResult:
    output: ListingOutput
    usage: dict = field(default_factory=lambda: {"tokens_in": 0, "tokens_out": 0})
    stage_log: list[str] = field(default_factory=list)


def _acc(total: dict, delta: dict) -> None:
    total["tokens_in"] += delta.get("tokens_in", 0)
    total["tokens_out"] += delta.get("tokens_out", 0)


def generate_listing(
    title: str,
    description: str,
    price: float | None = None,
    notes: str | None = None,
    image_paths: list[str] | None = None,
    db=None,
    listing_id: str | None = None,
    performance_context: str = "",
    brand_context: str = "",
    vision_context: str = "",
    on_step=None,
) -> PipelineResult:
    """Full pipeline. When `db` and `listing_id` are provided, the Phase 3
    image generation → validation → orchestration steps run and persist
    images/logs; `performance_context` closes the analytics feedback loop."""
    image_paths = image_paths or []
    usage = {"tokens_in": 0, "tokens_out": 0}
    done: list[str] = []
    from pathlib import Path as _Path
    filenames = [_Path(p).name for p in image_paths]

    total_steps = len(PIPELINE_STEPS) + (len(PHASE3_STEPS) if db is not None else 0)

    def step(name: str):
        log.info("pipeline step %d/%d: %s", len(done) + 1, total_steps, name)
        done.append(name)
        if on_step is not None:
            try:
                on_step(name, len(done), total_steps)
            except Exception:
                log.warning("on_step callback failed", exc_info=True)

    # 1 — input ingestion + deterministic signals
    step("input_ingestion")
    if not (title or "").strip() or not (description or "").strip():
        raise PipelineError("input_ingestion", "Title and description are required.")
    sig = signals.extract(title, description, price, len(image_paths), filenames)

    # 2 — product analysis
    step("product_analysis")
    try:
        analysis, u = product_analysis.run(title, description, price, notes, image_paths)
    except Exception as exc:
        raise PipelineError("product_analysis", str(exc)) from exc
    _acc(usage, u)

    # 3 — Buyer Decision Engine
    step("buyer_decision_engine")
    try:
        ctx = (performance_context
               + ("\n\n" + brand_context if brand_context else "")
               + ("\n\n" + vision_context if vision_context else "")).strip()
        bde, u = buyer_decision_engine.run(analysis, sig, ctx)
    except Exception as exc:
        raise PipelineError("buyer_decision_engine", str(exc)) from exc
    _acc(usage, u)

    # 4 — category classification (multi-signal + confidence fallback)
    step("category_classification")
    try:
        classification, u = category_classifier.run(analysis, bde, sig)
    except Exception as exc:
        raise PipelineError("category_classification", str(exc)) from exc
    _acc(usage, u)

    # 5 — listing strategy
    step("listing_strategy")
    try:
        listing, u = listing_strategy.run(analysis, bde, classification)
    except Exception as exc:
        raise PipelineError("listing_strategy", str(exc)) from exc
    _acc(usage, u)

    # 6 — competitor intelligence (market research + positioning)
    step("competitor_intelligence")
    try:
        competitor_intel, u = competitor_intelligence.run(analysis, bde, classification, listing)
    except Exception as exc:
        raise PipelineError("competitor_intelligence", str(exc)) from exc
    _acc(usage, u)

    # 7 — pricing strategy (grounded in the live market snapshot when available)
    step("pricing_strategy")
    try:
        pricing, u = pricing_strategy.run(analysis, bde, classification,
                                          competitor_intel=competitor_intel)
    except Exception as exc:
        raise PipelineError("pricing_strategy", str(exc)) from exc
    _acc(usage, u)

    # 8 — image strategy: generate → validate → regenerate until valid
    step("image_strategy_validated")
    all_feedback: list[str] = []
    checks = []
    images = None
    valid = False
    attempts = 0
    feedback: list[str] | None = None
    while attempts < MAX_IMAGE_ATTEMPTS and not valid:
        attempts += 1
        try:
            images, u = image_strategy.run(analysis, bde, classification,
                                           regeneration_feedback=feedback)
            _acc(usage, u)
        except Exception as exc:
            # schema rejection counts as a failed attempt with feedback
            feedback = [f"Schema rejection: {exc}"]
            all_feedback.extend(feedback)
            log.warning("image strategy attempt %d schema-rejected: %s", attempts, exc)
            continue
        valid, checks, feedback = validator.validate(images, bde)
        if not valid:
            all_feedback.extend(feedback)
            log.warning("image strategy attempt %d rejected by validator: %s",
                        attempts, feedback)
    if images is None or not valid:
        raise PipelineError(
            "image_strategy_validated",
            f"Image strategy failed validation after {attempts} attempts. "
            f"Outstanding issues: {all_feedback[-6:]}")
    report = validator.build_report(valid, checks, attempts, all_feedback)

    # 9 — conversion scoring (deterministic)
    step("conversion_scoring")
    try:
        scores = scoring.compute(bde, listing, images, report)
    except Exception as exc:
        raise PipelineError("conversion_scoring", str(exc)) from exc

    # 10 — output format enforcement
    step("output_formatting")
    try:
        output = output_formatter.run(analysis, bde, classification, listing,
                                      images, competitor_intel, pricing, report, scores)
    except Exception as exc:
        raise PipelineError("output_formatting", str(exc)) from exc

    # 11-13 — Phase 3: image generation → pixel validation → orchestration
    image_run = None
    if db is not None and listing_id is not None:
        step("image_generation")
        from ..imaging import generator as image_generator
        try:
            image_run = image_generator.generate_all(db, listing_id, images)
        except Exception as exc:
            raise PipelineError("image_generation", str(exc)) from exc
        step("image_validation")   # performed inside generate_all per attempt
        step("image_orchestration")
        output.export_formats["image_sequence"] = image_run.sequence_report
        # attach generated-image metadata into the final output for the UI
        output.export_formats["generated_images"] = [
            {"slot_id": g.slot_id, "image_id": g.image_id,
             "final_image_url": f"/api/listings/{listing_id}/images/{g.slot_id}/file",
             "generation_prompt": g.generation_prompt,
             "style_profile": g.style_profile,
             "validation_score": g.validation_score,
             "scores": g.scores,
             "regeneration_count": g.regeneration_count,
             "display_order": g.display_order}
            for g in image_run.images]

    # fail-safe: verify every enforced step ran and every required key exists
    required = PIPELINE_STEPS + (PHASE3_STEPS if (db is not None and listing_id is not None) else ())
    missing_steps = [s for s in required if s not in done]
    if missing_steps:
        raise PipelineError("pipeline_enforcement", f"Steps skipped: {missing_steps}")
    dumped = output.model_dump()
    missing_keys = [k for k in FINAL_OUTPUT_REQUIRED_KEYS if k not in dumped]
    if missing_keys:
        raise PipelineError("pipeline_enforcement", f"Final output missing keys: {missing_keys}")

    return PipelineResult(output=output, usage=usage, stage_log=done)
