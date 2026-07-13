"""
Etsy Growth AI engine — generates the complete ListingResult that powers the
frontend (a faithful port of the etsy-elevate-ai Lovable app).

One structured model call produces the entire strategy: product analysis,
market research, market gap, beat-best-sellers plan, brand plan, titles,
description, 13 tags, keywords, attributes, pricing, a 10-image visual
merchandising plan, a 10-dimension score set, and priority recommendations —
exactly the shape the UI renders (frontend/src/lib/types.ts).

Grounding upgrade over the original: when ETSY_API_KEY is configured, the
live market snapshot (real prices, real title terms, real tags) is injected
into the prompt so the market sections reflect what is actually ranking on
Etsy right now. Behavior and output shape are unchanged.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .etsy.market_research import fetch_market_snapshot
from .pipeline.llm import structured_call


# --- ListingResult schema (field names mirror the frontend types exactly) ---

class _ProductAnalysis(BaseModel):
    summary: str
    idealBuyer: str
    buyingMotivation: str
    emotionalAppeal: str
    complexity: str
    useCases: list[str]
    niches: list[str]
    seasonalOpportunities: list[str]
    giftPotential: str
    premiumPositioning: str


class _MarketResearch(BaseModel):
    overview: str
    competitorPatterns: list[str]
    customerLanguage: list[str]
    objections: list[str]


class _MarketGap(BaseModel):
    competitorsDoWell: list[str]
    customersRespondTo: list[str]
    competitorWeaknesses: list[str]
    differentiation: list[str]
    strongerOffer: str


class _BeatBestSellers(BaseModel):
    positioning: str
    keywordStrategy: str
    visualStrategy: str
    valueProps: list[str]
    whyChooseThis: str


class _BrandColor(BaseModel):
    hex: str
    name: str


class _Brand(BaseModel):
    positioningStatement: str
    idealCustomer: str
    personality: list[str]
    colors: list[_BrandColor] = Field(min_length=3, max_length=6)
    typography: list[str]
    collectionIdeas: list[str]
    expansionIdeas: list[str]
    consistencyGuidelines: list[str]


class _Titles(BaseModel):
    best: str = Field(max_length=140)
    alternatives: list[str]
    reasoning: str


class _FaqItem(BaseModel):
    q: str
    a: str


class _Description(BaseModel):
    hook: str
    problem: str
    transformation: str
    included: list[str]
    features: list[str]
    fileDetails: str
    instructions: str
    printing: str
    compatibility: str
    faq: list[_FaqItem]
    trust: str
    cta: str
    fullText: str


class _Keywords(BaseModel):
    primary: list[str]
    secondary: list[str]
    longTail: list[str]


class _Attributes(BaseModel):
    materials: list[str]
    colors: list[str]
    occasions: list[str]
    themes: list[str]
    categories: list[str]
    styles: list[str]


class _Pricing(BaseModel):
    recommended: float
    min: float
    max: float
    strategy: str


class _ImageBrief(BaseModel):
    n: int = Field(ge=1, le=10)
    title: str
    purpose: str
    psychology: str
    layout: str
    copyOverlay: str
    designDirection: str
    mockup: str
    cta: str = ""


class _Scores(BaseModel):
    seo: int = Field(ge=0, le=100)
    keywordOpportunity: int = Field(ge=0, le=100)
    competitiveAdvantage: int = Field(ge=0, le=100)
    thumbnail: int = Field(ge=0, le=100)
    visualQuality: int = Field(ge=0, le=100)
    conversion: int = Field(ge=0, le=100)
    brandAlignment: int = Field(ge=0, le=100)
    buyerConfidence: int = Field(ge=0, le=100)
    offerStrength: int = Field(ge=0, le=100)
    overall: int = Field(ge=0, le=100)


class ListingResult(BaseModel):
    productAnalysis: _ProductAnalysis
    marketResearch: _MarketResearch
    marketGap: _MarketGap
    beatBestSellers: _BeatBestSellers
    brand: _Brand
    titles: _Titles
    description: _Description
    tags: list[str] = Field(min_length=13, max_length=13)
    keywords: _Keywords
    attributes: _Attributes
    pricing: _Pricing
    images: list[_ImageBrief] = Field(min_length=10, max_length=10)
    scores: _Scores
    recommendations: list[str]

    @field_validator("tags")
    @classmethod
    def tags_etsy_legal(cls, v: list[str]) -> list[str]:
        for t in v:
            if len(t) > 20:
                raise ValueError(f"Etsy tag over 20 chars: {t!r}")
        return v

    @field_validator("images")
    @classmethod
    def image_sequence(cls, v: list[_ImageBrief]) -> list[_ImageBrief]:
        if sorted(i.n for i in v) != list(range(1, 11)):
            raise ValueError("images must be numbered 1-10 exactly once (the full Etsy gallery).")
        return v


# --- prompts (faithful to the original engine, run on Claude) ----------------

SYSTEM_PROMPT = (
    "You are Etsy Growth AI — a fusion of an expert Etsy strategist, SEO "
    "specialist, conversion copywriter, product photographer, graphic designer "
    "and ecommerce growth consultant. You reverse-engineer what top Etsy "
    "best-sellers do, find gaps competitors miss, and build a stronger, "
    "customer-focused offer. Use AIDA, PAS, buyer psychology, anchoring, trust "
    "signals and social proof. Always respond with strict JSON only.\n\n"
    "RULES:\n"
    "- tags: EXACTLY 13 Etsy tags, each <= 20 characters, lowercase, buyer-search phrases.\n"
    "- images: EXACTLY 10 items following the Etsy image sequence: 1 hero, "
    "2 overview, 3 what's included, 4 lifestyle mockup, 5 alternative use case, "
    "6 product details, 7 feature highlights, 8 size/format guide, 9 how it "
    "works, 10 brand + CTA.\n"
    "- description.fullText: the complete ready-to-paste Etsy description "
    "assembled from the sections, using line breaks and light emoji where natural.\n"
    "- brand.colors: 5 palette colors with valid 6-digit hex codes.\n"
    "- All scores are integers 0-100. overall reflects true sales potential, "
    "not an average inflation.\n"
    "- titles.best <= 140 characters, keyword-front-loaded, natural, high click-through.\n"
    "- IF LIVE ETSY MARKET DATA is provided it was measured from the actual top "
    "search results right now — ground marketResearch, marketGap and pricing in "
    "it; never contradict measured numbers.\n"
    "- Be specific, strategic and concrete. No placeholders. Write like an "
    "expert Etsy strategist + conversion copywriter."
)

IMPROVE_ACTIONS: dict[str, str] = {
    "regenerate": "Regenerate fresh, stronger title options while keeping everything accurate.",
    "seo": "Aggressively improve SEO: sharper keywords, better tags, stronger long-tail coverage and search alignment.",
    "conversion": "Maximize conversion: stronger hook, benefits, trust signals, objection handling and CTA.",
    "premium": "Reposition the listing as a premium, high-perceived-value product with elevated language and pricing.",
    "trendy": "Make it feel current and on-trend for today's Etsy buyers without losing timeless appeal.",
    "gift": "Reposition around gifting: gift occasions, recipients, emotional gifting motivation and gift-ready framing.",
    "audience": "Reposition for a different, higher-value target audience.",
    "compete": "Re-run competitor and market-gap analysis with fresh differentiation and a stronger offer.",
}


def build_product_brief(p) -> str:
    files = p.files if isinstance(p.files, list) else []
    file_list = ", ".join(f"{f.get('name', '?')} ({f.get('type', '?')})" for f in files) or "not specified"
    style = p.style if p.style and p.style != "Auto-detect" else "let AI detect"
    return (
        f"PRODUCT NAME: {p.name}\n"
        f"CATEGORY: {p.category or 'let AI detect'}\n"
        f"PREFERRED STYLE: {style}\n"
        f"TARGET AUDIENCE: {p.target_audience or 'let AI infer the best-converting audience'}\n"
        f"SELLER NOTES / EXTRA INPUT: {p.notes or 'none'}\n"
        f"UPLOADED FILES: {file_list}"
    )


def _market_block(keyword: str) -> str:
    snap = fetch_market_snapshot(keyword)
    return snap.render() if snap.ok else ""


def generate(product, competitors: str = "", keywords: str = "") -> tuple[ListingResult, dict]:
    extra = "\n".join(filter(None, [
        f"COMPETITOR EXAMPLES PROVIDED BY SELLER:\n{competitors}" if competitors else "",
        f"EXISTING KEYWORDS TO CONSIDER:\n{keywords}" if keywords else "",
    ]))
    market = _market_block(product.name)
    content = (
        "Analyze this digital product and produce a complete, optimized Etsy "
        "listing strategy designed to outperform current best-sellers.\n\n"
        + build_product_brief(product)
        + (f"\n\n{extra}" if extra else "")
        + (f"\n\n{market}" if market else "")
    )
    return structured_call(SYSTEM_PROMPT, content, ListingResult,
                           max_tokens=20000, temperature=0.8)


def improve(product, current_result: dict, action: str,
            instruction: str = "") -> tuple[ListingResult, dict]:
    directive = IMPROVE_ACTIONS.get(action, IMPROVE_ACTIONS["conversion"])
    if action == "audience" and instruction:
        directive += f" Specifically: {instruction}"
    import json
    content = (
        f"Improve the following existing Etsy listing. FOCUS: {directive}\n"
        + (f"Seller instruction: {instruction}\n" if instruction else "")
        + "\nPRODUCT:\n" + build_product_brief(product)
        + "\n\nCURRENT LISTING JSON:\n" + json.dumps(current_result)[:12000]
        + "\n\nReturn the FULL improved listing (all fields), keeping strengths "
          "and upgrading per the focus above."
    )
    return structured_call(SYSTEM_PROMPT, content, ListingResult,
                           max_tokens=20000, temperature=0.8)
