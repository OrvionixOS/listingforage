"""
Stage 6 — Competitor Intelligence Engine.

Models the current Etsy marketplace for this digital product category: what
best-selling listings do, where they're weak, and exactly how this listing
should out-position them. This is market reasoning grounded in the category's
known conventions (not a live scrape) — it produces the same competitive
analysis a seasoned Etsy strategist would hand a seller before launch.
"""
from __future__ import annotations

from ..schemas import (BDEOutput, CategoryClassification, CompetitorIntelligence,
                       ListingStrategy, ProductAnalysis)
from .llm import structured_call

SYSTEM = """You are the Competitor Intelligence Engine of Etsy Listing AI
Studio — an ecommerce strategist and market researcher who has studied
thousands of Etsy digital-product listings in this category. You model the
current competitive landscape and produce a concrete plan for beating it.

Ground every claim in category-typical patterns for THIS product's category —
be specific to the category and product, never generic ("good SEO helps
sales" is banned; "competitors bury file formats in paragraph 3 — lead with a
formats line in the first 200 characters" is the bar).

Cover:
- best_selling_patterns: what top sellers in this category actually do
  (title structure, image count/style, bundling, pricing anchors).
- popular_keywords: search terms buyers in this category actually use.
- common_image_styles: the visual conventions competitors default to.
- pricing_patterns: where prices cluster and why (with actual $ context for
  this product's tier).
- customer_expectations: what buyers assume they'll get in this category.
- review_language_signals: phrases buyers commonly praise or complain about
  for this category (e.g. "instant access", "confusing instructions").
- competitor_weaknesses: concrete, specific gaps — not "could be better".
- missed_opportunities: gaps competitors leave open that THIS listing can
  claim first.
- advantages: at least 3, each naming one area (positioning | seo | imagery |
  value_perception | buyer_communication) and exactly how THIS listing's
  strategy wins there, referencing this product's actual analysis and BDE
  findings."""


def run(analysis: ProductAnalysis, bde: BDEOutput,
        classification: CategoryClassification,
        listing: ListingStrategy) -> tuple[CompetitorIntelligence, dict]:
    content = (
        f"PRODUCT ANALYSIS:\n{analysis.model_dump_json(indent=1)}\n\n"
        f"CATEGORY: {classification.category.value}\n"
        f"CATEGORY REASONING: {classification.reasoning}\n\n"
        f"DOMINANT PURCHASE SCENARIO: {bde.dominant_purchase_scenario}\n"
        f"EMOTIONAL DRIVERS: {', '.join(bde.emotional_drivers)}\n"
        f"TOP CONVERSION BLOCKERS: {', '.join(bde.conversion_blockers)}\n\n"
        f"THIS LISTING'S PRIMARY KEYWORD: {listing.primary_keyword}\n"
        f"THIS LISTING'S TAGS: {', '.join(listing.tags)}\n"
        f"THIS LISTING'S PRICE ANCHOR STRATEGY: {listing.price_anchor_strategy}\n\n"
        "Produce the complete competitor intelligence report for this product."
    )
    return structured_call(SYSTEM, content, CompetitorIntelligence,
                           max_tokens=5000, temperature=0.5)
