"""
Insights engines: SEO Studio + Buyer Journey Simulator.

Both are deterministic compositions of analysis the pipeline already produced —
no extra model calls, instant, always explainable.
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from .database import Listing, ListingImage
from .schemas import ListingOutput

# ---------------------------------------------------------------------------
# SEO Studio
# ---------------------------------------------------------------------------

BUYER_INTENT_TERMS = {
    "gift", "personalized", "custom", "bundle", "set", "printable", "instant",
    "download", "digital", "seamless", "wedding", "birthday", "anniversary",
    "kit", "template", "pack", "handmade", "vintage", "luxury", "premium",
}
ETSY_TAG_MAX = 20


def _tag_strength(tag: str, title_terms: set[str]) -> dict:
    t = tag.lower().strip()
    words = t.split()
    length_util = len(t) / ETSY_TAG_MAX                      # use the space you're given
    multiword = min(len(words), 3) / 3                        # long-tail beats single words
    intent = 1.0 if set(words) & BUYER_INTENT_TERMS else 0.0
    title_echo = 1.0 if set(words) & title_terms else 0.0     # tags reinforcing the title rank
    score = round((0.3 * length_util + 0.3 * multiword + 0.25 * intent + 0.15 * title_echo) * 100)
    notes = []
    if len(words) == 1:
        notes.append("single word — long-tail phrases convert better")
    if len(t) < 10:
        notes.append(f"only {len(t)}/{ETSY_TAG_MAX} chars used")
    if not (set(words) & BUYER_INTENT_TERMS):
        notes.append("no buyer-intent term")
    return {"tag": tag, "strength": score, "notes": notes}


def seo_report(db: Session, listing: Listing) -> dict:
    output = ListingOutput.model_validate(listing.output_json)
    ls = output.listing_strategy
    title = ls.titles[0].title
    title_terms = set(re.findall(r"[a-z]{3,}", title.lower()))

    tags = [_tag_strength(t, title_terms) for t in ls.tags]
    avg = round(sum(t["strength"] for t in tags) / len(tags)) if tags else 0

    # title analysis
    kw = ls.primary_keyword.lower()
    kw_pos = title.lower().find(kw)
    title_checks = {
        "primary keyword present": kw_pos >= 0,
        "keyword front-loaded (first 40 chars)": 0 <= kw_pos <= 40,
        "under 140 chars": len(title) <= 140,
        "readable (no keyword stuffing)": title.count("|") + title.count(",") <= 5,
    }

    # suggestions from uncertainty map: unresolved doubts are search phrases too
    suggestions = []
    covered = " ".join(ls.tags).lower()
    for u in sorted(output.buyer_decision_engine.buyer_uncertainty_map,
                    key=lambda x: -x.severity)[:6]:
        terms = set(re.findall(r"[a-z]{4,}", u.uncertainty.lower())) - {"this", "will", "what", "does"}
        missing = [t for t in terms if t not in covered][:2]
        if missing:
            suggestions.append({
                "source": f"buyer doubt (sev {u.severity})",
                "suggestion": " ".join(missing),
                "why": f"Buyers searching around “{u.uncertainty[:60]}” won't find you."})
    for sk in ls.secondary_keywords:
        if sk.lower() not in covered:
            suggestions.append({"source": "secondary keyword",
                                "suggestion": sk,
                                "why": "Identified in strategy but absent from tags."})

    return {
        "primary_keyword": ls.primary_keyword,
        "title": {"text": title, "checks": title_checks,
                  "score": round(100 * sum(title_checks.values()) / len(title_checks))},
        "tags": tags,
        "tag_average_strength": avg,
        "suggestions": suggestions[:8],
        "search_intent": {
            "buyer": output.product_analysis.target_buyer,
            "occasion": output.product_analysis.buying_occasion,
        },
    }


# ---------------------------------------------------------------------------
# Buyer Journey Simulator
# ---------------------------------------------------------------------------

def journey(db: Session, listing: Listing) -> dict:
    output = ListingOutput.model_validate(listing.output_json)
    ls = output.listing_strategy
    bde = output.buyer_decision_engine
    title = ls.titles[0].title

    images = (db.query(ListingImage)
              .filter(ListingImage.listing_id == listing.id,
                      ListingImage.superseded.is_(False))
              .order_by(ListingImage.display_order).all())
    slot_by_id = {s.slot_id: s for s in output.image_prompts.slots}

    stage_scores = {k.replace("_score", ""): v for k, v in bde.scores.model_dump().items()}
    assessments = {(a.stage.value if hasattr(a.stage, "value") else a.stage): a
                   for a in bde.stage_assessments}
    friction = []
    for stage, sc in stage_scores.items():
        if sc < 60:
            a = assessments.get(stage)
            issue = (a.risks[0] if a and a.risks else
                     (a.buyer_question if a else "weak stage"))
            friction.append({"where": stage, "severity": "high" if sc < 45 else "medium",
                             "issue": issue[:140], "type": "stage"})
    for u in bde.buyer_uncertainty_map:
        if u.severity >= 4:
            resolved = any((b.uncertainty_resolved or -1) == u.id for b in ls.description_blocks) or \
                       any(sl.primary_uncertainty_id == u.id for sl in output.image_prompts.slots)
            if not resolved:
                friction.append({"where": u.stage.value if hasattr(u.stage, "value") else u.stage,
                                 "severity": "high",
                                 "issue": f"Unresolved sev-{u.severity} doubt: {u.uncertainty}",
                                 "type": "uncertainty"})

    return {
        "search_result": {
            "title_shown": title[:64] + ("…" if len(title) > 64 else ""),
            "title_mobile": title[:40] + ("…" if len(title) > 40 else ""),
            "price": listing.input_price,
            "thumbnail_slot": images[0].slot_id if images else None,
            "thumbnail_score": images[0].validation_score if images else None,
        },
        "image_sequence": [
            {"position": img.display_order, "slot_id": img.slot_id,
             "purpose": slot_by_id[img.slot_id].objective if img.slot_id in slot_by_id else "",
             "psychological_stage": (slot_by_id[img.slot_id].psychological_stage.value
                                     if img.slot_id in slot_by_id else ""),
             "score": img.validation_score}
            for img in images],
        "reading_flow": [
            {"heading": b.heading, "stage": b.bde_stage.value if hasattr(b.bde_stage, "value") else b.bde_stage,
             "resolves": b.uncertainty_resolved}
            for b in ls.description_blocks],
        "decision_timeline": [
            {"stage": st, "score": sc,
             "state": "strong" if sc >= 75 else "adequate" if sc >= 60 else "at risk"}
            for st, sc in stage_scores.items()],
        "friction_points": friction,
    }
