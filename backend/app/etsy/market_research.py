"""
Live Etsy market research for the Competitor Intelligence Engine.

Fetches the top active Etsy listings for the product's primary keyword at
GENERATION time (public-scope API — needs only ETSY_API_KEY, no shop OAuth)
and reduces them to a deterministic MarketSnapshot: real price distribution,
real title language, real tag usage, real favorite counts. The snapshot is
injected into the Competitor Intelligence Engine prompt so its analysis is
grounded in what is actually ranking on Etsy today, and stored on the output
so every claim is auditable.

Failure is never fatal: no API key, a network error, or an empty result set
degrades to model-knowledge-only analysis with the data source labeled
honestly.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field

from .client import EtsyClient

log = logging.getLogger("listingforge.market")

SEARCH_LIMIT = 25
# words too generic to tell us anything about a niche
STOPWORDS = {
    "the", "and", "for", "with", "your", "you", "this", "that", "from", "are",
    "digital", "download", "instant", "printable", "file", "files", "etsy",
    "png", "jpg", "pdf", "svg", "set", "pack", "diy", "new", "gift",
}


@dataclass
class MarketSnapshot:
    keyword: str
    listings_analyzed: int = 0
    price_min: float | None = None
    price_median: float | None = None
    price_max: float | None = None
    avg_favorites: float | None = None
    top_title_terms: list[str] = field(default_factory=list)   # ["term (12/25)", ...]
    top_tags: list[str] = field(default_factory=list)
    sample_titles: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.listings_analyzed > 0

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "listings_analyzed": self.listings_analyzed,
            "price_min": self.price_min,
            "price_median": self.price_median,
            "price_max": self.price_max,
            "avg_favorites": self.avg_favorites,
            "top_title_terms": self.top_title_terms,
            "top_tags": self.top_tags,
            "sample_titles": self.sample_titles,
            "error": self.error,
        }

    def render(self) -> str:
        """Prompt block: the measured market, stated as facts with counts."""
        if not self.ok:
            return ""
        lines = [
            f"LIVE ETSY MARKET DATA — top {self.listings_analyzed} active listings "
            f'for "{self.keyword}" (fetched now, sorted by Etsy relevance):',
            f"- Price range: ${self.price_min:.2f}-${self.price_max:.2f}, "
            f"median ${self.price_median:.2f}",
        ]
        if self.avg_favorites is not None:
            lines.append(f"- Average favorites per listing: {self.avg_favorites:.0f}")
        if self.top_title_terms:
            lines.append("- Most frequent title terms (term, listings using it): "
                         + ", ".join(self.top_title_terms))
        if self.top_tags:
            lines.append("- Most frequent tags: " + ", ".join(self.top_tags))
        if self.sample_titles:
            lines.append("- Sample competing titles:")
            lines += [f'  * "{t}"' for t in self.sample_titles]
        return "\n".join(lines)


def _price(row: dict) -> float | None:
    p = row.get("price") or {}
    try:
        amount, divisor = int(p.get("amount", 0)), int(p.get("divisor", 100))
        return amount / divisor if amount > 0 and divisor > 0 else None
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def aggregate(keyword: str, rows: list[dict]) -> MarketSnapshot:
    """Pure reduction of raw listing rows → snapshot. No network, testable."""
    snap = MarketSnapshot(keyword=keyword, listings_analyzed=len(rows))
    if not rows:
        return snap

    prices = [p for p in (_price(r) for r in rows) if p is not None]
    if prices:
        snap.price_min = round(min(prices), 2)
        snap.price_median = round(_median(prices), 2)
        snap.price_max = round(max(prices), 2)

    favs = [r.get("num_favorers") for r in rows if isinstance(r.get("num_favorers"), int)]
    if favs:
        snap.avg_favorites = round(sum(favs) / len(favs), 1)

    kw_words = set(keyword.lower().split())
    term_hits: Counter = Counter()
    for r in rows:
        words = set(re.findall(r"[a-z]{3,}", str(r.get("title", "")).lower()))
        for w in words - STOPWORDS - kw_words:
            term_hits[w] += 1
    # only terms multiple competitors converge on are market signal
    snap.top_title_terms = [f"{w} ({n}/{len(rows)})"
                            for w, n in term_hits.most_common(12) if n >= 2]

    tag_hits: Counter = Counter()
    for r in rows:
        for t in (r.get("tags") or []):
            tag_hits[str(t).lower()] += 1
    snap.top_tags = [f"{t} ({n})" for t, n in tag_hits.most_common(15) if n >= 2]

    snap.sample_titles = [str(r.get("title", ""))[:140] for r in rows[:6] if r.get("title")]
    return snap


def fetch_market_snapshot(keyword: str, client: EtsyClient | None = None,
                          limit: int = SEARCH_LIMIT) -> MarketSnapshot:
    """Live fetch + aggregate. Degrades to an empty snapshot (with the reason
    recorded) instead of raising — market research must never kill a pipeline."""
    client = client or EtsyClient()
    if not client.api_key:
        return MarketSnapshot(keyword=keyword, error="ETSY_API_KEY not configured")
    try:
        rows = client.search_active_public(keyword, limit=limit)
    except Exception as exc:
        log.warning("market research fetch failed for %r: %s", keyword, exc)
        return MarketSnapshot(keyword=keyword, error=f"fetch failed: {exc}")
    return aggregate(keyword, rows)
