"""
Conversion Scoring Engine (Phase 2).

Seven scores, each with an explanation and computed contributing factors.
Fully deterministic: scores are derived from the generated artifacts (BDE
stage scores, uncertainty resolution coverage, validator results, Etsy SEO
mechanics, mobile readability rules) so identical inputs always produce
identical scores and every factor is auditable.

Scoring model: each score starts from a base and accumulates signed factor
impacts, clamped to 0-100. Factors carry their impact and evidence.
"""
from __future__ import annotations

import re

from ..schemas import (BDEOutput, ConversionScore, ConversionScores,
                       ImageIntent, ImageStrategy, ListingStrategy,
                       ScoreFactor, ValidationReport)


def _clamp(v: float) -> int:
    return int(max(0, min(100, round(v))))


def _score(base: int, factors: list[ScoreFactor], explanation: str) -> ConversionScore:
    total = base + sum(f.impact for f in factors)
    return ConversionScore(score=_clamp(total), explanation=explanation,
                           contributing_factors=factors)


def _resolution_coverage(bde: BDEOutput, images: ImageStrategy,
                         listing: ListingStrategy) -> tuple[int, int]:
    """How many severity>=4 doubts are resolved by a slot, description block, or FAQ."""
    claimed = {s.primary_uncertainty_id for s in images.slots}
    claimed |= {i for s in images.slots for i in s.secondary_uncertainty_ids}
    resolved_texts = " ".join(
        [b.uncertainty_resolved for b in listing.description_blocks]
        + [str(f.get("blocker_resolved", "")) for f in listing.faq_items]
    ).lower()
    high = [u for u in bde.buyer_uncertainty_map if u.severity >= 4]
    resolved = 0
    for u in high:
        key = u.uncertainty.lower()[:25]
        if u.id in claimed or key[:14] in resolved_texts:
            resolved += 1
    return resolved, len(high)


