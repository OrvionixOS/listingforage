"""
Stage 5 — Image Strategy Engine + Prompt Generation (Phase 2).

MANDATORY 7-SLOT SYSTEM. Each slot carries: slot_id, intent,
psychological_stage, objective, required_visual_type, prompt_constraints, and
a structured ImagePrompt whose lighting / camera / environment / composition /
product-focus / realism fields are hard requirements enforced by schema.

Each slot must claim a DIFFERENT primary buyer uncertainty (schema-enforced).
The Image Strategy Validator (validator.py) audits the result and this module
accepts its feedback for regeneration passes.
"""
from __future__ import annotations

from ..schemas import (BDEOutput, CategoryClassification, ImageStrategy,
                       ProductAnalysis, ProductCategory)
from .llm import structured_call

SLOT_BLUEPRINTS: dict[ProductCategory, str] = {
    ProductCategory.digital_product: """
1 CTR/attention hero_macro — single striking asset full bleed, legible at 180px.
2 CLARITY/interpretation file_grid — every file with count/format/size labels.
3 TRUST/trust zoom_proof — 100% zoom crop proving resolution (300 DPI callout).
4 CLARITY/interpretation tiling_demo or spec visual for the top clarity doubt.
5 CONTEXT/usage_imagination mockup_in_use — files applied in real work.
6 VALUE/value_justification variant_grid — full variety + per-item math cue.
7 CONVERSION/final_objection info_card — license / how-it-works / top blocker.""",
    ProductCategory.physical_product: """
1 CTR/attention hero_macro — clean high-contrast hero, item fills frame.
2 CLARITY/interpretation scale_reference — item next to hand/common object or
  dimension overlay.
3 TRUST/trust zoom_proof — macro craftsmanship detail.
4 CONTEXT/usage_imagination lifestyle_scene — real environment.
5 VALUE/value_justification variant_grid or what's-included flat lay.
6 TRUST/trust process_shot — maker's hands, studio, proving handmade.
7 CONVERSION/final_objection info_card — packaging + shipping/care.""",
    ProductCategory.print_on_demand: """
1 CTR/attention hero_macro — best-selling variant, model or styled flat.
2 CLARITY/interpretation size_chart — print placement + sizing overlay.
3 CONTEXT/usage_imagination lifestyle_scene — wear/use shot matching persona.
4 VALUE/value_justification variant_grid — all colors/sizes.
5 TRUST/trust zoom_proof — fabric/print texture close-up, honest.
6 CLARITY/interpretation comparison_split — artwork detail isolated.
7 CONVERSION/final_objection info_card — sizing guide + care + fulfillment time.""",
    ProductCategory.gift_personalized: """
1 CTR/attention hero_macro — personalization visible with a REAL name.
2 CLARITY/interpretation info_card — personalization steps (choose→enter→preview→receive).
3 CONTEXT/usage_imagination lifestyle_scene — gifting moment / occasion setting.
4 TRUST/trust zoom_proof — personalization quality close-up.
5 VALUE/value_justification unboxing — gift packaging + everything included.
6 CLARITY/interpretation variant_grid — font/color/style options.
7 CONVERSION/final_objection info_card — deadline + proof-approval policy.""",
    ProductCategory.saas_tool: """
1 CTR/attention hero_macro — hero UI screenshot with one bold outcome line.
2 CLARITY/interpretation info_card — access model (duration, seats, delivery).
3 CONTEXT/usage_imagination mockup_in_use — tool inside a real workflow.
4 TRUST/trust comparison_split — results/social-proof visual.
5 VALUE/value_justification variant_grid — feature/plan comparison.
6 CLARITY/interpretation info_card — 3-step onboarding strip.
7 CONVERSION/final_objection info_card — refund/access/support policy.""",
}

