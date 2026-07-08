"""Stage 1 — Product Analysis. Turns raw seller inputs into a structured product model."""
from __future__ import annotations

import base64
from pathlib import Path

from ..schemas import ProductAnalysis
from .llm import structured_call

SYSTEM = """You are the Product Analysis module of ListingForge AI, an e-commerce
conversion intelligence system for Etsy sellers.

Your job: extract a rigorous, structured model of the product from the seller's
raw inputs (title, description, price, photos). You are NOT writing marketing
copy. You are building the factual substrate every downstream engine relies on.

Rules:
- Only state attributes supported by the inputs. Never invent materials, sizes,
  or features.
- The `ambiguities` list is your most important output: everything a first-time
  Etsy browser could NOT determine from these inputs alone. Be exhaustive and
  specific ("no dimensions given", "unclear if frame is included", "digital vs
  shipped is ambiguous").
- `target_buyer` and `buying_occasion` must be written in buyer language, not
  demographic jargon.
- `competitive_context`: what this listing sits next to in Etsy search results
  and what buyers compare it against."""


def _image_blocks(image_paths: list[str]) -> list[dict]:
    blocks = []
    for p in image_paths[:6]:
        path = Path(p)
        if not path.exists():
            continue
        media = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media,
                "data": base64.b64encode(path.read_bytes()).decode(),
            },
        })
    return blocks


def run(title: str, description: str, price: float | None,
        notes: str | None, image_paths: list[str]) -> tuple[ProductAnalysis, dict]:
    text = (
        f"SELLER INPUTS\n"
        f"Title: {title}\n"
        f"Price: {price if price is not None else 'not provided'}\n"
        f"Description:\n{description}\n"
        f"Seller notes: {notes or 'none'}\n"
        f"Photos attached: {len(image_paths)}"
    )
    content: str | list = text
    imgs = _image_blocks(image_paths)
    if imgs:
        content = imgs + [{"type": "text", "text": text}]
    return structured_call(SYSTEM, content, ProductAnalysis, max_tokens=2048)
