"""
Central AI Context Manager — the single source of truth for a listing run.

Every pipeline module reads from and writes to a ListingContext instead of
rebuilding knowledge independently. Each write records provenance (which
module, when), so the decision trail is auditable. At the end of a run the
context snapshot persists to Listing.context_json, and future runs for the
same user can preload durable slots (brand, preferences, learning insights).

Slots:
  product_analysis, vision_analysis, buyer_psychology, category,
  brand_profile, brand_memory, seo_strategy, image_strategy,
  pricing_strategy, competitor_insights, review_insights,
  user_preferences, marketplace_config, performance_history,
  validation_results, optimization_history

Usage:
  ctx = ListingContext.begin(db, user_id, listing_id)
  ctx.set("product_analysis", analysis.model_dump(), source="product_analysis")
  block = ctx.prompt_block(["buyer_psychology", "brand_profile"])  # for LLM calls
  ctx.decision("image_strategy", "chose macro hero", why="vision: high texture detail")
  ctx.snapshot(db)   # persist
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("listingforge.context")

SLOTS = (
    "product_analysis", "vision_analysis", "buyer_psychology", "category",
    "brand_profile", "brand_memory", "seo_strategy", "image_strategy",
    "pricing_strategy", "competitor_insights", "review_insights",
    "user_preferences", "marketplace_config", "performance_history",
    "validation_results", "optimization_history",
)

# Slots that carry over between runs for the same user/listing.
DURABLE_SLOTS = ("brand_profile", "brand_memory", "user_preferences",
                 "marketplace_config", "performance_history",
                 "review_insights", "competitor_insights",
                 "optimization_history")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ListingContext:
    def __init__(self, user_id: str = "", listing_id: str | None = None):
        self.user_id = user_id
        self.listing_id = listing_id
        self._data: dict[str, Any] = {}
        self._meta: dict[str, dict] = {}      # slot -> {source, at, version}
        self._decisions: list[dict] = []      # ordered AI decision log

    # ------------------------------------------------------------------ core
    def set(self, slot: str, value: Any, source: str) -> None:
        if slot not in SLOTS:
            raise KeyError(f"Unknown context slot: {slot}")
        version = self._meta.get(slot, {}).get("version", 0) + 1
        self._data[slot] = value
        self._meta[slot] = {"source": source, "at": _now(), "version": version}
        log.debug("ctx[%s] <- %s (v%d)", slot, source, version)

    def get(self, slot: str, default: Any = None) -> Any:
        return self._data.get(slot, default)

    def has(self, slot: str) -> bool:
        return slot in self._data and self._data[slot] not in (None, "", {}, [])

    def decision(self, module: str, decision: str, why: str = "") -> None:
        self._decisions.append({"module": module, "decision": decision,
                                "why": why, "at": _now()})

    @property
    def decisions(self) -> list[dict]:
        return list(self._decisions)

    # ------------------------------------------------------- prompt building
    def prompt_block(self, slots: list[str] | None = None,
                     max_chars_per_slot: int = 2400) -> str:
        """Render selected slots as a compact context block for LLM prompts.

        Modules receive shared intelligence instead of re-deriving it —
        this is what prevents duplicate reasoning across the pipeline.
        """
        parts = []
        for slot in (slots or [s for s in SLOTS if self.has(s)]):
            if not self.has(slot):
                continue
            value = self._data[slot]
            text = value if isinstance(value, str) else json.dumps(value, default=str)
            if len(text) > max_chars_per_slot:
                text = text[:max_chars_per_slot] + "…[truncated]"
            parts.append(f"[{slot.upper().replace('_', ' ')}]\n{text}")
        return "\n\n".join(parts)

    # ---------------------------------------------------------- persistence
    def to_dict(self) -> dict:
        return {"user_id": self.user_id, "listing_id": self.listing_id,
                "data": self._data, "meta": self._meta,
                "decisions": self._decisions, "saved_at": _now()}

    @classmethod
    def from_dict(cls, raw: dict) -> "ListingContext":
        ctx = cls(raw.get("user_id", ""), raw.get("listing_id"))
        ctx._data = raw.get("data", {})
        ctx._meta = raw.get("meta", {})
        ctx._decisions = raw.get("decisions", [])
        return ctx

    def snapshot(self, db) -> None:
        """Persist the full context onto the listing row."""
        if db is None or not self.listing_id:
            return
        from ..database import Listing
        row = db.get(Listing, self.listing_id)
        if row is not None:
            row.context_json = self.to_dict()
            db.commit()

    # ------------------------------------------------------------ bootstrap
    @classmethod
    def begin(cls, db, user_id: str, listing_id: str | None = None) -> "ListingContext":
        """Start a run preloaded with everything durable we know:
        brand system, brand memory, learning insights, performance history,
        user preferences, marketplace config, and any prior run's durable slots.
        """
        ctx = cls(user_id, listing_id)
        if db is None:
            return ctx
        # prior snapshot for this listing (regeneration case)
        if listing_id:
            from ..database import Listing
            row = db.get(Listing, listing_id)
            if row is not None and row.context_json:
                old = cls.from_dict(row.context_json)
                for slot in DURABLE_SLOTS:
                    if old.has(slot):
                        ctx.set(slot, old.get(slot), source="previous_run")
        # brand profile
        try:
            from ..brandctx import brand_context
            bc = brand_context(db, user_id)
            if bc:
                ctx.set("brand_profile", bc, source="brand_studio")
        except Exception:
            log.warning("brand context load failed", exc_info=True)
        # brand memory (learned visual/copy preferences)
        try:
            from .brand_memory import recall
            mem = recall(db, user_id)
            if mem:
                ctx.set("brand_memory", mem, source="brand_memory")
        except Exception:
            log.warning("brand memory load failed", exc_info=True)
        # shop performance history
        try:
            from ..etsy.optimizer import performance_context
            perf = performance_context(db, user_id)
            if perf:
                ctx.set("performance_history", perf, source="etsy_optimizer")
        except Exception:
            log.warning("performance context load failed", exc_info=True)
        # learning engine insights
        try:
            from .learning_engine import learning_context
            lc = learning_context(db, user_id)
            if lc:
                ctx.set("optimization_history", lc, source="learning_engine")
        except Exception:
            log.warning("learning context load failed", exc_info=True)
        ctx.set("marketplace_config", {"marketplace": "etsy", "tag_count": 13,
                                       "title_max": 140, "image_slots": 7},
                source="config")
        return ctx
