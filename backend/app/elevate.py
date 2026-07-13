"""
Etsy Growth AI engine — generates the complete ListingResult that powers the
frontend (a faithful port of the etsy-elevate-ai Lovable app).

One structured model call produces the entire strategy: product analysis,
market research, market gap, beat-best-sellers plan, brand plan, titles,
description, 13 tags, keywords, attributes, pricing, a 10-image visual
merchandising plan, a 10-dimension score set, and priority recommendations —
exactly the shape the UI renders (frontend/src/lib/types.ts).

VISION: identify_product() looks at the actual uploaded product images and
answers "what IS this?" — product type, premium positioning, a suggested
product name, an SEO title, 13 tags, target buyers, and branded collection
ideas — and generate() attaches the same images so the full listing is
grounded in the real pixels, not just the seller's description.

Grounding upgrade over the original: when ETSY_API_KEY is configured, the
live market snapshot (real prices, real title terms, real tags) is injected
into the prompt so the market sections reflect what is actually ranking on
Etsy right now. Behavior and output shape are unchanged.
"""
from __future__ import annotations

import base64
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from .etsy.market_research import fetch_market_snapshot
from .pipeline.llm import structured_call

MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
MAX_VISION_IMAGES = 8
MAX_VISION_EDGE = 1568  # Anthropic's optimal max image edge


def _image_blocks(image_paths: list[str]) -> list[dict]:
    """Product images → vision blocks. Downscaled + re-encoded as JPEG so a
    pack of multi-MB PNGs doesn't balloon the request (detail at 1568px is
    plenty for identification and grounding)."""
    blocks = []
    for p in image_paths[:MAX_VISION_IMAGES]:
        path = Path(p)
        if not path.exists() or path.suffix.lower() not in MEDIA_TYPES:
            continue
        try:
            import io

            from PIL import Image
            img = Image.open(path)
            img.thumbnail((MAX_VISION_EDGE, MAX_VISION_EDGE))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=85)
            data, media = buf.getvalue(), "image/jpeg"
        except Exception:
            data, media = path.read_bytes(), MEDIA_TYPES[path.suffix.lower()]
        blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media,
                       "data": base64.b64encode(data).decode()},
        })
    return blocks


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
    # Complete shop kit — a cohesive Etsy store, not just one listing
    shopBannerConcept: str = Field(
        default="", description="Design direction for the Etsy shop banner: layout, copy, imagery.")
    shopIconConcept: str = Field(
        default="", description="Design direction for the shop icon/avatar.")
    listingStyleGuide: list[str] = Field(
        default_factory=list,
        description="4-7 rules every future listing image/copy should follow for a cohesive shop.")


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


# --- product taxonomy (mirrors frontend/src/lib/categories.ts) ---------------

CATEGORY_GROUPS: dict[str, list[str]] = {
    "Art & Collectibles": ["Digital wall art", "Printable art", "Digital illustrations",
                           "Digital paintings", "Photography prints"],
    "Craft Supplies & Tools": ["Digital papers", "Scrapbook papers", "SVG files",
                               "Cricut files", "Sewing patterns", "Embroidery patterns",
                               "Laser cut files", "Craft templates"],
    "Paper & Party Supplies": ["Invitations", "Party printables", "Wedding templates",
                               "Cards", "Labels", "Signs", "Printable decorations"],
    "Templates & Design Resources": ["Canva templates", "Resume templates",
                                     "Social media templates", "Business templates",
                                     "Branding kits", "Presentation templates"],
    "Planners & Organization": ["Digital planners", "Printable planners", "Calendars",
                                "Trackers", "Checklists", "Notion templates"],
    "Journals, Books & Educational": ["Ebooks", "Workbooks", "Guided journals",
                                      "Coloring books", "Worksheets", "Learning resources"],
    "Graphics & Digital Assets": ["Clip art", "Digital stickers", "Backgrounds",
                                  "Textures", "Patterns", "Fonts", "Brushes", "Icons"],
    "Photography & Creative Tools": ["Lightroom presets", "Photoshop actions",
                                     "Photo overlays", "Mockups", "Editing resources"],
    "Business & Professional Resources": ["Client forms", "Contracts", "Spreadsheets",
                                          "Calculators", "SOP templates", "Marketing materials"],
    "AI & Digital Tools": ["AI prompt packs", "AI workflow templates", "ChatGPT resources",
                           "Midjourney resources", "Automation templates"],
    "Wellness & Spirituality": ["Manifestation journals", "Tarot resources",
                                "Astrology resources", "Meditation guides",
                                "Affirmation cards", "Spiritual workbooks"],
    "3D & Technical Files": ["3D models", "STL files", "CAD files",
                             "Digital manufacturing files"],
    "Audio & Video Assets": ["Music files", "Sound effects", "Video templates",
                             "Motion graphics", "LUTs"],
}

