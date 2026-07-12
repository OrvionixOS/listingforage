"""
Stage 5 — Image Strategy Engine + Prompt Generation.

MANDATORY 10-SLOT SYSTEM — the complete Etsy digital-product gallery. Each
slot carries a FIXED conversion role (schemas.IMAGE_ROLE_BY_SLOT) plus intent,
psychological_stage, objective, required_visual_type, prompt_constraints, and
a structured ImagePrompt whose lighting / camera / environment / composition /
product-focus / realism fields are hard requirements enforced by schema.

Slot roles (fixed order, spec-mandated):
  1 hero · 2 overview · 3 value_breakdown · 4 lifestyle_mockup ·
  5 alternate_use_case · 6 close_up_detail · 7 how_it_works ·
  8 sizes_formats_compatibility · 9 benefits_transformation · 10 brand_cta

Each slot must ALSO claim a DIFFERENT primary buyer uncertainty (schema-
enforced). The Image Strategy Validator (validator.py) audits the result and
this module accepts its feedback for regeneration passes.
"""
from __future__ import annotations

from ..schemas import (BDEOutput, CategoryClassification, ImageStrategy,
                       ProductAnalysis, ProductCategory)
from .llm import structured_call

SLOT_BLUEPRINTS: dict[ProductCategory, str] = {
    ProductCategory.printable_art: """
1 hero (CTR/attention) hero_macro — the print full bleed, colors true, legible at 180px.
2 overview (CLARITY/interpretation) file_grid — every print/size/format in the download, labeled.
3 value_breakdown (VALUE/value_justification) variant_grid — sizes included (8x10, 16x20, A4...) with per-size math.
4 lifestyle_mockup (CONTEXT/usage_imagination) lifestyle_scene — framed and hung in a real, styled room.
5 alternate_use_case (CONTEXT/usage_imagination) lifestyle_scene — a second room/pairing (nursery vs office, gallery wall grouping).
6 close_up_detail (TRUST/trust) zoom_proof — 100% zoom crop proving print resolution (300 DPI callout).
7 how_it_works (CLARITY/interpretation) info_card — download → print → frame steps.
8 sizes_formats_compatibility (CLARITY/interpretation) size_chart — exact sizes/aspect ratios + file formats (JPG/PDF).
9 benefits_transformation (VALUE/value_justification) lifestyle_scene — the room transformation this art delivers.
10 brand_cta (CONVERSION/final_objection) info_card — license terms, shop brand, clear call to action.""",
    ProductCategory.digital_planner: """
1 hero (CTR/attention) hero_macro — planner cover/hero spread, bold and legible at 180px.
2 overview (CLARITY/interpretation) file_grid — every page/section in the planner, labeled and counted.
3 value_breakdown (VALUE/value_justification) variant_grid — page count, sections, bonus pages with per-item value.
4 lifestyle_mockup (CONTEXT/usage_imagination) mockup_in_use — planner open on an iPad/GoodNotes, being used.
5 alternate_use_case (CONTEXT/usage_imagination) mockup_in_use — printed-and-used alternative, or a second use case (work vs personal).
6 close_up_detail (TRUST/trust) zoom_proof — hyperlink/tab navigation close-up proving real functionality.
7 how_it_works (CLARITY/interpretation) info_card — import → navigate → use steps (app names explicit).
8 sizes_formats_compatibility (CLARITY/interpretation) info_card — supported apps (GoodNotes/Notability/print), file format.
9 benefits_transformation (VALUE/value_justification) info_card — the organization/time-saved transformation.
10 brand_cta (CONVERSION/final_objection) info_card — license, refill policy, shop brand + call to action.""",
    ProductCategory.template: """
1 hero (CTR/attention) hero_macro — best template design, full bleed, legible at 180px.
2 overview (CLARITY/interpretation) file_grid — every template/slide/variant included, labeled.
3 value_breakdown (VALUE/value_justification) variant_grid — count of templates/color variations with per-item math.
4 lifestyle_mockup (CONTEXT/usage_imagination) mockup_in_use — template shown customized inside the actual tool (Canva UI).
5 alternate_use_case (CONTEXT/usage_imagination) mockup_in_use — a second platform/use (Instagram vs print, or a different niche).
6 close_up_detail (TRUST/trust) zoom_proof — close-up of typography/layout quality proving polish.
7 how_it_works (CLARITY/interpretation) info_card — open link → edit text/colors → download steps.
8 sizes_formats_compatibility (CLARITY/interpretation) info_card — tool required (Canva free/pro), fonts, dimensions.
9 benefits_transformation (VALUE/value_justification) comparison_split — before/after: generic vs this template's professional result.
10 brand_cta (CONVERSION/final_objection) info_card — commercial license, shop brand, call to action.""",
    ProductCategory.invitation: """
1 hero (CTR/attention) hero_macro — invitation with a REAL sample name/date, legible at 180px.
2 overview (CLARITY/interpretation) file_grid — every included piece (invite, RSVP, thank-you card), labeled.
3 value_breakdown (VALUE/value_justification) variant_grid — matching suite pieces included, per-item value.
4 lifestyle_mockup (CONTEXT/usage_imagination) lifestyle_scene — invitation in a real gifting/event-planning moment.
5 alternate_use_case (CONTEXT/usage_imagination) variant_grid — color/style variant options for a different event tone.
6 close_up_detail (TRUST/trust) zoom_proof — personalization/print-quality close-up.
7 how_it_works (CLARITY/interpretation) info_card — choose → enter details → preview → receive/print steps.
8 sizes_formats_compatibility (CLARITY/interpretation) size_chart — print sizes, editing platform (Canva/Corjl), formats.
9 benefits_transformation (VALUE/value_justification) lifestyle_scene — the event feeling/impression this creates.
10 brand_cta (CONVERSION/final_objection) info_card — deadline + proof-approval policy, shop brand, call to action.""",
    ProductCategory.svg_cut_file: """
1 hero (CTR/attention) hero_macro — the cut design shown clean and bold, legible at 180px.
2 overview (CLARITY/interpretation) file_grid — every file format included (svg/dxf/eps/png), labeled.
3 value_breakdown (VALUE/value_justification) variant_grid — design count/variations with per-item math.
4 lifestyle_mockup (CONTEXT/usage_imagination) mockup_in_use — design cut and applied to a real product (shirt, tumbler, sign).
5 alternate_use_case (CONTEXT/usage_imagination) mockup_in_use — a second craft application (vinyl decal vs laser wood).
6 close_up_detail (TRUST/trust) zoom_proof — clean-cut-edge close-up proving line quality.
7 how_it_works (CLARITY/interpretation) info_card — open in software → resize → cut steps (app names explicit).
8 sizes_formats_compatibility (CLARITY/interpretation) info_card — Cricut Design Space/Silhouette Studio/laser compatibility, formats.
9 benefits_transformation (VALUE/value_justification) lifestyle_scene — the finished craft project transformation.
10 brand_cta (CONVERSION/final_objection) info_card — commercial license, shop brand, call to action.""",
    ProductCategory.digital_bundle: """
1 hero (CTR/attention) hero_macro — best single asset from the bundle, legible at 180px.
2 overview (CLARITY/interpretation) file_grid — full contents grid, every item counted and labeled.
3 value_breakdown (VALUE/value_justification) variant_grid — "N items for $X = $Y each" explicit per-item math.
4 lifestyle_mockup (CONTEXT/usage_imagination) mockup_in_use — bundle assets used together in one real project.
5 alternate_use_case (CONTEXT/usage_imagination) mockup_in_use — a different project using different bundle assets.
6 close_up_detail (TRUST/trust) zoom_proof — quality close-up on a representative asset.
7 how_it_works (CLARITY/interpretation) info_card — download → unzip → use in [software] steps.
8 sizes_formats_compatibility (CLARITY/interpretation) info_card — all formats included, software compatibility.
9 benefits_transformation (VALUE/value_justification) comparison_split — bundle savings vs buying items individually.
10 brand_cta (CONVERSION/final_objection) info_card — commercial license, shop brand, call to action.""",
    ProductCategory.educational_product: """
1 hero (CTR/attention) hero_macro — the worksheet/resource cover page, legible at 180px.
2 overview (CLARITY/interpretation) file_grid — every worksheet/page included, labeled by topic.
3 value_breakdown (VALUE/value_justification) variant_grid — page/activity count, answer keys included, per-item value.
4 lifestyle_mockup (CONTEXT/usage_imagination) lifestyle_scene — resource in use at a desk/classroom table.
5 alternate_use_case (CONTEXT/usage_imagination) lifestyle_scene — home-school vs classroom use, or a second grade/age variant.
6 close_up_detail (TRUST/trust) zoom_proof — close-up proving print clarity and layout quality.
7 how_it_works (CLARITY/interpretation) info_card — download → print → use steps.
8 sizes_formats_compatibility (CLARITY/interpretation) info_card — grade/age range, format (PDF), answer key inclusion.
9 benefits_transformation (VALUE/value_justification) info_card — the specific learning outcome this delivers.
10 brand_cta (CONVERSION/final_objection) info_card — curriculum alignment note, shop brand, call to action.""",
    ProductCategory.pattern: """
1 hero (CTR/attention) hero_macro — the finished make, clean and bold, legible at 180px.
2 overview (CLARITY/interpretation) file_grid — every pattern piece/page included, labeled.
3 value_breakdown (VALUE/value_justification) variant_grid — sizes/variations included with per-item value.
4 lifestyle_mockup (CONTEXT/usage_imagination) lifestyle_scene — the finished project worn/displayed in real use.
5 alternate_use_case (CONTEXT/usage_imagination) variant_grid — a color/yarn/fabric variation of the same pattern.
6 close_up_detail (TRUST/trust) zoom_proof — stitch/seam close-up proving finished quality.
7 how_it_works (CLARITY/interpretation) info_card — skill level → materials → construction steps overview.
8 sizes_formats_compatibility (CLARITY/interpretation) size_chart — sizes/gauge, yardage/notions needed, file format.
9 benefits_transformation (VALUE/value_justification) comparison_split — raw materials vs finished, professional-looking result.
10 brand_cta (CONVERSION/final_objection) info_card — skill-level honesty note, shop brand, call to action.""",
}

