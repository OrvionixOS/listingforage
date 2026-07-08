"""
ListingForge AI — Inter-module data contracts (Phase 2).

HARD RULES enforced at this layer:
- Structured JSON between all modules.
- Six named BDE stage scores derived from input signals.
- Exactly 7 image slots; each maps to a DIFFERENT primary buyer uncertainty.
- Every image prompt carries mandatory lighting / camera / environment /
  composition / product-focus / realism fields plus the conversion clause.
- Final output always contains: product_category, confidence,
  buyer_decision_engine, listing_strategy, image_prompts, validation_report,
  conversion_scores.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


CONVERSION_CLAUSE = "Etsy conversion optimized, designed to reduce buyer uncertainty"


class ProductCategory(str, Enum):
    physical_product = "physical_product"
    digital_product = "digital_product"
    print_on_demand = "print_on_demand"
    gift_personalized = "gift_personalized"
    saas_tool = "saas_tool"


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
    buying_occasion: str
    price_tier: str = Field(description="budget | mid | premium")
    competitive_context: str
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
        if len(v) < 5:
            raise ValueError("Uncertainty map too shallow: at least 5 distinct buyer doubts required.")
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


class DescriptionBlock(BaseModel):
    heading: str
    body: str
    bde_stage: BDEStage
    uncertainty_resolved: str


class ListingStrategy(BaseModel):
    primary_keyword: str
    secondary_keywords: list[str]
    titles: list[TitleVariant] = Field(min_length=3, max_length=5)
    tags: list[str] = Field(min_length=13, max_length=13)
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


class ImageSlot(BaseModel):
    slot_id: int = Field(ge=1, le=7)
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
        return self


class ImageStrategy(BaseModel):
    slots: list[ImageSlot] = Field(min_length=7, max_length=7)

    @field_validator("slots")
    @classmethod
    def structural_rules(cls, v: list[ImageSlot]) -> list[ImageSlot]:
        if sorted(s.slot_id for s in v) != [1, 2, 3, 4, 5, 6, 7]:
            raise ValueError("Exactly slots 1-7 required, no duplication.")
        primaries = [s.primary_uncertainty_id for s in v]
        if len(set(primaries)) != 7:
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
    "listing_strategy", "image_prompts", "validation_report", "conversion_scores",
)


class ListingOutput(BaseModel):
    # Enforced final shape
    product_category: ProductCategory
    confidence: float
    buyer_decision_engine: BDEOutput
    listing_strategy: ListingStrategy
    image_prompts: ImageStrategy
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