PRODUCT_CATEGORIES = [f"{group} / {sub}"
                      for group, subs in CATEGORY_GROUPS.items() for sub in subs]


# --- product-file analysis (PDF / ZIP / SVG / link) ---------------------------

MAX_PDF_BYTES = 10 * 1024 * 1024


def _asset_context(files: list[dict]) -> tuple[list[dict], str]:
    """Optional product files → (extra content blocks, inventory text).
    PDFs are attached as readable documents; ZIPs are inventoried (file count,
    types, sample names); SVGs are noted — so the AI knows exactly what's
    included, how many pages/files, and the intended use."""
    blocks: list[dict] = []
    notes: list[str] = []
    for f in files:
        path = Path(f.get("path", ""))
        if not path.exists():
            continue
        suffix = path.suffix.lower()
        name = f.get("name") or path.name
        if suffix == ".pdf":
            if path.stat().st_size <= MAX_PDF_BYTES:
                blocks.append({
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf",
                               "data": base64.b64encode(path.read_bytes()).decode()},
                })
                notes.append(f"- {name}: PDF attached in full — read it to know exact contents and page count.")
            else:
                notes.append(f"- {name}: PDF ({path.stat().st_size // 1024} KB, too large to attach).")
        elif suffix == ".zip":
            try:
                import zipfile
                from collections import Counter
                with zipfile.ZipFile(path) as z:
                    entries = [i for i in z.infolist() if not i.is_dir()]
                ext_counts = Counter((Path(i.filename).suffix.lower() or "no-ext") for i in entries)
                sample = ", ".join(i.filename for i in entries[:12])
                counts = ", ".join(f"{n}x {ext}" for ext, n in ext_counts.most_common())
                notes.append(f"- {name}: ZIP containing {len(entries)} files ({counts}). Sample: {sample}")
            except Exception:
                notes.append(f"- {name}: ZIP (could not be read).")
        elif suffix == ".svg":
            notes.append(f"- {name}: SVG vector file ({path.stat().st_size // 1024} KB).")
    inventory = ("PRODUCT FILE CONTENTS (measured from the actual uploaded product "
                 "files — this is ground truth for what's included):\n" + "\n".join(notes)) if notes else ""
    return blocks, inventory


class ProductIdentification(BaseModel):
    """What the uploaded images actually are, and how to sell them."""
    product_type: str = Field(
        description="Plain naming of what these images are, e.g. 'luxury metallic digital paper / seamless texture pack'.")
    positioning: str = Field(
        description="2-4 sentences: the aesthetic these images actually have, how to position them "
                    "(e.g. premium interior-design feel vs scrapbook craft), and which higher-value "
                    "buyers that positioning attracts.")
    suggested_name: str = Field(description="A concise product name for the shop's own records.")
    category: str = Field(description=f"The best fit from: {', '.join(PRODUCT_CATEGORIES)}")
    style: str = Field(description="Dominant visual style, e.g. Luxury, Minimal, Boho.")
    target_buyers: list[str] = Field(
        min_length=2, description="Specific buyer segments this positioning attracts.")
    seo_title: str = Field(
        max_length=140,
        description="A strong ready-to-use Etsy title, keyword-front-loaded, <=140 chars.")
    tags: list[str] = Field(
        min_length=13, max_length=13,
        description="EXACTLY 13 Etsy tags, each <=20 chars, lowercase buyer-search phrases.")
    collection_ideas: list[str] = Field(
        min_length=4,
        description="Branded, collectible product-line names for scaling a whole shop around this "
                    "style, e.g. 'Luxe Surfaces Vol. 1 — Sculpted Plaster'. Same series name across all.")
    shop_branding_note: str = Field(
        description="1-2 sentences on why the collection naming works (cohesive, premium, collectible).")
    observed_details: str = Field(
        description="Objective inventory of what the images show: how many designs, colors, finishes, "
                    "textures, any visible text/mockups. Used to ground the full listing generation.")

    @field_validator("tags")
    @classmethod
    def tags_etsy_legal(cls, v: list[str]) -> list[str]:
        for t in v:
            if len(t) > 20:
                raise ValueError(f"Etsy tag over 20 chars: {t!r}")
        return v


