"""Stage 1 — Product Analysis. Turns raw seller inputs into a structured product model."""
from __future__ import annotations

import base64
from pathlib import Path

from ..schemas import ProductAnalysis
from .llm import structured_call

SYSTEM = """You are the Product Analysis module of Etsy Listing AI Studio, an
automated AI Etsy listing engine for DIGITAL PRODUCTS. You act as a market
researcher and customer psychology expert.

Your job: extract a rigorous, structured model of the product from the
seller's raw inputs (title, description, price, uploaded product files/photos)
— determine product category signal, style, theme, colors, audience, buyer
intent, occasion, seasonality, market positioning, and price tier. You are NOT
writing marketing copy. You are building the factual substrate every
downstream engine relies on.

Rules:
- Only state attributes supported by the inputs. Never invent formats, sizes,
  or features that weren't shown or described.
- The `ambiguities` list is your most important output: everything a first-time
  Etsy browser could NOT determine from these inputs alone. Be exhaustive and
  specific ("no page count given", "unclear which apps this planner supports",
  "no commercial-use license stated").
- `who_buys_and_why`: directly and specifically answer "who is most likely to
  buy this product and why?" — one buyer persona, one causal reason, in plain
  language grounded in what the images/copy actually show.
- `target_buyer` and `buying_occasion` must be written in buyer language, not
  demographic jargon.
- `emotional_buying_triggers`: 2-5 specific emotional drivers behind the
  purchase (e.g. "wants an organized life without redesigning a system from
  scratch", "needs a professional look fast without hiring a designer").
- `market_positioning` and `competitive_context`: what this listing sits next
  to in Etsy search results and what buyers compare it against."""


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
