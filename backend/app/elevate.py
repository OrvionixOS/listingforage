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
