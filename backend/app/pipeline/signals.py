"""
Input Signal Extraction — deterministic computation layer.

Extracts measurable signals from raw seller inputs (title, description, price,
images). These signals feed:
  1. the Buyer Decision Engine's stage scores (blended with model assessment)
  2. the multi-signal category classifier
  3. the Conversion Scoring Engine

Everything here is pure computation: testable, reproducible, no LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict


# --- lexicons ---------------------------------------------------------------

DIGITAL_TERMS = ["digital download", "instant download", "printable", "svg", "png file",
                 "jpg file", "pdf", "template", "clipart", "digital paper", "dpi", "digital file"]
PHYSICAL_TERMS = ["handmade", "ships", "shipping", "sterling", "ceramic", "wood", "leather",
                  "cotton", "linen", "hand poured", "hand carved", "made to order"]
POD_TERMS = ["t-shirt", "tshirt", "sweatshirt", "hoodie", "mug", "tote", "unisex",
             "bella canvas", "gildan", "printed on demand", "poster print", "sizes s-", "size chart"]
GIFT_TERMS = ["personalized", "personalised", "custom name", "monogram", "engraved",
              "gift for", "anniversary", "wedding gift", "birthday gift", "mother's day",
              "father's day", "custom text", "customized"]
SAAS_TERMS = ["subscription", "software", "app access", "dashboard", "login", "saas",
              "tool access", "lifetime access", "account", "api"]

SPEC_PATTERNS = [
    r"\b\d+\s?x\s?\d+\s?(in|inch|inches|cm|mm|px)\b",
    r"\b\d{2,4}\s?dpi\b",
    r"\b\d+\s?(files?|pages?|pieces?|designs?|textures?|templates?)\b",
    r"\b(jpg|jpeg|png|pdf|svg|eps|psd|docx|xlsx)\b",
]
TRUST_TERMS = ["guarantee", "refund", "return", "review", "handmade", "small business",
               "since \\d{4}", "commercial use", "license", "support"]
USE_TERMS = ["perfect for", "use for", "great for", "ideal for", "wear", "display",
             "decorate", "print", "frame", "apply"]
VALUE_TERMS = ["included", "includes", "bundle", "pack of", "set of", "bonus", "free"]
OBJECTION_TERMS = ["faq", "how it works", "delivery", "processing time", "compatib",
                   "requirements", "please note", "refund", "return policy", "size guide"]


@dataclass
class InputSignals:
    # raw metrics
    title_len: int = 0
    title_frontload_words: list[str] = field(default_factory=list)
    desc_len: int = 0
    desc_line_count: int = 0
    image_count: int = 0
    has_price: bool = False

    # detection counts
    spec_hits: int = 0
    trust_hits: int = 0
    use_hits: int = 0
    value_hits: int = 0
    objection_hits: int = 0

    # category term hits
    category_hits: dict = field(default_factory=dict)

    # derived heuristic stage scores, 0-100
    attention_signal: int = 0
    interpretation_signal: int = 0
    trust_signal: int = 0
    usage_imagination_signal: int = 0
    value_justification_signal: int = 0
    objection_signal: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _count_hits(text: str, terms: list[str]) -> int:
    return sum(1 for t in terms if re.search(t if "\\" in t else re.escape(t), text))


def _clamp(v: float) -> int:
    return int(max(0, min(100, round(v))))


def extract(title: str, description: str, price: float | None,
            image_count: int) -> InputSignals:
    t = (title or "").lower()
    d = (description or "").lower()
    full = f"{t}\n{d}"

    s = InputSignals(
        title_len=len(title or ""),
        title_frontload_words=(title or "")[:40].split(),
        desc_len=len(description or ""),
        desc_line_count=len([ln for ln in (description or "").splitlines() if ln.strip()]),
        image_count=image_count,
        has_price=price is not None,
        spec_hits=sum(len(re.findall(p, full)) for p in SPEC_PATTERNS),
        trust_hits=_count_hits(full, TRUST_TERMS),
        use_hits=_count_hits(full, USE_TERMS),
        value_hits=_count_hits(full, VALUE_TERMS),
        objection_hits=_count_hits(full, OBJECTION_TERMS),
        category_hits={
            "digital_product": _count_hits(full, DIGITAL_TERMS),
            "physical_product": _count_hits(full, PHYSICAL_TERMS),
            "print_on_demand": _count_hits(full, POD_TERMS),
            "gift_personalized": _count_hits(full, GIFT_TERMS),
            "saas_tool": _count_hits(full, SAAS_TERMS),
        },
    )

    # --- heuristic stage signals (0-100 baselines) ---------------------------
    # attention: can the raw inputs even produce a distinct thumbnail + title hook?
    s.attention_signal = _clamp(
        30
        + (25 if s.image_count > 0 else 0)
        + (15 if s.image_count >= 3 else 0)
        + (15 if 30 <= s.title_len <= 140 else 0)
        + (15 if len(s.title_frontload_words) >= 4 else 0)
    )
    # interpretation: specs answer "what is this / what do I get"
    s.interpretation_signal = _clamp(15 + 18 * min(s.spec_hits, 4) + (13 if s.desc_len > 200 else 0))
    # trust: legitimacy/quality signals in copy + photos
    s.trust_signal = _clamp(10 + 18 * min(s.trust_hits, 4) + (18 if s.image_count >= 4 else 0))
    # usage imagination: use-case language + contextual photos
    s.usage_imagination_signal = _clamp(10 + 20 * min(s.use_hits, 3) + (30 if s.image_count >= 5 else 0))
    # value justification: what's-included + price context
    s.value_justification_signal = _clamp(
        10 + 20 * min(s.value_hits, 3) + (15 if s.has_price else 0) + (15 if s.spec_hits >= 2 else 0)
    )
    # objection handling: policies/FAQ/compatibility present
    s.objection_signal = _clamp(5 + 24 * min(s.objection_hits, 4))

    return s