IDENTIFY_SYSTEM = (
    "You are Etsy Growth AI's product identification engine — an expert Etsy "
    "strategist and merchandiser LOOKING AT the seller's actual product images. "
    "Identify what the product really is from the pixels, then position it for "
    "the HIGHEST-VALUE buyer segment its aesthetic can credibly attract (e.g. "
    "premium interior-design feel -> luxury digital papers / seamless "
    "backgrounds / texture overlays for designers and branding agencies, rather "
    "than scrapbook craft supplies).\n\n"
    "RULES:\n"
    "- Describe only what is visibly in the images; never invent contents.\n"
    "- seo_title: keyword-front-loaded, natural, <=140 chars, names the product "
    "type, key colors/finishes, and commercial use when plausible.\n"
    "- tags: EXACTLY 13, each <=20 characters, lowercase buyer-search phrases.\n"
    "- collection_ideas: one cohesive series brand across all entries "
    "(e.g. 'Luxe Surfaces Vol. 1 — Sculpted Plaster', 'Vol. 2 — Metallic "
    "Weaves'), so the shop reads as a curated design resource.\n"
    "- category MUST be one of the provided options.\n"
    "Respond with strict JSON only."
)


def identify_product(image_paths: list[str]) -> tuple[ProductIdentification, dict]:
    """Vision pass: what are these images, and how should they be sold?"""
    blocks = _image_blocks(image_paths)
    if not blocks:
        raise ValueError("No readable images provided.")
    content = blocks + [{
        "type": "text",
        "text": (f"These {len(blocks)} images are a seller's digital product files. "
                 "Identify the product and produce the identification report."),
    }]
    return structured_call(IDENTIFY_SYSTEM, content, ProductIdentification,
                           max_tokens=3000, temperature=0.6)


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
    "- images: EXACTLY 10 items following the Etsy listing image set: "
    "1 hero (main Etsy thumbnail, product-focused, high click potential), "
    "2 product showcase (shows everything included), "
    "3 feature breakdown (highlights benefits and contents), "
    "4 close-up detail (shows quality and details), "
    "5 lifestyle mockup (shows the product being used), "
    "6 size/file information (explains exactly what the buyer receives), "
    "7 comparison (shows value and bundle contents), "
    "8 brand style (matches the store aesthetic), "
    "9 how it works (download → use → create), "
    "10 final sales (strong conversion-focused close).\n"
    "- images[].psychology: every image is designed to SELL, not to be pretty. "
    "Name the specific buyer-psychology trigger it fires — attention, desire, "
    "trust, objection removal, social proof, or value demonstration — and make "
    "the scene outcome-focused ('busy entrepreneur using the planner on an iPad, "
    "visibly organized and in control'), never decorative ('beautiful planner "
    "mockup'). Across the 10 images cover ALL six triggers at least once.\n"
    "- description.fullText: the complete ready-to-paste Etsy description "
    "assembled from the sections, using line breaks and light emoji where natural.\n"
    "- brand.colors: 5 palette colors with valid 6-digit hex codes. Also fill "
    "shopBannerConcept, shopIconConcept and listingStyleGuide so the seller "
    "gets a cohesive Etsy store, not one listing.\n"
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
    name = p.name if p.name and p.name != "Untitled product" \
        else "not provided — infer the best product name from the images/files"
    lines = [
        f"PRODUCT NAME: {name}",
        f"CATEGORY: {p.category or 'let AI detect'}",
        f"PREFERRED STYLE: {style}",
        f"TARGET AUDIENCE: {p.target_audience or 'let AI infer the best-converting audience'}",
        f"SELLER NOTES / EXTRA INPUT: {p.notes or 'none'}",
        f"UPLOADED FILES: {file_list}",
    ]
    if getattr(p, "brand_name", None):
        lines.append(f"BRAND NAME: {p.brand_name} — weave it into the brand plan and image set.")
    if getattr(p, "color_preferences", None):
        lines.append(f"BRAND COLOR PREFERENCES: {p.color_preferences}")
    if getattr(p, "file_link", None):
        lines.append(f"PRODUCT FILE LINK (e.g. Canva): {p.file_link}")
    return "\n".join(lines)


