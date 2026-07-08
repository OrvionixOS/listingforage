"""
Stage 2 — BUYER DECISION ENGINE (Phase 2).

Real computation module:
  1. Deterministic input-signal extraction (signals.py) produces six heuristic
     stage baselines from measurable properties of the raw inputs.
  2. The model produces the qualitative analysis: stage assessments, the
     uncertainty map, trust gap analysis, drivers, blockers, friction points.
  3. compute_scores() blends both into the six named stage scores:
     score = 0.5 * signal_baseline + 0.5 * (model_answer_strength * 10)

The blend means neither pure keyword heuristics nor pure model vibes decide a
score — a listing with zero specs cannot fake a high interpretation_score, and
a spec-stuffed listing with real trust risks cannot fake a high trust_score.
"""
from __future__ import annotations

from ..schemas import (BDEModelOutput, BDEOutput, BDEStage, ProductAnalysis,
                       StageScores)
from .llm import structured_call
from .signals import InputSignals

SYSTEM = """You are the BUYER DECISION ENGINE of ListingForge AI — a buyer
decision simulation engine for e-commerce conversion optimization. You model
how real Etsy buyers decide, stage by stage. You are a buyer-psychology
analyst, not a copywriter.

THE SIX STAGES (assess all six):

1. attention — Search-results grid, ~180px thumbnail, competing with 40+ tiles.
   Buyer question: "Does anything here pull my eye?" Factors: contrast, subject
   legibility at thumbnail scale, one dominant focal point, differentiation.

2. interpretation — First 2 seconds on the listing page. "What exactly is this,
   and what exactly do I get?" Failure mode: any format, size, quantity or
   medium ambiguity. Confused buyers back out to search.

3. trust — "Is this seller legitimate and is the quality real?" Etsy signals:
   real-item photos vs stock renders, visible craftsmanship, real-shop feel.

4. usage_imagination — "Can I see this in MY life?" The buyer must mentally
   place the item in their home, work, body, or the recipient's hands.

5. value_justification — "Is this worth the price vs the tab of similar
   listings I have open?" Factors: what's included, scale honesty, effort
   visibility, comparison anchors.

6. final_objection — Last 10 seconds before purchase or abandonment. "What
   could go wrong?" Sizing, shipping time, compatibility, licensing, returns.

You are also given DETERMINISTIC INPUT SIGNALS measured from the raw inputs
(spec detection counts, trust-term counts, image counts, etc). Use them as
evidence — e.g. spec_hits=0 means the interpretation stage has a real problem,
whatever the copy vibe suggests.

ANALYSIS RULES:
- Ground every finding in the product analysis (especially `ambiguities`) and
  the measured signals. Generic findings are worthless.
- buyer_uncertainty_map: 6-10 items. Each is ONE specific doubt, tagged to a
  stage, severity 1-5 (5 = purchase-blocking), with the listing surfaces that
  can resolve it (image, title, description, faq, video). Order from most to
  least severe. These become the assignment targets for the 7 image slots, so
  make each one concrete and visually resolvable where possible.
- trust_gap_analysis: each gap needs the evidence that creates it and the
  concrete remedy that closes it.
- conversion_blockers: only severity-4/5 doubts.
- emotional_drivers: ranked, emotionally accurate, not hype.
- dominant_purchase_scenario: commit to ONE scenario to optimize around.
- decision_friction_points: moments of effort/confusion in browse-to-purchase.
- stage_assessments.current_answer_strength: 0-10, how well the CURRENT raw
  inputs answer that stage's question. Be strict; this feeds the scoring
  engine and inflated numbers corrupt downstream optimization."""

_SIGNAL_FOR_STAGE = {
    BDEStage.attention: "attention_signal",
    BDEStage.interpretation: "interpretation_signal",
    BDEStage.trust: "trust_signal",
    BDEStage.usage_imagination: "usage_imagination_signal",
    BDEStage.value_justification: "value_justification_signal",
    BDEStage.final_objection: "objection_signal",
}

_SCORE_FIELD = {
    BDEStage.attention: "attention_score",
    BDEStage.interpretation: "interpretation_score",
    BDEStage.trust: "trust_score",
    BDEStage.usage_imagination: "usage_imagination_score",
    BDEStage.value_justification: "value_justification_score",
    BDEStage.final_objection: "objection_score",
}


def compute_scores(model_out: BDEModelOutput, signals: InputSignals) -> StageScores:
    """Blend deterministic signal baselines with model stage assessments."""
    strengths = {a.stage: a.current_answer_strength for a in model_out.stage_assessments}
    values = {}
    for stage, field in _SCORE_FIELD.items():
        heuristic = getattr(signals, _SIGNAL_FOR_STAGE[stage])
        model_score = strengths[stage] * 10
        values[field] = int(round(0.5 * heuristic + 0.5 * model_score))
    return StageScores(**values)


def run(analysis: ProductAnalysis, signals: InputSignals,
        performance_context: str = "") -> tuple[BDEOutput, dict]:
    content = (
        "PRODUCT ANALYSIS (structured):\n"
        f"{analysis.model_dump_json(indent=1)}\n\n"
        "DETERMINISTIC INPUT SIGNALS (measured from raw inputs):\n"
        f"{signals.to_dict()}\n\n"
        + (f"{performance_context}\n\n" if performance_context else "")
        + "Run the full six-stage Buyer Decision Engine analysis."
    )
    model_out, usage = structured_call(SYSTEM, content, BDEModelOutput,
                                       max_tokens=7000, temperature=0.5)
    scores = compute_scores(model_out, signals)
    full = BDEOutput(**model_out.model_dump(), scores=scores,
                     input_signals=signals.to_dict())
    return full, usage
