"""
Listing Editor engine.

apply_edits(): validated field updates against the completed ListingOutput —
titles, description blocks, tags, materials, FAQ, price. Hard Etsy rules are
enforced server-side; every successful edit triggers a deterministic rescore
so the Live Quality Panel is always truthful.

rescore(): recomputes the 7 conversion scores plus two Phase 4 additions:
  - brand_consistency: measured overlap between the brand profile (voice
    terms, messaging pillars, photography style) and the actual copy/prompts
  - compliance: deterministic Etsy rule checks (tag count/length, title
    length, image count, materials count, price present)

assist(): AI-assisted improvement of a single field, grounded in the Buyer
Decision Engine analysis, returning improved value + rationale (explainable).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from .database import BrandProfile, Listing, ListingImage
from .pipeline import scoring
from .schemas import ListingOutput

ETSY_TITLE_MAX = 140
ETSY_TAG_MAX = 20
ETSY_TAG_COUNT = 13
ETSY_MATERIALS_MAX = 13

EDITABLE = {"title", "description_blocks", "tags", "materials", "faq_items", "price"}


@dataclass
class EditResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    output: ListingOutput | None = None
    scores: dict | None = None


def _validate(field_name: str, value) -> list[str]:
    errs = []
    if field_name == "title":
        if not isinstance(value, str) or not value.strip():
            errs.append("Title cannot be empty.")
        elif len(value) > ETSY_TITLE_MAX:
            errs.append(f"Title exceeds Etsy's {ETSY_TITLE_MAX} character limit ({len(value)}).")
    elif field_name == "tags":
        if not isinstance(value, list) or len(value) != ETSY_TAG_COUNT:
            errs.append(f"Exactly {ETSY_TAG_COUNT} tags are required "
                        f"({len(value) if isinstance(value, list) else 0} given).")
        else:
            for t in value:
                if not isinstance(t, str) or not t.strip():
                    errs.append("Tags cannot be empty.")
                    break
                if len(t) > ETSY_TAG_MAX:
                    errs.append(f"Tag “{t}” exceeds {ETSY_TAG_MAX} characters.")
            if len({t.lower().strip() for t in value if isinstance(t, str)}) != len(value):
                errs.append("Tags must be unique.")
    elif field_name == "description_blocks":
        if not isinstance(value, list) or not value:
            errs.append("At least one description block is required.")
        else:
            for b in value:
                if not (b.get("heading", "").strip() and b.get("body", "").strip()):
                    errs.append("Every description block needs a heading and body.")
                    break
    elif field_name == "materials":
        if not isinstance(value, list) or not value:
            errs.append("At least one material/format entry is required.")
        elif len(value) > ETSY_MATERIALS_MAX:
            errs.append(f"Etsy accepts at most {ETSY_MATERIALS_MAX} materials.")
    elif field_name == "faq_items":
        if not isinstance(value, list):
            errs.append("FAQ items must be a list of question/answer pairs.")
    elif field_name == "price":
        try:
            if float(value) < 0.20:
                errs.append("Etsy's minimum price is $0.20.")
        except (TypeError, ValueError):
            errs.append("Price must be a number.")
    return errs


def apply_edits(db: Session, listing: Listing, edits: dict) -> EditResult:
    unknown = set(edits) - EDITABLE
    if unknown:
        return EditResult(False, [f"Unknown fields: {', '.join(sorted(unknown))}"])
    errors: list[str] = []
    for k, v in edits.items():
        errors += _validate(k, v)
    if errors:
        return EditResult(False, errors)

    output = ListingOutput.model_validate(listing.output_json)
    ls = output.listing_strategy
    if "title" in edits:
        ls.titles[0].title = edits["title"].strip()
        ls.titles[0].strategy = ls.titles[0].strategy or "edited"
    if "tags" in edits:
        ls.tags = [t.strip() for t in edits["tags"]]
    if "description_blocks" in edits:
        from .schemas import DescriptionBlock
        blocks = []
        for i, b in enumerate(edits["description_blocks"]):
            old = ls.description_blocks[i] if i < len(ls.description_blocks) else None
            blocks.append(DescriptionBlock(
                heading=b["heading"].strip(), body=b["body"].strip(),
                bde_stage=b.get("bde_stage") or (old.bde_stage if old else "interpretation"),
                uncertainty_resolved=b.get("uncertainty_resolved")
                                     or (old.uncertainty_resolved if old else None)))
        ls.description_blocks = blocks
    if "faq_items" in edits:
        ls.faq_items = edits["faq_items"]
    if "materials" in edits:
        output.product_analysis.materials_or_format = [m.strip() for m in edits["materials"]]
    if "price" in edits:
        listing.input_price = float(edits["price"])

    scores = rescore(db, listing, output)
    listing.output_json = output.model_dump(mode="json")
    db.commit()
    return EditResult(True, [], output, scores)


# ---------------------------------------------------------------------------
# Rescoring: conversion + brand + compliance
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[a-z]{3,}")


def _terms(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def brand_consistency(profile: BrandProfile | None, output: ListingOutput) -> dict:
    if profile is None or not (profile.voice or profile.messaging_pillars or profile.photography_style):
        return {"score": None, "explanation": "No brand profile configured yet — "
                "set one up in Brand Studio to measure consistency.", "problems": [],
                "recommendations": ["Create a brand profile so every listing can be "
                                    "checked against your voice and visual identity."]}
    copy_text = " ".join([b.heading + " " + b.body for b in output.listing_strategy.description_blocks]
                         + [t.title for t in output.listing_strategy.titles])
    copy_terms = _terms(copy_text)
    prompt_text = " ".join(s.prompt.render() for s in output.image_prompts.slots)
    prompt_terms = _terms(prompt_text)

    problems, hits, total = [], 0, 0
    for pillar in (profile.messaging_pillars or []):
        total += 1
        if _terms(pillar) & copy_terms:
            hits += 1
        else:
            problems.append(f"Messaging pillar “{pillar}” doesn't appear in the copy.")
    voice_terms = _terms(profile.voice or "")
    if voice_terms:
        total += 1
        overlap = len(voice_terms & copy_terms) / len(voice_terms)
        if overlap >= 0.25:
            hits += 1
        else:
            problems.append("Copy tone shows little overlap with your defined voice.")
    photo_terms = _terms(profile.photography_style or "")
    if photo_terms:
        total += 1
        if len(photo_terms & prompt_terms) / len(photo_terms) >= 0.25:
            hits += 1
        else:
            problems.append("Image prompts don't reflect your photography style.")
    score = round(100 * hits / total) if total else None
    return {"score": score,
            "explanation": f"{hits} of {total} brand signals present in this listing.",
            "problems": problems,
            "recommendations": [f"Weave in: {p}" for p in problems][:3]
                               or ["Brand system fully reflected — nothing to fix."]}


def compliance(output: ListingOutput, listing: Listing, image_count: int) -> dict:
    checks = {
        f"exactly {ETSY_TAG_COUNT} tags": len(output.listing_strategy.tags) == ETSY_TAG_COUNT,
        f"all tags ≤ {ETSY_TAG_MAX} chars": all(len(t) <= ETSY_TAG_MAX for t in output.listing_strategy.tags),
        f"title ≤ {ETSY_TITLE_MAX} chars": len(output.listing_strategy.titles[0].title) <= ETSY_TITLE_MAX,
        "7 listing images": image_count >= 7,
        f"materials ≤ {ETSY_MATERIALS_MAX}": len(output.product_analysis.materials_or_format) <= ETSY_MATERIALS_MAX,
        "price set (≥ $0.20)": bool(listing.input_price and listing.input_price >= 0.20),
    }
    failed = [k for k, ok in checks.items() if not ok]
    return {"score": round(100 * sum(checks.values()) / len(checks)),
            "explanation": f"{sum(checks.values())} of {len(checks)} Etsy requirements met.",
            "problems": [f"Failing: {f}" for f in failed],
            "recommendations": [f"Fix before publishing: {f}" for f in failed]
                               or ["Fully compliant with Etsy listing rules."]}


def rescore(db: Session, listing: Listing, output: ListingOutput | None = None) -> dict:
    output = output or ListingOutput.model_validate(listing.output_json)
    conv = scoring.compute(output.buyer_decision_engine, output.listing_strategy,
                           output.image_prompts, output.validation_report)
    output.conversion_scores = conv
    image_count = (db.query(ListingImage)
                   .filter(ListingImage.listing_id == listing.id,
                           ListingImage.superseded.is_(False)).count())
    profile = (db.query(BrandProfile)
               .filter(BrandProfile.user_id == listing.user_id).first())
    brand = brand_consistency(profile, output)
    comp = compliance(output, listing, image_count)
    scores_dict = output.conversion_scores.model_dump(mode="json")
    scores_dict["brand_consistency"] = brand
    scores_dict["compliance"] = comp
    return scores_dict


# ---------------------------------------------------------------------------
# AI field assist — explainable improvement grounded in the BDE
# ---------------------------------------------------------------------------

def assist(listing: Listing, field_name: str, instruction: str = "",
           block_index: int | None = None) -> dict:
    from pydantic import BaseModel

    from .pipeline.llm import structured_call

    output = ListingOutput.model_validate(listing.output_json)
    bde = output.buyer_decision_engine
    top_uncertainties = sorted(bde.buyer_uncertainty_map, key=lambda u: -u.severity)[:4]
    context = (
        f"TARGET BUYER: {output.product_analysis.target_buyer}\n"
        f"TOP BUYER UNCERTAINTIES: "
        + "; ".join(f"[sev {u.severity}] {u.uncertainty}" for u in top_uncertainties)
        + f"\nPRIMARY KEYWORD: {output.listing_strategy.primary_keyword}"
    )

    class Improvement(BaseModel):
        improved_value: str
        rationale: str
        uncertainty_addressed: str

    if field_name == "title":
        current = output.listing_strategy.titles[0].title
        task = (f"Improve this Etsy title (max {ETSY_TITLE_MAX} chars, front-load the primary "
                f"keyword, keep it human-readable):\nCURRENT: {current}")
    elif field_name == "description_block" and block_index is not None:
        b = output.listing_strategy.description_blocks[block_index]
        task = (f"Improve this description block body (keep the heading's intent: "
                f"“{b.heading}”, stage: {b.bde_stage}):\nCURRENT: {b.body}")
    elif field_name == "tags":
        task = ("Improve this 13-tag set. Return improved_value as a comma-separated list of "
                f"EXACTLY 13 tags, each ≤{ETSY_TAG_MAX} chars, unique, buyer-intent phrased:\n"
                f"CURRENT: {', '.join(output.listing_strategy.tags)}")
    else:
        raise ValueError(f"Unsupported assist field: {field_name}")

    if instruction:
        task += f"\nUSER DIRECTION: {instruction}"

    result, _ = structured_call(
        "You are ListingForge's conversion copy editor. Improve the given field so it "
        "resolves the highest-severity buyer uncertainties. Never invent product claims. "
        "Explain your change in one or two sentences.",
        context + "\n\n" + task, Improvement, max_tokens=1200, temperature=0.4)
    return result.model_dump()