def _market_block(keyword: str) -> str:
    snap = fetch_market_snapshot(keyword)
    return snap.render() if snap.ok else ""


def generate(product, competitors: str = "", keywords: str = "") -> tuple[ListingResult, dict]:
    extra = "\n".join(filter(None, [
        f"COMPETITOR EXAMPLES PROVIDED BY SELLER:\n{competitors}" if competitors else "",
        f"EXISTING KEYWORDS TO CONSIDER:\n{keywords}" if keywords else "",
    ]))
    market = _market_block(product.name)
    text = (
        "Analyze this digital product and produce a complete, optimized Etsy "
        "listing strategy designed to outperform current best-sellers.\n\n"
        + build_product_brief(product)
        + (f"\n\n{extra}" if extra else "")
        + (f"\n\n{market}" if market else "")
    )
    # ground the whole listing in the real product images + product files
    files = [f for f in (product.files or []) if isinstance(f, dict) and f.get("path")]
    image_paths = [f["path"] for f in files if f.get("kind") != "asset"]
    asset_files = [f for f in files if f.get("kind") == "asset"]
    blocks = _image_blocks(image_paths) if image_paths else []
    asset_blocks, inventory = _asset_context(asset_files)
    if inventory:
        text += "\n\n" + inventory
    if blocks or asset_blocks:
        text = ("The attached images and files ARE the product — ground every "
                "claim (what's included, page/file counts, style, intended use) "
                "in what they actually contain.\n\n" + text)
        content: str | list = blocks + asset_blocks + [{"type": "text", "text": text}]
    else:
        content = text
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


# ==============================================================================
# GROWTH LAB — the Etsy product strategist tools
# ==============================================================================

# --- 1. Thumbnail Optimization Simulator --------------------------------------

class ThumbnailVariation(BaseModel):
    n: int = Field(ge=1, le=10)
    concept: str = Field(description="One-line concept for this thumbnail variation.")
    textPlacement: str
    productSize: str = Field(description="How much of the frame the product fills and why.")
    colorContrast: str
    visualHierarchy: str = Field(description="What the eye hits 1st/2nd/3rd at 180px.")
    predictedCtr: int = Field(ge=0, le=100, description="Predicted click-through strength 0-100.")
    reasoning: str = Field(description="Why this variation earns or loses clicks in the search grid.")


class ThumbnailSimulation(BaseModel):
    variations: list[ThumbnailVariation] = Field(min_length=5, max_length=10)
    winner: int = Field(description="The n of the highest-predicted-CTR variation.")
    winnerRationale: str
    competitorComparison: str = Field(
        description="How the winning thumbnail differs from what competitors in this niche do.")


THUMBNAIL_SYSTEM = (
    "You are Etsy Growth AI's Thumbnail Optimization Simulator. The thumbnail "
    "is the single biggest click factor on Etsy: a 180px tile competing in a "
    "40-tile search grid. Design 5-10 DISTINCT thumbnail variations for this "
    "product and predict each one's click-through strength.\n\n"
    "Vary deliberately across: text placement (none / top band / bottom band / "
    "corner badge), product size in frame, color contrast strategy, and visual "
    "hierarchy. Judge every variation at 180px mobile scale. predictedCtr must "
    "differentiate honestly (spread the scores; no ties at the top). Pick ONE "
    "winner and explain why it beats the niche's common thumbnail style. "
    "If live market data is provided, compare against what competitors "
    "actually do. Respond with strict JSON only."
)


