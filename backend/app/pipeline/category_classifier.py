"""
Stage 3 — Category Classification Engine (Phase 2).

Multi-signal classification:
  Signal A — lexical term hits per category (deterministic, from signals.py)
  Signal B — structural properties (spec density, personalization language,
             price tier, image count)
  Signal C — the BDE's dominant purchase scenario and emotional drivers
  Signal D — model judgment over all of the above

Confidence protocol:
  - The model must report calibrated confidence.
  - If confidence < 0.6, a FALLBACK pass runs: the model must choose the most
    CONVERSION-RELEVANT category (the one whose listing structure best serves
    the dominant purchase scenario), not the most literal one, and document
    the fallback_reasoning.
"""
from __future__ import annotations

from ..config import get_settings
from ..schemas import BDEOutput, CategoryClassification, ProductAnalysis
from .llm import structured_call
from .signals import InputSignals

settings = get_settings()

CATEGORY_GUIDE = """CATEGORIES AND THEIR STRUCTURAL CONSEQUENCES:

- physical_product: handmade/sourced tangible goods shipped to the buyer.
  Dimensions and materials up front; shipping time is a final-objection
  priority; craftsmanship close-ups are trust-critical.

- digital_product: instant-download files (printables, templates, digital
  paper, planners, SVGs). "INSTANT DOWNLOAD" disambiguation is
  interpretation-critical; formats/sizes/compatibility explicit; what's-included
  grid is value-critical; licensing dominates final objections.

- print_on_demand: designs fulfilled by a POD partner (shirts, mugs, posters).
  Size charts and print placement are final-objection priorities; mockup
  honesty is a trust issue; fulfillment time must be disclosed.

- gift_personalized: items whose PRIMARY purchase driver is gifting or
  customization. Personalization workflow clarity is interpretation-critical;
  occasion keywords dominate SEO; deadline + typo fears are top objections;
  recipient-reaction imagery drives usage imagination.

- saas_tool: software subscriptions/tools sold via Etsy. Access model and
  duration clarity dominate; screenshots replace photography; refund/access
  objections dominate."""

SYSTEM = f"""You are the Category Classification Engine of ListingForge AI.
Classify the product into exactly one category using MULTIPLE signal types,
never keywords alone.

{CATEGORY_GUIDE}

SIGNALS YOU WILL RECEIVE:
1. Lexical: per-category term-hit counts measured deterministically.
2. Structural: spec density, image count, price tier, personalization language.
3. Behavioral: the BDE's dominant purchase scenario and emotional drivers —
   what the buyer is actually doing, which outranks what the product literally is.

RULES:
- Weigh all signal types; list which you used in signals_considered.
- Cross-category products (e.g. a personalized digital portrait) classify by
  the DOMINANT purchase driver in the BDE scenario.
- confidence must be calibrated: strong multi-signal agreement -> 0.85+,
  mixed signals -> 0.5-0.7, genuine ambiguity -> below 0.5. Never report high
  confidence to look decisive.
- listing_structure_implications: 4-7 concrete consequences for THIS product's
  titles, tags, images, and description order."""

FALLBACK_SYSTEM = f"""You are the Category Classification Engine of ListingForge
AI running a LOW-CONFIDENCE FALLBACK pass. A first pass could not decide
confidently between categories.

{CATEGORY_GUIDE}

FALLBACK RULE — decide by conversion relevance, not literalness:
Pick the category whose listing STRUCTURE (image slots, description order,
objection handling) best serves the dominant purchase scenario and removes the
most severe buyer uncertainties. Example: a "custom pet portrait PDF" is
literally a digital product, but if the scenario is gift-buying, the
gift_personalized structure (occasion SEO, deadline objections,
recipient-reaction imagery) converts better — choose it.

You MUST fill fallback_reasoning: name the literal candidate, the chosen
conversion-relevant category, and why the chosen structure wins for this
scenario. Report your true confidence in the FALLBACK decision (it may stay
below 0.6; do not inflate it)."""


def _content(analysis: ProductAnalysis, bde: BDEOutput, signals: InputSignals,
             prior: CategoryClassification | None = None) -> str:
    parts = [
        f"PRODUCT ANALYSIS:\n{analysis.model_dump_json(indent=1)}",
        f"LEXICAL SIGNALS (term hits per category): {signals.category_hits}",
        ("STRUCTURAL SIGNALS: "
         f"spec_hits={signals.spec_hits}, image_count={signals.image_count}, "
         f"desc_len={signals.desc_len}, has_price={signals.has_price}"),
        f"BDE DOMINANT PURCHASE SCENARIO: {bde.dominant_purchase_scenario}",
        f"BDE EMOTIONAL DRIVERS: {bde.emotional_drivers}",
        f"BDE TOP BLOCKERS: {bde.conversion_blockers}",
    ]
    if prior is not None:
        parts.append(
            "FIRST-PASS RESULT (LOW CONFIDENCE):\n"
            f"category={prior.category.value}, confidence={prior.confidence}, "
            f"reasoning={prior.reasoning}"
        )
    parts.append("Classify this product.")
    return "\n\n".join(parts)


def run(analysis: ProductAnalysis, bde: BDEOutput,
        signals: InputSignals) -> tuple[CategoryClassification, dict]:
    usage_total = {"tokens_in": 0, "tokens_out": 0}

    result, usage = structured_call(
        SYSTEM, _content(analysis, bde, signals), CategoryClassification,
        model=settings.model_fast, max_tokens=1800, temperature=0.2)
    usage_total["tokens_in"] += usage["tokens_in"]
    usage_total["tokens_out"] += usage["tokens_out"]

    if result.confidence < 0.6:
        # Fallback: conversion-relevance decision with the stronger model.
        result, usage = structured_call(
            FALLBACK_SYSTEM, _content(analysis, bde, signals, prior=result),
            CategoryClassification, model=settings.model_reasoning,
            max_tokens=1800, temperature=0.3)
        usage_total["tokens_in"] += usage["tokens_in"]
        usage_total["tokens_out"] += usage["tokens_out"]
        if not result.fallback_reasoning:
            result.fallback_reasoning = (
                "Low first-pass confidence triggered conversion-relevance fallback: "
                + result.reasoning
            )

    return result, usage_total
