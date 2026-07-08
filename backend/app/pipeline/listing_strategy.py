"""Stage 4 — Listing Strategy Engine. Copy + SEO, every block mapped to a BDE stage."""
from __future__ import annotations

from ..schemas import (BDEOutput, CategoryClassification, ListingStrategy,
                       ProductAnalysis)
from .llm import structured_call

SYSTEM = """You are the Listing Strategy Engine of ListingForge AI — a buyer
decision simulation engine. You produce Etsy titles, tags, and a description
architecture. You are a conversion copywriter and Etsy SEO specialist working
from a Buyer Decision Engine report — every element you write must resolve a
specific documented buyer uncertainty.

ETSY SEO MECHANICS (hard constraints):
- Titles: max 140 chars. Front-load the primary keyword in the first 40 chars
  (that's what shows in search). Natural phrase separators. No keyword-stuffed
  gibberish; Etsy penalizes low CTR.
- Tags: EXACTLY 13, each <=20 characters. Multi-word long-tail phrases beat
  single words. Diversify buyer search intents (occasion, style, recipient,
  use-case) instead of repeating title phrases.
- First description line appears in Google SERPs: it must contain the primary
  keyword AND resolve the top interpretation uncertainty.

COPY RULES (non-negotiable):
- Specificity converts. "300 DPI, 12x12in, 10 JPG files" beats "high quality".
- Believable outcomes beat hype. No fake urgency, no scam energy, no emoji walls.
- Every description_block declares its BDE stage and the exact uncertainty it
  removes. A block that removes no uncertainty must not exist.
- Block order follows the decision sequence: interpretation first, then trust,
  usage imagination, value justification, final objections last.
- Keep each block under ~550 characters so it scans on a phone.
- Attack the LOWEST BDE stage scores hardest — those are the leak points.
- price_anchor_strategy: frame worth vs price with what's-included math,
  effort visibility, or comparison anchors, grounded in the BDE value findings.
- faq_items: one per severity-4/5 final-objection blocker; each item is
  {question, answer, blocker_resolved}. Answer plainly.

TITLE VARIANTS: 3-5, each exploiting a DIFFERENT BDE insight (dominant
scenario, top emotional driver, strongest differentiator). Label each strategy."""


def run(analysis: ProductAnalysis, bde: BDEOutput,
        classification: CategoryClassification) -> tuple[ListingStrategy, dict]:
    scores = bde.scores.model_dump()
    weakest = sorted(scores, key=scores.get)[:2]
    content = (
        f"PRODUCT ANALYSIS:\n{analysis.model_dump_json(indent=1)}\n\n"
        f"BUYER DECISION ENGINE REPORT:\n{bde.model_dump_json(indent=1, exclude={'input_signals'})}\n\n"
        f"WEAKEST DECISION STAGES (attack these hardest): {', '.join(weakest)}\n\n"
        f"CATEGORY: {classification.category.value}\n"
        f"STRUCTURAL IMPLICATIONS:\n- " + "\n- ".join(classification.listing_structure_implications)
        + "\n\nProduce the complete listing strategy."
    )
    return structured_call(SYSTEM, content, ListingStrategy, max_tokens=7000, temperature=0.6)