def thumbnail_simulation(product, current_result: dict) -> tuple[ThumbnailSimulation, dict]:
    import json
    titles = (current_result.get("titles") or {})
    market = _market_block(product.name)
    text = (
        "Design thumbnail variations for this Etsy listing.\n\n"
        + build_product_brief(product)
        + f"\n\nLISTING TITLE: {titles.get('best', '')}"
        + f"\nTAGS: {', '.join(current_result.get('tags') or [])}"
        + (f"\n\n{market}" if market else "")
    )
    files = [f for f in (product.files or []) if isinstance(f, dict) and f.get("path")]
    image_paths = [f["path"] for f in files if f.get("kind") != "asset"]
    blocks = _image_blocks(image_paths) if image_paths else []
    content: str | list = (blocks + [{"type": "text", "text": text}]) if blocks else text
    return structured_call(THUMBNAIL_SYSTEM, content, ThumbnailSimulation,
                           max_tokens=6000, temperature=0.7)


# --- 2. Product Upgrade Generator ----------------------------------------------

class UpgradeItem(BaseModel):
    addition: str = Field(description="The concrete add-on, e.g. 'matching phone wallpapers'.")
    whyItWorks: str
    effort: str = Field(description="low | medium | high — how hard for the seller to produce.")
    valueImpact: str = Field(description="How it changes perceived value.")


class UpgradePlan(BaseModel):
    currentOffer: str = Field(description="Plain summary of what the product is today.")
    upgrades: list[UpgradeItem] = Field(min_length=4, max_length=8)
    upgradedOffer: str = Field(description="The new, stronger bundle described as one offer.")
    priceFrom: float = Field(gt=0)
    priceTo: float = Field(gt=0)
    pricingRationale: str


UPGRADE_SYSTEM = (
    "You are Etsy Growth AI's Product Upgrade Generator. Take the seller's "
    "current digital product and design upgrades that raise its PERCEIVED "
    "VALUE and justify a meaningfully higher price (e.g. $5 -> $15).\n\n"
    "Upgrades must be realistic digital add-ons the same seller could produce "
    "(matching wallpapers, editable Canva version, bonus templates, journal "
    "prompts, tracker pages, extra formats). Prefer low-effort/high-perceived-"
    "value additions first. priceFrom = a fair price for the current offer; "
    "priceTo = the upgraded bundle price. Respond with strict JSON only."
)


def upgrade_plan(product, current_result: dict) -> tuple[UpgradePlan, dict]:
    pricing = (current_result.get("pricing") or {})
    text = (
        "Design the upgrade plan for this product.\n\n"
        + build_product_brief(product)
        + f"\n\nCURRENT RECOMMENDED PRICE: ${pricing.get('recommended', 'unknown')}"
        + f"\nWHAT'S INCLUDED TODAY: {', '.join((current_result.get('description') or {}).get('included') or []) or 'see product brief'}"
    )
    return structured_call(UPGRADE_SYSTEM, text, UpgradePlan,
                           max_tokens=4000, temperature=0.7)


# --- 3. Product Expansion Engine -----------------------------------------------

class ExpansionIdea(BaseModel):
    name: str
    subcategory: str = Field(description="Best-fit subcategory from the product taxonomy.")
    whyItSells: str
    priceRange: str = Field(description="e.g. '$6-$12'")


class ExpansionPlan(BaseModel):
    collectionName: str = Field(
        description="The cohesive series brand tying the catalog together.")
    ideas: list[ExpansionIdea] = Field(min_length=12, max_length=20)
    launchOrder: list[str] = Field(
        min_length=3, description="Which 3-5 to launch first and why, as short lines.")
    crossSellStrategy: str


EXPANSION_SYSTEM = (
    "You are Etsy Growth AI's Product Expansion Engine. From ONE product, "
    "design the related-product catalog that turns a single listing into a "
    "revenue-generating shop (e.g. moon phase digital paper -> astrology "
    "journal, tarot card backgrounds, lunar planner, zodiac stickers, crystal "
    "worksheets, manifestation workbook).\n\n"
    "Every idea must share the same buyer and aesthetic so the shop cross-"
    "sells naturally. Name a cohesive collection brand and give each idea a "
    "realistic Etsy price range. Respond with strict JSON only."
)