SYSTEM_TEMPLATE = """You are the Image Strategy Engine of Etsy Listing AI
Studio — a product photographer, graphic designer, and buyer decision
simulation engine in one. Etsy gives ten image slots. Design the COMPLETE
gallery: EXACTLY 10 slots, one per fixed conversion role. Every slot is a
conversion instrument. Decoration is forbidden.

HARD RULES:
- slot_id 1-10 exactly once, each with its FIXED role in this exact order:
  1=hero 2=overview 3=value_breakdown 4=lifestyle_mockup 5=alternate_use_case
  6=close_up_detail 7=how_it_works 8=sizes_formats_compatibility
  9=benefits_transformation 10=brand_cta.
  Slot 1 (hero) is always the search thumbnail (intent CTR, stage attention,
  legible at 180px). Slot 10 (brand_cta) always closes the final objection and
  reinforces brand trust (intent CONVERSION).
- Each slot claims a DIFFERENT primary_uncertainty_id from the indexed
  uncertainty map — 10 slots, 10 different doubts, highest severities first.
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
  * at least two usage demonstrations (lifestyle_scene or mockup_in_use) —
    slots 4 and 5 (lifestyle_mockup, alternate_use_case) satisfy this
  * no psychological stage covered by more than 3 slots
  * at least 5 distinct intents and at least 6 distinct visual types across
    the 10 slots

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

CATEGORY BLUEPRINT (roles/order are FIXED — adapt required_visual_type,
objective, and prompt content to this specific product within each role):
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
    content += "\nDesign the complete 10-slot Etsy gallery image strategy."

    return structured_call(
        SYSTEM_TEMPLATE.format(blueprint=blueprint),
        content, ImageStrategy, max_tokens=16000, temperature=0.6,
    )