SYSTEM_TEMPLATE = """You are the Image Strategy Engine of ListingForge AI — a
buyer decision simulation engine. Etsy gives ten image slots; the first seven
do all conversion work. Design EXACTLY 7 slots. Every slot is a conversion
instrument. Decoration is forbidden.

HARD RULES:
- slot_id 1-7 exactly once. Slot 1 is always the search thumbnail (intent CTR,
  stage attention, legible at 180px). Slot 7 always kills the top remaining
  final objection (intent CONVERSION).
- Each slot claims a DIFFERENT primary_uncertainty_id from the indexed
  uncertainty map — 7 slots, 7 different doubts, highest severities first.
  secondary_uncertainty_ids may overlap.
- objective: state the doubt in plain language (paraphrase the map item).
- required_visual_type: one concrete format (hero_macro, file_grid, zoom_proof,
  tiling_demo, lifestyle_scene, scale_reference, variant_grid, process_shot,
  info_card, mockup_in_use, comparison_split, size_chart, unboxing).
- prompt_constraints: 2-4 slot-specific rules (e.g. "must show a real printed
  sample, not a screen render", "dimension overlay must use inches AND cm").
- COVERAGE REQUIREMENTS the validator will reject you on:
  * at least one TRUST-intent slot with a quality-proof visual
  * at least one slot resolving scale/what-you-get clarity
    (scale_reference, file_grid, size_chart, or dimension-overlay visual)
  * at least one usage demonstration (lifestyle_scene or mockup_in_use)
  * no psychological stage covered by more than 2 slots
  * at least 4 distinct intents and at least 4 distinct visual types across
    the 7 slots

PROMPT REQUIREMENTS (every prompt object, all fields mandatory):
- subject: the exact scene, specific to THIS product's materials and colors.
- lighting: source, quality, direction (e.g. "large softbox 45° camera-left,
  soft specular highlights, gentle falloff").
- camera: lens/focal length, angle, aperture feel (e.g. "100mm macro, f/5.6,
  slight top-down 15°").
- environment: the set (e.g. "honed black slate surface, seamless charcoal
  backdrop").
- composition: framing rules, negative space, focal hierarchy.
- product_focus: explicit instruction keeping the product the hero of frame.
- realism_constraint: honest materials, true scale, no CGI plasticity, no
  exaggerated gloss.
- text_overlays: exact copy, max 6 words each, only where the slot needs them.
- negative: failure modes to avoid.
Vague or artistic-only language ("beautiful", "stunning composition") is
rejected. Every prompt is automatically suffixed with the clause
"Etsy conversion optimized, designed to reduce buyer uncertainty".

CATEGORY BLUEPRINT (adapt to this product; reorder slots 2-6 when the
uncertainty map demands):
{blueprint}"""


def run(analysis: ProductAnalysis, bde: BDEOutput,
        classification: CategoryClassification,
        regeneration_feedback: list[str] | None = None) -> tuple[ImageStrategy, dict]:
    blueprint = SLOT_BLUEPRINTS[classification.category]
    indexed = "\n".join(
        f"[id={u.id}] ({u.stage.value}, severity {u.severity}) {u.uncertainty} "
        f"— resolvable by: {', '.join(u.resolvable_by)}"
        for u in bde.buyer_uncertainty_map
    )
    trust_gaps = "\n".join(
        f"- {g.gap} (sev {g.severity}) → remedy: {g.remedy}"
        for g in bde.trust_gap_analysis
    )
    content = (
        f"PRODUCT ANALYSIS:\n{analysis.model_dump_json(indent=1)}\n\n"
        f"BUYER UNCERTAINTY MAP (indexed — claim primary ids from here):\n{indexed}\n\n"
        f"TRUST GAP ANALYSIS:\n{trust_gaps}\n\n"
        f"CONVERSION BLOCKERS:\n- " + "\n- ".join(bde.conversion_blockers) + "\n\n"
        f"EMOTIONAL DRIVERS:\n- " + "\n- ".join(bde.emotional_drivers) + "\n\n"
        f"DOMINANT PURCHASE SCENARIO: {bde.dominant_purchase_scenario}\n"
    )
    if regeneration_feedback:
        content += (
            "\nPREVIOUS ATTEMPT REJECTED BY THE IMAGE STRATEGY VALIDATOR.\n"
            "You MUST fix every one of these failures:\n- "
            + "\n- ".join(regeneration_feedback) + "\n"
        )
    content += "\nDesign the 7-slot image strategy."

    return structured_call(
        SYSTEM_TEMPLATE.format(blueprint=blueprint),
        content, ImageStrategy, max_tokens=12000, temperature=0.6,
    )