def expansion_plan(product, current_result: dict) -> tuple[ExpansionPlan, dict]:
    brand = (current_result.get("brand") or {})
    text = (
        "Design the product expansion catalog.\n\n"
        + build_product_brief(product)
        + f"\n\nBRAND POSITIONING: {brand.get('positioningStatement', '')}"
        + f"\nIDEAL CUSTOMER: {brand.get('idealCustomer', '')}"
    )
    return structured_call(EXPANSION_SYSTEM, text, ExpansionPlan,
                           max_tokens=6000, temperature=0.8)


# --- 4. Beat-the-Best-Seller mode ----------------------------------------------

class CompetitorProfile(BaseModel):
    title: str
    price: float | None = None
    tags: list[str] = Field(default_factory=list)
    imageCount: int | None = None
    reviewSignals: list[str] = Field(
        default_factory=list,
        description="What buyers praise and complain about in the reviews.")
    strengths: list[str] = Field(min_length=2)
    weaknesses: list[str] = Field(min_length=2)


class CompetitorTeardown(BaseModel):
    competitor: CompetitorProfile
    gaps: list[str] = Field(min_length=3, description="Openings the competitor leaves.")
    positioningPlan: str = Field(
        description="How the seller's product wins: positioning, offer, imagery, keywords.")
    upgradedOffer: str = Field(
        description="The concrete stronger offer, e.g. '150-page planner + stickers + trackers + editable Canva version'.")
    data_source: str = "model_knowledge"   # set by the engine, never the model


TEARDOWN_SYSTEM = (
    "You are Etsy Growth AI's Beat-the-Best-Seller engine. You are given a "
    "competitor Etsy listing and the seller's own product. Tear the competitor "
    "down honestly — real strengths, real weaknesses, what its reviews signal "
    "— then design the plan that BEATS it: sharper positioning, a stronger "
    "offer, better imagery, better keywords.\n\n"
    "IF MEASURED COMPETITOR DATA is provided (fetched live from Etsy), it is "
    "ground truth — quote its actual title/price/tags/reviews. If not, reason "
    "from the URL/description given and never invent measured numbers. "
    "Respond with strict JSON only."
)


def _parse_etsy_listing_id(url: str) -> str | None:
    import re
    m = re.search(r"etsy\.com/(?:[a-z]{2}(?:-[a-zA-Z]{2})?/)?listing/(\d+)", url)
    return m.group(1) if m else None


def fetch_competitor_facts(url: str) -> tuple[str, str]:
    """Live competitor fetch → (facts_text, data_source). Degrades honestly."""
    from .etsy.client import EtsyClient
    listing_id = _parse_etsy_listing_id(url)
    if not listing_id:
        return f"COMPETITOR URL (could not parse a listing id): {url}", "model_knowledge"
    client = EtsyClient()
    if not client.api_key:
        return (f"COMPETITOR LISTING URL: {url} (no ETSY_API_KEY configured — "
                "no live data available)"), "model_knowledge"
    try:
        row = client.get_listing_public(listing_id)
    except Exception as exc:
        return f"COMPETITOR LISTING URL: {url} (live fetch failed: {exc})", "model_knowledge"
    price = row.get("price") or {}
    try:
        price_str = f"${int(price.get('amount', 0)) / int(price.get('divisor', 100)):.2f}"
    except (TypeError, ValueError, ZeroDivisionError):
        price_str = "unknown"
    reviews_txt = ""
    try:
        reviews = client.get_listing_reviews_public(listing_id, limit=20)
        snippets = [f"[{r.get('rating', '?')}/5] {str(r.get('review', ''))[:200]}"
                    for r in reviews if r.get("review")][:12]
        if snippets:
            reviews_txt = "\nRECENT REVIEWS:\n" + "\n".join(snippets)
    except Exception:
        pass
    facts = (
        "MEASURED COMPETITOR DATA (fetched live from Etsy right now — ground truth):\n"
        f"TITLE: {row.get('title', '')}\n"
        f"PRICE: {price_str}\n"
        f"TAGS: {', '.join(row.get('tags') or [])}\n"
        f"IMAGE COUNT: {len(row.get('images') or []) or row.get('num_images', 'unknown')}\n"
        f"FAVORITES: {row.get('num_favorers', 'unknown')} | VIEWS: {row.get('views', 'unknown')}\n"
        f"DESCRIPTION (first 1500 chars):\n{str(row.get('description', ''))[:1500]}"
        + reviews_txt
    )
    return facts, "live_etsy_data"


