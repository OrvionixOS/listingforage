"""Stage 8 — Output Format Enforcer. Deterministic rendering + shape enforcement."""
from __future__ import annotations

import csv
import io

from ..schemas import (BDEOutput, CategoryClassification, ConversionScores,
                       ImageStrategy, ListingOutput, ListingStrategy,
                       ProductAnalysis, ValidationReport)


def _etsy_paste_ready(listing: ListingStrategy) -> str:
    parts = [listing.titles[0].title, ""]
    for block in listing.description_blocks:
        parts += [block.heading.upper(), block.body, ""]
    if listing.faq_items:
        parts.append("FAQ")
        for item in listing.faq_items:
            parts += [f"Q: {item.get('question', '')}", f"A: {item.get('answer', '')}", ""]
    parts += ["TAGS (copy into the 13 tag fields):", ", ".join(listing.tags)]
    return "\n".join(parts).strip()


def _csv_row(listing: ListingStrategy, category: str) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["title", "description", "tags", "category"])
    description = "\n\n".join(f"{b.heading}\n{b.body}" for b in listing.description_blocks)
    writer.writerow([listing.titles[0].title, description, ",".join(listing.tags), category])
    return buf.getvalue()


def _image_brief(images: ImageStrategy) -> str:
    lines = ["IMAGE PRODUCTION BRIEF — 7 SLOTS", "=" * 40]
    for s in sorted(images.slots, key=lambda x: x.slot_id):
        lines += [
            f"\nSLOT {s.slot_id} — {s.intent.value} ({s.psychological_stage.value})",
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
        images: ImageStrategy, report: ValidationReport,
        scores: ConversionScores) -> ListingOutput:
    """Assemble the enforced final output. The ListingOutput model validator
    rejects the assembly if any required key is missing — the format enforcer."""
    output = ListingOutput(
        product_category=classification.category,
        confidence=classification.confidence,
        buyer_decision_engine=bde,
        listing_strategy=listing,
        image_prompts=images,
        validation_report=report,
        conversion_scores=scores,
        product_analysis=analysis,
        classification=classification,
    )
    output.export_formats = {
        "etsy_paste_ready": _etsy_paste_ready(listing),
        "csv_row": _csv_row(listing, classification.category.value),
        "image_brief": _image_brief(images),
        "scorecard": _scores_summary(scores),
    }
    return output
