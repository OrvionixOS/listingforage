"""
Etsy Listing AI Studio — Inter-module data contracts.

HARD RULES enforced at this layer:
- Structured JSON between all modules.
- Six named BDE stage scores derived from input signals.
- Exactly 10 image slots (the full Etsy gallery), each maps to a fixed
  conversion role AND a DIFFERENT primary buyer uncertainty.
- Every image prompt carries mandatory lighting / camera / environment /
  composition / product-focus / realism fields plus the conversion clause.
- Final output always contains: product_category, confidence,
  buyer_decision_engine, listing_strategy, image_prompts, competitor_intelligence,
  pricing_strategy, validation_report, conversion_scores.
- The platform is DIGITAL-PRODUCTS-ONLY: every category is an instant-download
  digital good (printable, planner, template, invitation, cut file, bundle,
  educational resource, or pattern).
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


CONVERSION_CLAUSE = "Etsy conversion optimized, designed to reduce buyer uncertainty"


class ProductCategory(str, Enum):
    """The eight digital product categories the Digital Product Category
    Engine recognizes and optimizes for."""
    printable_art = "printable_art"
    digital_planner = "digital_planner"
    template = "template"
    invitation = "invitation"
    svg_cut_file = "svg_cut_file"
    digital_bundle = "digital_bundle"
    educational_product = "educational_product"
    pattern = "pattern"


class BDEStage(str, Enum):
    attention = "attention"
    interpretation = "interpretation"
    trust = "trust"
    usage_imagination = "usage_imagination"
    value_justification = "value_justification"
    final_objection = "final_objection"


class ImageIntent(str, Enum):
    CTR = "CTR"
    CLARITY = "CLARITY"
    TRUST = "TRUST"
    VALUE = "VALUE"
    CONTEXT = "CONTEXT"
    CONVERSION = "CONVERSION"


# ---------------------------------------------------------------------------
# Stage 1 — Product Analysis
# ---------------------------------------------------------------------------

class ProductAnalysis(BaseModel):
    product_name: str
    core_offer: str = Field(description="One sentence: what the buyer actually receives.")
    materials_or_format: list[str] = Field(default_factory=list)
    key_attributes: list[str] = Field(default_factory=list)
    target_buyer: str
    who_buys_and_why: str = Field(
        description="Direct answer to: who is most likely to buy this product and why?")
    buying_occasion: str
    seasonality: str = Field(default="", description="Peak buying windows, or 'evergreen'.")
    price_tier: str = Field(description="budget | mid | premium")
    competitive_context: str
    market_positioning: str = Field(
        default="", description="Where this sits vs the category's typical listings.")
    emotional_buying_triggers: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 2 — Buyer Decision Engine
# ---------------------------------------------------------------------------

class StageAssessment(BaseModel):
    stage: BDEStage
    buyer_question: str
    current_answer_strength: int = Field(ge=0, le=10)
    risks: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)


class UncertaintyItem(BaseModel):
    id: int = Field(default=0, ge=0, description="Stable index used by slots to claim uncertainties.")
    stage: BDEStage
    uncertainty: str
    severity: int = Field(ge=1, le=5)
    resolvable_by: list[str] = Field(default_factory=list)


class TrustGap(BaseModel):
    gap: str = Field(description="The specific legitimacy/quality doubt.")
    evidence: str = Field(description="What in the inputs creates or fails to resolve it.")
    severity: int = Field(ge=1, le=5)
    remedy: str = Field(description="The concrete listing element that closes it.")


class StageScores(BaseModel):
    """Six named 0-100 scores: 50% deterministic input signals +
    50% model stage assessment (buyer_decision_engine.compute_scores)."""
    attention_score: int = Field(ge=0, le=100)
    interpretation_score: int = Field(ge=0, le=100)
    trust_score: int = Field(ge=0, le=100)
    usage_imagination_score: int = Field(ge=0, le=100)
    value_justification_score: int = Field(ge=0, le=100)
    objection_score: int = Field(ge=0, le=100)


class BDEModelOutput(BaseModel):
    """What the model produces. Scores are computed afterwards from signals."""
    stage_assessments: list[StageAssessment]
    buyer_uncertainty_map: list[UncertaintyItem]
    missing_information_gaps: list[str]
    trust_gap_analysis: list[TrustGap]
    emotional_drivers: list[str]
    conversion_blockers: list[str]
    decision_friction_points: list[str]
    dominant_purchase_scenario: str

    @field_validator("stage_assessments")
    @classmethod
    def all_six_stages(cls, v: list[StageAssessment]) -> list[StageAssessment]:
        missing = set(BDEStage) - {s.stage for s in v}
        if missing:
            raise ValueError(f"BDE output missing stages: {sorted(m.value for m in missing)}")
        return v

    @field_validator("buyer_uncertainty_map")
    @classmethod
    def sequential_ids(cls, v: list[UncertaintyItem]) -> list[UncertaintyItem]:
        for i, u in enumerate(v):
            u.id = i  # normalize to stable sequential ids
        if len(v) < 10:
            # the 10-slot Image Strategy Engine needs 10 DISTINCT doubts to claim
            raise ValueError("Uncertainty map too shallow: at least 10 distinct buyer doubts required "
                             "(one per Etsy gallery image slot).")
        return v


class BDEOutput(BDEModelOutput):
    """Full BDE result: model analysis + computed scores + raw input signals."""
    scores: StageScores
    input_signals: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage 3 — Category classification
# ---------------------------------------------------------------------------

class CategoryClassification(BaseModel):
    category: ProductCategory
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    signals_considered: list[str] = Field(
        default_factory=list,
        description="Distinct signal types weighed: lexical, structural, BDE scenario, price tier, buyer language.")
    fallback_reasoning: Optional[str] = Field(
        default=None,
        description="Populated when confidence < 0.6: why the most CONVERSION-RELEVANT category won over the most literal one.")
    listing_structure_implications: list[str]


# ---------------------------------------------------------------------------
# Stage 4 — Listing copy strategy
# ---------------------------------------------------------------------------

class TitleVariant(BaseModel):
    title: str = Field(max_length=140)
    strategy: str
    is_best: bool = Field(default=False, description="True for exactly the recommended title.")


class DescriptionSection(str, Enum):
    """The mandatory conversion-copy architecture for a digital-product
    Etsy description, in required reading order."""
    opening_hook = "opening_hook"
    buyer_problem = "buyer_problem"
    emotional_benefit = "emotional_benefit"
    transformation = "transformation"
    features = "features"
    whats_included = "whats_included"
    file_details = "file_details"
    instructions = "instructions"
    compatibility = "compatibility"
    objection_handling = "objection_handling"
    call_to_action = "call_to_action"


class DescriptionBlock(BaseModel):
    section: DescriptionSection
    heading: str
    body: str
    bde_stage: BDEStage
    uncertainty_resolved: str


class ListingStrategy(BaseModel):
    primary_keyword: str
    secondary_keywords: list[str]
    long_tail_keywords: list[str] = Field(default_factory=list)
    search_phrases: list[str] = Field(default_factory=list)
    titles: list[TitleVariant] = Field(
        min_length=6, max_length=6,
        description="Exactly 6: the best title (is_best=True) plus 5 alternatives.")
    title_explanation: str = Field(
        default="", description="Why the best title beats the 5 alternatives.")
    tags: list[str] = Field(min_length=13, max_length=13)
    attributes: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list, max_length=13)
    colors: list[str] = Field(default_factory=list)
    occasions: list[str] = Field(default_factory=list)
    description_blocks: list[DescriptionBlock]
    price_anchor_strategy: str
    faq_items: list[dict] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def tag_length(cls, v: list[str]) -> list[str]:
        for t in v:
            if len(t) > 20:
                raise ValueError(f"Etsy tag over 20 chars: {t!r}")
        return v

    @field_validator("titles")
    @classmethod
    def exactly_one_best(cls, v: list[TitleVariant]) -> list[TitleVariant]:
        """Normalizes so titles[0] is ALWAYS the best title — every consumer
        (editor, scoring, exports, Etsy publish) relies on that invariant."""
        best_idx = next((i for i, t in enumerate(v) if t.is_best), 0)
        for t in v:
            t.is_best = False
        v[0], v[best_idx] = v[best_idx], v[0]
        v[0].is_best = True
        return v


# ---------------------------------------------------------------------------
# Stage 5 — Image strategy: 7 slots, structured prompts
# ---------------------------------------------------------------------------

class ImagePrompt(BaseModel):
    """Structured generation prompt. Every field is MANDATORY and non-empty —
    vague or artistic-only prompts are rejected at validation."""
    subject: str
    lighting: str = Field(description="Lighting specification: source, quality, direction.")
    camera: str = Field(description="Camera specification: lens/focal length, angle, aperture feel.")
    environment: str = Field(description="Environment / set specification.")
    composition: str = Field(description="Composition rules: framing, negative space, focal hierarchy.")
    product_focus: str = Field(description="Explicit instruction keeping the product the hero.")
    realism_constraint: str = Field(description="Realism constraint: honest materials, true scale, no CGI plasticity.")
    text_overlays: list[str] = Field(default_factory=list, description="Exact overlay copy; <=6 words each.")
    negative: str = Field(default="", description="What to avoid.")

    @model_validator(mode="after")
    def no_vague_fields(self):
        for name in ("subject", "lighting", "camera", "environment",
                     "composition", "product_focus", "realism_constraint"):
            if len(getattr(self, name).strip()) < 8:
                raise ValueError(f"ImagePrompt.{name} is missing or too vague — hard requirement.")
        for t in self.text_overlays:
            if len(t.split()) > 6:
                raise ValueError(f"Overlay over 6 words (unreadable on mobile): {t!r}")
        return self

    def render(self) -> str:
        parts = [
            f"SUBJECT: {self.subject}",
            f"LIGHTING: {self.lighting}",
            f"CAMERA: {self.camera}",
            f"ENVIRONMENT: {self.environment}",
            f"COMPOSITION: {self.composition}",
            f"PRODUCT FOCUS: {self.product_focus}",
            f"REALISM: {self.realism_constraint}",
        ]
        if self.text_overlays:
            overlays = " ".join('"' + t + '"' for t in self.text_overlays)
            parts.append(f"TEXT OVERLAYS: {overlays}")
        if self.negative:
            parts.append(f"NEGATIVE: {self.negative}")
        parts.append(CONVERSION_CLAUSE + ".")
        return "\n".join(parts)


class ImageRole(str, Enum):
    """The 10 fixed Etsy gallery roles, in mandated slot order (1-10)."""
    hero = "hero"
    overview = "overview"
    value_breakdown = "value_breakdown"
    lifestyle_mockup = "lifestyle_mockup"
    alternate_use_case = "alternate_use_case"
    close_up_detail = "close_up_detail"
    how_it_works = "how_it_works"
    sizes_formats_compatibility = "sizes_formats_compatibility"
    benefits_transformation = "benefits_transformation"
    brand_cta = "brand_cta"


IMAGE_ROLE_BY_SLOT: dict[int, ImageRole] = {
    1: ImageRole.hero,
    2: ImageRole.overview,
    3: ImageRole.value_breakdown,
    4: ImageRole.lifestyle_mockup,
    5: ImageRole.alternate_use_case,
    6: ImageRole.close_up_detail,
    7: ImageRole.how_it_works,
    8: ImageRole.sizes_formats_compatibility,
    9: ImageRole.benefits_transformation,
    10: ImageRole.brand_cta,
}


class ImageSlot(BaseModel):
    slot_id: int = Field(ge=1, le=10)
    role: ImageRole = Field(description="Fixed conversion role for this slot position.")
    intent: ImageIntent
    psychological_stage: BDEStage
    objective: str = Field(description="The specific buyer uncertainty this slot removes.")
    required_visual_type: str = Field(
        description="Concrete visual format: hero_macro, file_grid, zoom_proof, tiling_demo, "
                    "lifestyle_scene, scale_reference, variant_grid, process_shot, info_card, "
                    "mockup_in_use, comparison_split, size_chart, unboxing")
    prompt_constraints: list[str] = Field(
        min_length=1, description="Slot-specific rules the prompt must obey.")
    prompt: ImagePrompt
    primary_uncertainty_id: int = Field(
        ge=0, description="THE uncertainty this slot exists to resolve. Unique across slots.")
    secondary_uncertainty_ids: list[int] = Field(default_factory=list)
    composition_notes: str = Field(default="", description="Guidance for manual photo/design execution.")

    @model_validator(mode="after")
    def objective_present(self):
        if len(self.objective.strip()) < 10:
            raise ValueError(f"Slot {self.slot_id}: objective missing — aesthetic-only slots are forbidden.")
        expected = IMAGE_ROLE_BY_SLOT.get(self.slot_id)
        if expected is not None and self.role != expected:
            raise ValueError(
                f"Slot {self.slot_id} must have role {expected.value!r}, got {self.role.value!r}.")
        return self


class ImageStrategy(BaseModel):
    slots: list[ImageSlot] = Field(min_length=10, max_length=10)

    @field_validator("slots")
    @classmethod
    def structural_rules(cls, v: list[ImageSlot]) -> list[ImageSlot]:
        if sorted(s.slot_id for s in v) != list(range(1, 11)):
            raise ValueError("Exactly slots 1-10 required, no duplication — the full Etsy gallery.")
        primaries = [s.primary_uncertainty_id for s in v]
        if len(set(primaries)) != 10:
            dupes = sorted({p for p in primaries if primaries.count(p) > 1})
            raise ValueError(f"Every slot must map to a DIFFERENT buyer uncertainty; duplicated ids: {dupes}")
        return v


# ---------------------------------------------------------------------------
# Validation report (Image Strategy Validator output)
# ---------------------------------------------------------------------------

class ValidationCheck(BaseModel):
    check: str
    passed: bool
    detail: str


class ValidationReport(BaseModel):
    valid: bool
    checks: list[ValidationCheck]
    attempts: int = Field(ge=1, description="Generation attempts needed to pass.")
    regeneration_feedback: list[str] = Field(
        default_factory=list, description="Feedback sent to the model on failed attempts.")


# ---------------------------------------------------------------------------
# Competitor Intelligence Engine
# ---------------------------------------------------------------------------

class CompetitorAdvantage(BaseModel):
    area: str = Field(description="positioning | seo | imagery | value_perception | buyer_communication")
    how_this_listing_wins: str


class CompetitorIntelligence(BaseModel):
    best_selling_patterns: list[str] = Field(
        min_length=2, description="What top-performing listings in this category do.")
    popular_keywords: list[str] = Field(default_factory=list)
    common_image_styles: list[str] = Field(default_factory=list)
    pricing_patterns: str
    customer_expectations: list[str] = Field(default_factory=list)
    review_language_signals: list[str] = Field(
        default_factory=list, description="Phrases buyers commonly praise or complain about in this category.")
    competitor_weaknesses: list[str] = Field(min_length=2)
    missed_opportunities: list[str] = Field(
        min_length=2, description="Gaps competitors leave open that this listing can claim.")
    advantages: list[CompetitorAdvantage] = Field(
        min_length=3, description="How this listing beats competitors: positioning, SEO, imagery, "
                                  "value perception, and buyer communication.")
    # Provenance — set by the engine AFTER the model call, never by the model.
    data_source: str = Field(
        default="model_knowledge",
        description="live_etsy_data (grounded in a real-time Etsy search) or model_knowledge (fallback).")
    market_snapshot: dict = Field(
        default_factory=dict,
        description="The measured live-market facts (prices, terms, tags, sample titles) the analysis was grounded in.")


# ---------------------------------------------------------------------------
# Pricing Strategy Engine
# ---------------------------------------------------------------------------

class PricingStrategy(BaseModel):
    recommended_price: float = Field(gt=0)
    price_range_low: float = Field(gt=0)
    price_range_high: float = Field(gt=0)
    psychological_pricing_note: str = Field(
        description="Why this exact price point (e.g. charm pricing, anchor effects).")
    price_positioning: str = Field(description="budget | mid-market | premium, with reasoning.")
    bundle_opportunities: list[str] = Field(min_length=1)
    upsell_ideas: list[str] = Field(min_length=1)
    premium_version_opportunities: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def range_sane(self):
        if not (self.price_range_low <= self.recommended_price <= self.price_range_high):
            raise ValueError("recommended_price must fall within price_range_low/high.")
        return self


# ---------------------------------------------------------------------------
# Conversion Scoring Engine output
# ---------------------------------------------------------------------------

class ScoreFactor(BaseModel):
    factor: str
    impact: int = Field(description="Signed contribution to the score.")
    detail: str


class ConversionScore(BaseModel):
    score: int = Field(ge=0, le=100)
    explanation: str
    contributing_factors: list[ScoreFactor]


class ConversionScores(BaseModel):
    CTR_score: ConversionScore
    trust_score: ConversionScore
    clarity_score: ConversionScore
    conversion_score: ConversionScore
    seo_score: ConversionScore
    mobile_score: ConversionScore
    listing_completeness_score: ConversionScore


# ---------------------------------------------------------------------------
# Final output — format enforced
# ---------------------------------------------------------------------------

FINAL_OUTPUT_REQUIRED_KEYS = (
    "product_category", "confidence", "buyer_decision_engine",
    "listing_strategy", "image_prompts", "competitor_intelligence",
    "pricing_strategy", "validation_report", "conversion_scores",
)


class ListingOutput(BaseModel):
    # Enforced final shape
    product_category: ProductCategory
    confidence: float
    buyer_decision_engine: BDEOutput
    listing_strategy: ListingStrategy
    image_prompts: ImageStrategy
    competitor_intelligence: CompetitorIntelligence
    pricing_strategy: PricingStrategy
    validation_report: ValidationReport
    conversion_scores: ConversionScores
    # Supporting context
    product_analysis: ProductAnalysis
    classification: CategoryClassification
    export_formats: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_final_shape(self):
        for k in FINAL_OUTPUT_REQUIRED_KEYS:
            if getattr(self, k, None) is None:
                raise ValueError(f"Output format violation — missing required key: {k}")
        return self


# ---------------------------------------------------------------------------
# API request/response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    title: str
    description: str
    price: Optional[float] = None
    image_ids: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