def beat_competitor(product, competitor_url: str) -> tuple[CompetitorTeardown, ListingResult, dict]:
    """Teardown the competitor, then rebuild the seller's ENTIRE listing to
    outperform it. Returns (teardown, rebuilt ListingResult, usage)."""
    facts, source = fetch_competitor_facts(competitor_url)

    teardown, u1 = structured_call(
        TEARDOWN_SYSTEM,
        "Tear down this competitor and design the winning plan.\n\n"
        f"{facts}\n\nSELLER'S PRODUCT:\n{build_product_brief(product)}",
        CompetitorTeardown, max_tokens=4000, temperature=0.6)
    teardown.data_source = source  # engine-enforced provenance

    directive = (
        "BEAT THIS SPECIFIC COMPETITOR. Rebuild the entire listing to "
        "outperform it using the teardown below: position against its "
        "weaknesses, exceed its offer (upgradedOffer), out-keyword it, and "
        "out-image it. Do not copy its title or copy — beat them.\n\n"
        f"COMPETITOR TEARDOWN:\n{teardown.model_dump_json(indent=1)}\n\n{facts}"
    )
    result, u2 = generate(product, competitors=directive)
    usage = {"tokens_in": u1["tokens_in"] + u2["tokens_in"],
             "tokens_out": u1["tokens_out"] + u2["tokens_out"]}
    return teardown, result, usage


# --- 5. One-click Etsy listing package ------------------------------------------

def build_package(product, result: dict) -> str:
    """Assemble the ready-to-upload package as paste-friendly markdown."""
    r = result
    pa = r.get("productAnalysis") or {}
    d = r.get("description") or {}
    pricing = r.get("pricing") or {}
    beat = r.get("beatBestSellers") or {}
    gap = r.get("marketGap") or {}
    lines = [
        "ETSY LISTING PACKAGE — ready to upload",
        "=" * 50,
        "",
        "TITLE",
        (r.get("titles") or {}).get("best", ""),
        "",
        "DESCRIPTION (paste as-is)",
        d.get("fullText", ""),
        "",
        "13 TAGS (paste into the tag fields)",
        ", ".join(r.get("tags") or []),
        "",
        "CATEGORY",
        product.category or "—",
        "",
        "PRICING",
        f"${pricing.get('recommended', '—')} (range ${pricing.get('min', '—')}-${pricing.get('max', '—')})",
        pricing.get("strategy", ""),
        "",
        "CUSTOMER AVATAR",
        f"Ideal buyer: {pa.get('idealBuyer', '—')}",
        f"Buying motivation: {pa.get('buyingMotivation', '—')}",
        f"Emotional appeal: {pa.get('emotionalAppeal', '—')}",
        "",
        "PRODUCT POSITIONING",
        beat.get("positioning", "") or gap.get("strongerOffer", ""),
        f"Why buyers choose this: {beat.get('whyChooseThis', '—')}",
        "",
        "FILE DELIVERY INSTRUCTIONS",
        f"Files: {d.get('fileDetails', '—')}",
        f"Instructions: {d.get('instructions', '—')}",
        f"Compatibility: {d.get('compatibility', '—')}",
        "",
        "10 LISTING IMAGES (build to this plan)",
    ]
    for img in r.get("images") or []:
        lines.append(f"{img.get('n')}. {img.get('title')} — {img.get('purpose')}")
        lines.append(f"   Psychology: {img.get('psychology')} | Overlay: {img.get('copyOverlay')}")
        lines.append(f"   Layout: {img.get('layout')} | Mockup: {img.get('mockup')}")
    return "\n".join(lines)
