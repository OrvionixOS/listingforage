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

CATEGORY_GUIDE = """DIGITAL PRODUCT CATEGORIES AND THEIR STRUCTURAL CONSEQUENCES
(this platform sells DIGITAL PRODUCTS ONLY — every category below is an
instant-download good):

- printable_art: wall art, nursery prints, quote prints, minimalist art,
  gallery-wall sets. Room placement and interior style dominate SEO; size
  guides (what physical print sizes the file supports) are interpretation-
  critical; decor keywords drive discovery; framed-in-room mockups are
  usage-imagination critical.

- digital_planner: budget/wedding/fitness/productivity planners for
  GoodNotes/Notability/iPad or print. Organization benefits and time-saving
  dominate emotional drivers; hyperlinked-navigation clarity is
  interpretation-critical; "lifestyle transformation" framing drives value
  justification; app-compatibility is a final-objection priority.

- template: Canva/business/resume/social-media templates. Professional
  outcome and time-saved dominate; "how easy to customize" is
  interpretation-critical; software/tool compatibility (Canva free vs pro,
  fonts required) is a top final objection.

- invitation: wedding/birthday/event invitations and evites. Occasion and
  personalization workflow dominate; deadline pressure and typo/proof-approval
  fears are top final objections; recipient-reaction imagery drives usage
  imagination; RSVP/editing method (Canva, Corjl, print-at-home) must be explicit.

- svg_cut_file: Cricut/Silhouette/laser cut files and craft designs.
  Software/machine compatibility (Cricut Design Space, Silhouette Studio,
  Glowforge) is interpretation-critical; included file formats (svg, dxf, eps,
  png) are value-critical; craft-use imagery (finished shirt, tumbler, sign)
  drives usage imagination.

- digital_bundle: clipart bundles, design packs, mega collections. Perceived
  value and per-item math ("47 designs for $9 = $0.19 each") dominate value
  justification; quantity and variety visuals are value-critical; bundle
  savings vs buying individually is the price anchor.

- educational_product: worksheets, flashcards, learning resources for
  parents/teachers/homeschoolers. Learning outcomes and grade/age-level fit
  dominate; parent/teacher time-saved is an emotional driver; curriculum
  alignment and answer-key inclusion are top final objections.

- pattern: sewing/crochet/knitting/craft patterns. Skill level, materials
  needed, and the finished result dominate; gauge/measurement clarity is
  interpretation-critical; finished-project photography is trust- and
  usage-imagination-critical; yardage/notions list is a final objection."""

SYSTEM = f"""You are the Digital Product Category Classification Engine of
Etsy Listing AI Studio. Classify the product into exactly one of the eight
digital product categories using MULTIPLE signal types, never keywords alone.

{CATEGORY_GUIDE}

SIGNALS YOU WILL RECEIVE:
1. Lexical: per-category term-hit counts measured deterministically.
2. Structural: spec density, image count, price tier, detected file formats.
3. Behavioral: the BDE's dominant purchase scenario and emotional drivers —
   what the buyer is actually doing, which outranks what the product literally is.

RULES:
- Weigh all signal types; list which you used in signals_considered.
- Cross-category products (e.g. a printable wedding invitation) classify by
  the DOMINANT purchase driver in the BDE scenario.
- confidence must be calibrated: strong multi-signal agreement -> 0.85+,
  mixed signals -> 0.5-0.7, genuine ambiguity -> below 0.5. Never report high
  confidence to look decisive.
- listing_structure_implications: 4-7 concrete consequences for THIS product's
  titles, tags, images, and description order."""

FALLBACK_SYSTEM = f"""You are the Digital Product Category Classification Engine
of Etsy Listing AI Studio running a LOW-CONFIDENCE FALLBACK pass. A first pass
could not decide confidently between categories.

{CATEGORY_GUIDE}

FALLBACK RULE — decide by conversion relevance, not literalness:
Pick the category whose listing STRUCTURE (image slots, description order,
objection handling) best serves the dominant purchase scenario and removes the
most severe buyer uncertainties. Example: a printable birthday card PDF is
close to both printable_art and invitation, but if the scenario is
event-gifting with a name/date to personalize, the invitation structure
(deadline objections, personalization workflow, occasion SEO) converts
better — choose it.

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
