"""Stage 8 — Output Format Enforcer. Deterministic rendering + shape enforcement."""
from __future__ import annotations

import csv
import io

from ..schemas import (BDEOutput, CategoryClassification, CompetitorIntelligence,
                       ConversionScores, ImageStrategy, ListingOutput,
                       ListingStrategy, PricingStrategy, ProductAnalysis,
                       ValidationReport)


def _best_title(listing: ListingStrategy):
    return next((t for t in listing.titles if t.is_best), listing.titles[0])


def _etsy_paste_ready(listing: ListingStrategy, pricing: PricingStrategy) -> str:
    parts = [_best_title(listing).title, "", f"PRICE: ${pricing.recommended_price:.2f}", ""]
    for block in listing.description_blocks:
        parts += [block.heading.upper(), block.body, ""]
    if listing.faq_items:
        parts.append("FAQ")
        for item in listing.faq_items:
            parts += [f"Q: {item.get('question', '')}", f"A: {item.get('answer', '')}", ""]
    parts += ["TAGS (copy into the 13 tag fields):", ", ".join(listing.tags)]
    if listing.materials:
        parts += ["", "MATERIALS:", ", ".join(listing.materials)]
    return "\n".join(parts).strip()


def _competitor_brief(intel: CompetitorIntelligence) -> str:
    lines = ["COMPETITOR INTELLIGENCE", "=" * 40, "",
             "Best-selling patterns:"]
    lines += [f"- {p}" for p in intel.best_selling_patterns]
    lines += ["", "Competitor weaknesses:"] + [f"- {w}" for w in intel.competitor_weaknesses]
    lines += ["", "Missed opportunities this listing claims:"] + [f"- {m}" for m in intel.missed_opportunities]
    lines += ["", "How this listing beats competitors:"]
    lines += [f"- [{a.area}] {a.how_this_listing_wins}" for a in intel.advantages]
    return "\n".join(lines)


def _pricing_brief(pricing: PricingStrategy) -> str:
    lines = ["PRICING STRATEGY", "=" * 40, "",
             f"Recommended price: ${pricing.recommended_price:.2f} "
             f"(range ${pricing.price_range_low:.2f}-${pricing.price_range_high:.2f})",
             f"Positioning: {pricing.price_positioning}",
             f"Psychological pricing: {pricing.psychological_pricing_note}",
             "", "Bundle opportunities:"] + [f"- {b}" for b in pricing.bundle_opportunities]
    lines += ["", "Upsell ideas:"] + [f"- {u}" for u in pricing.upsell_ideas]
    lines += ["", "Premium version opportunities:"] + [f"- {p}" for p in pricing.premium_version_opportunities]
    return "\n".join(lines)


def _csv_row(listing: ListingStrategy, category: str, pricing: PricingStrategy) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["title", "description", "price", "tags", "materials", "category"])
    description = "\n\n".join(f"{b.heading}\n{b.body}" for b in listing.description_blocks)
    writer.writerow([_best_title(listing).title, description, f"{pricing.recommended_price:.2f}",
                     ",".join(listing.tags), ",".join(listing.materials), category])
    return buf.getvalue()


def _image_brief(images: ImageStrategy) -> str:
    lines = ["IMAGE PRODUCTION BRIEF — 10 SLOTS (FULL ETSY GALLERY)", "=" * 40]
    for s in sorted(images.slots, key=lambda x: x.slot_id):
        lines += [
            f"\nSLOT {s.slot_id} ({s.role.value}) — {s.intent.value} ({s.psychological_stage.value})",
            f"Visual type: {s.required_visual_type}",
            f"Objective: {s.objective}",
            "Constraints: " + "; ".join(s.prompt_constraints),
            f"AI prompt:\n{s.prompt.render()}",
        ]
        if s.composition_notes:
            lines.append(f"Manual shoot notes: {s.composition_notes}")
    return "\n".join(lines)


def _scores_summary(scores: ConversionScores) -> str:
    lines = ["CONVERSION SCORECARD", "=" * 40]
    for name, cs in scores.model_dump().items():
        lines.append(f"\n{name}: {cs['score']}/100")
        lines.append(f"  {cs['explanation']}")
        for f in cs["contributing_factors"]:
            sign = "+" if f["impact"] >= 0 else ""
            lines.append(f"  [{sign}{f['impact']}] {f['factor']}: {f['detail']}")
    return "\n".join(lines)


def run(analysis: ProductAnalysis, bde: BDEOutput,
        classification: CategoryClassification, listing: ListingStrategy,
        images: ImageStrategy, competitor_intel: CompetitorIntelligence,
        pricing: PricingStrategy, report: ValidationReport,
        scores: ConversionScores) -> ListingOutput:
    """Assemble the enforced final output. The ListingOutput model validator
    rejects the assembly if any required key is missing — the format enforcer."""
    output = ListingOutput(
        product_category=classification.category,
        confidence=classification.confidence,
        buyer_decision_engine=bde,
        listing_strategy=listing,
        image_prompts=images,
        competitor_intelligence=competitor_intel,
        pricing_strategy=pricing,
        validation_report=report,
        conversion_scores=scores,
        product_analysis=analysis,
        classification=classification,
    )
    output.export_formats = {
        "etsy_paste_ready": _etsy_paste_ready(listing, pricing),
        "csv_row": _csv_row(listing, classification.category.value, pricing),
        "image_brief": _image_brief(images),
        "scorecard": _scores_summary(scores),
        "competitor_intelligence_brief": _competitor_brief(competitor_intel),
        "pricing_strategy_brief": _pricing_brief(pricing),
    }
    return output