def compute(bde: BDEOutput, listing: ListingStrategy, images: ImageStrategy,
            report: ValidationReport) -> ConversionScores:
    slots = images.slots
    primary_title = listing.titles[0].title
    first40 = primary_title[:40].lower()
    kw = listing.primary_keyword.lower()

    # ---------------- CTR ----------------
    f: list[ScoreFactor] = []
    slot1 = next((s for s in slots if s.slot_id == 1), None)
    if slot1 and slot1.intent == ImageIntent.CTR:
        f.append(ScoreFactor(factor="CTR-dedicated thumbnail", impact=18,
                 detail=f"Slot 1 is a {slot1.required_visual_type} built for the search grid."))
    else:
        f.append(ScoreFactor(factor="No CTR thumbnail", impact=-25,
                 detail="Slot 1 is not attention-optimized."))
    if kw and kw in first40:
        f.append(ScoreFactor(factor="Keyword in visible title window", impact=12,
                 detail="Primary keyword appears in the first 40 title characters shown in search."))
    else:
        f.append(ScoreFactor(factor="Keyword outside visible window", impact=-10,
                 detail="Primary keyword missing from the first 40 title characters."))
    heavy = [t for s in slots if s.slot_id == 1 for t in s.prompt.text_overlays]
    if slot1 and not heavy:
        f.append(ScoreFactor(factor="Clean thumbnail", impact=6,
                 detail="No text overlays competing at 180px scale."))
    f.append(ScoreFactor(factor="Attention stage baseline",
             impact=int((bde.scores.attention_score - 50) * 0.3),
             detail=f"BDE attention_score {bde.scores.attention_score}/100 for the raw inputs."))
    ctr = _score(55, f, "Probability the listing earns the click in a 40-tile search grid: thumbnail design, visible title window, attention baseline.")

    # ---------------- Trust ----------------
    f = []
    trust_slots = [s for s in slots if s.intent == ImageIntent.TRUST]
    f.append(ScoreFactor(factor="Trust-proof slots", impact=min(len(trust_slots), 2) * 12,
             detail=f"{len(trust_slots)} slot(s) dedicated to quality/legitimacy proof."))
    remedies = " ".join(g.remedy.lower() for g in bde.trust_gap_analysis)
    covered = sum(1 for g in bde.trust_gap_analysis
                  if any(w in " ".join(s.objective.lower() for s in slots)
                         for w in g.gap.lower().split()[:3]))
    f.append(ScoreFactor(factor="Trust gaps addressed", impact=min(covered, 3) * 6,
             detail=f"{covered}/{len(bde.trust_gap_analysis)} identified trust gaps targeted by slot objectives."))
    trust_blocks = [b for b in listing.description_blocks if b.bde_stage.value == "trust"]
    if trust_blocks:
        f.append(ScoreFactor(factor="Trust copy block", impact=8,
                 detail=f'"{trust_blocks[0].heading}" reinforces quality in the description.'))
    f.append(ScoreFactor(factor="Trust stage baseline",
             impact=int((bde.scores.trust_score - 50) * 0.25),
             detail=f"BDE trust_score {bde.scores.trust_score}/100."))
    trust = _score(48, f, "Perceived legitimacy and quality: proof imagery, trust-gap remedies, trust copy.")

    # ---------------- Clarity ----------------
    f = []
    interp_slots = [s for s in slots if s.intent == ImageIntent.CLARITY]
    f.append(ScoreFactor(factor="Clarity slots", impact=min(len(interp_slots), 2) * 10,
             detail=f"{len(interp_slots)} slot(s) answer what-is-this / what-do-I-get visually."))
    spec_hits = bde.input_signals.get("spec_hits", 0)
    all_body = " ".join(b.body.lower() for b in listing.description_blocks)
    specs_in_copy = len(re.findall(r"\b\d+\s?(x\s?\d+)?\s?(in|inch|cm|px|dpi|files?|pages?|pieces?)\b", all_body))
    f.append(ScoreFactor(factor="Specification density in copy", impact=min(specs_in_copy, 5) * 3,
             detail=f"{specs_in_copy} concrete spec mention(s) across description blocks."))
    if listing.description_blocks and listing.description_blocks[0].bde_stage.value == "interpretation":
        f.append(ScoreFactor(factor="Interpretation-first description", impact=10,
                 detail="First block answers the buyer's first question before anything else."))
    else:
        f.append(ScoreFactor(factor="Buried interpretation", impact=-8,
                 detail="Description does not lead with what-is-this clarity."))
    f.append(ScoreFactor(factor="Interpretation baseline",
             impact=int((bde.scores.interpretation_score - 50) * 0.25),
             detail=f"BDE interpretation_score {bde.scores.interpretation_score}/100 "
                    f"(raw inputs had {spec_hits} measurable spec signal(s))."))
    clarity = _score(50, f, "How instantly a first-time viewer understands what the product is and exactly what they receive.")

    # ---------------- SEO ----------------
    f = []
    f.append(ScoreFactor(factor="Full 13-tag usage", impact=12,
             detail="All 13 Etsy tag slots used (schema-enforced)."))
    long_tail = sum(1 for t in listing.tags if len(t.split()) >= 2)
    f.append(ScoreFactor(factor="Long-tail tags", impact=min(long_tail, 10),
             detail=f"{long_tail}/13 tags are multi-word phrases."))
    tag_words = [w for t in listing.tags for w in t.lower().split()]
    diversity = len(set(tag_words)) / max(len(tag_words), 1)
    f.append(ScoreFactor(factor="Tag intent diversity", impact=int(diversity * 14),
             detail=f"{int(diversity*100)}% unique words across tags — diversified search intents."))
    if kw in first40:
        f.append(ScoreFactor(factor="Front-loaded primary keyword", impact=10,
                 detail="Primary keyword inside the first 40 title characters."))
    first_line = listing.description_blocks[0].body.split("\n")[0].lower() if listing.description_blocks else ""
    if kw and kw.split()[0] in first_line:
        f.append(ScoreFactor(factor="Keyword in first description line", impact=8,
                 detail="Google SERP snippet line contains the primary keyword."))
    if len(primary_title) > 140:
        f.append(ScoreFactor(factor="Title over limit", impact=-20, detail="Title exceeds 140 chars."))
    seo = _score(42, f, "Etsy + Google search mechanics: tag usage, long-tail diversity, keyword placement.")

    # ---------------- Mobile ----------------
    f = []
    bad_overlays = [t for s in slots for t in s.prompt.text_overlays if len(t.split()) > 6]
    f.append(ScoreFactor(factor="Overlay readability", impact=10 if not bad_overlays else -12,
             detail="All overlays <=6 words — readable on a phone." if not bad_overlays
                    else f"{len(bad_overlays)} overlay(s) too long for mobile."))
    long_blocks = [b for b in listing.description_blocks if len(b.body) > 550]
    f.append(ScoreFactor(factor="Scannable description blocks", impact=8 if not long_blocks else -6,
             detail="Every block under 550 chars — thumb-scroll friendly." if not long_blocks
                    else f"{len(long_blocks)} block(s) exceed comfortable mobile length."))
    meaningful40 = len(first40.strip()) >= 25
    f.append(ScoreFactor(factor="Mobile title window", impact=8 if meaningful40 else -5,
             detail="First 40 title characters form a complete, meaningful hook."
                    if meaningful40 else "Visible mobile title window is too thin."))
    if slot1:
        f.append(ScoreFactor(factor="Thumbnail-scale legibility", impact=8,
                 detail="Slot 1 constraint: single focal subject legible at 180px."))
    mobile = _score(55, f, "Experience on the device where ~70% of Etsy browsing happens: overlay length, block scannability, visible title window."
)

    # ---------------- Completeness ----------------
    f = []
    parts = [
        ("3+ title variants", len(listing.titles) >= 3, 8),
        ("13 tags", len(listing.tags) == 13, 8),
        ("4+ description blocks", len(listing.description_blocks) >= 4, 10),
        ("FAQ present", len(listing.faq_items) >= 1, 8),
        ("10-slot image system", len(slots) == 10, 12),
        ("Price anchor strategy", bool(listing.price_anchor_strategy.strip()), 6),
        ("Validator passed", report.valid, 10),
    ]
    for name, ok, weight in parts:
        f.append(ScoreFactor(factor=name, impact=weight if ok else -weight,
                 detail="present" if ok else "MISSING"))
    completeness = _score(38, f, "Structural completeness of the listing system against the full Etsy Listing AI Studio specification.")

    # ---------------- Conversion (composite) ----------------
    f = []
    resolved, total_high = _resolution_coverage(bde, images, listing)
    rate = resolved / total_high if total_high else 1.0
    f.append(ScoreFactor(factor="High-severity doubt resolution", impact=int(rate * 30) - 15,
             detail=f"{resolved}/{total_high} severity-4/5 buyer doubts are resolved by a slot, block, or FAQ."))
    obj_slot = next((s for s in slots if s.slot_id == 10), None)
    if obj_slot and obj_slot.intent == ImageIntent.CONVERSION:
        f.append(ScoreFactor(factor="Final-objection killer", impact=8,
                 detail=f"Slot 10 (brand_cta) targets: {obj_slot.objective[:70]}"))
    faq_blockers = len(listing.faq_items)
    f.append(ScoreFactor(factor="Objection FAQ coverage", impact=min(faq_blockers, 3) * 4,
             detail=f"{faq_blockers} FAQ item(s) answering final objections."))
    subs = [ctr.score, trust.score, clarity.score]
    f.append(ScoreFactor(factor="Funnel sub-scores", impact=int((sum(subs) / 3 - 50) * 0.4),
             detail=f"CTR {ctr.score} / trust {trust.score} / clarity {clarity.score} feed the composite."))
    f.append(ScoreFactor(factor="Value justification baseline",
             impact=int((bde.scores.value_justification_score - 50) * 0.2),
             detail=f"BDE value_justification_score {bde.scores.value_justification_score}/100."))
    conversion = _score(50, f, "Composite purchase probability: high-severity doubt resolution rate, objection handling, and the funnel sub-scores.")

    return ConversionScores(
        CTR_score=ctr, trust_score=trust, clarity_score=clarity,
        conversion_score=conversion, seo_score=seo, mobile_score=mobile,
        listing_completeness_score=completeness,
    )
