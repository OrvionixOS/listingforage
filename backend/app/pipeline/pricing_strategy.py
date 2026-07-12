"""
Stage 7 — Pricing Strategy Engine.

Recommends a single price point plus the full monetization picture: charm/
psychological pricing rationale, bundle opportunities, upsells, and premium
version ideas — grounded in the product's category, value density, and the
Buyer Decision Engine's value-justification findings.
"""
from __future__ import annotations

from ..schemas import (BDEOutput, CategoryClassification, PricingStrategy,
                       ProductAnalysis)
from .llm import structured_call

SYSTEM = """You are the Pricing Strategy Engine of Etsy Listing AI Studio — an
ecommerce strategist specializing in Etsy digital-product pricing psychology.

RULES:
- recommended_price must be a realistic Etsy digital-product price for this
  category and value density (typically $2-$45 for single items, higher for
  large bundles). Never guess wildly — anchor to price_tier and
  competitive_context from the product analysis.
- Use charm pricing ($X.99 / $X.49 / round-number premium framing) and explain
  WHY in psychological_pricing_note — reference anchoring, decoy effects, or
  round-number premium perception as appropriate.
- price_range_low/high must bracket recommended_price and reflect realistic
  category variance.
- price_positioning: state budget | mid-market | premium AND why, grounded in
  the BDE's value_justification_score and emotional drivers.
- bundle_opportunities: concrete bundle ideas that pair THIS product with
  adjacent products in the same category (name specific complementary items).
- upsell_ideas: concrete post-purchase or listing-level upsells (commercial
  license upgrade, extra formats, editable source files, matching set).
- premium_version_opportunities: how a higher-tier version of THIS exact
  product could be built and priced, and what buyer segment it serves."""


def run(analysis: ProductAnalysis, bde: BDEOutput,
        classification: CategoryClassification) -> tuple[PricingStrategy, dict]:
    content = (
        f"PRODUCT ANALYSIS:\n{analysis.model_dump_json(indent=1)}\n\n"
        f"CATEGORY: {classification.category.value}\n"
        f"VALUE JUSTIFICATION SCORE: {bde.scores.value_justification_score}/100\n"
        f"EMOTIONAL DRIVERS: {', '.join(bde.emotional_drivers)}\n"
        f"DOMINANT PURCHASE SCENARIO: {bde.dominant_purchase_scenario}\n\n"
        "Produce the complete pricing strategy for this product."
    )
    return structured_call(SYSTEM, content, PricingStrategy,
                           max_tokens=2500, temperature=0.4)
