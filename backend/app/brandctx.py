"""Brand context: distills the user's BrandProfile into a prompt block."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .database import BrandProfile


def brand_context(db: Session, user_id: str) -> str:
    p = db.query(BrandProfile).filter(BrandProfile.user_id == user_id).first()
    if p is None or not p.apply_to_generations:
        return ""
    lines = ["BRAND SYSTEM (apply to all copy and image direction):"]
    if p.brand_name:
        lines.append(f"- Brand: {p.brand_name}")
    if p.voice:
        lines.append(f"- Voice: {p.voice}")
    if p.messaging_pillars:
        lines.append(f"- Messaging pillars: {', '.join(p.messaging_pillars)}")
    if p.photography_style:
        lines.append(f"- Photography style: {p.photography_style}")
    if p.palette:
        lines.append(f"- Palette: {p.palette}")
    if p.packaging_guidelines:
        lines.append(f"- Packaging: {p.packaging_guidelines}")
    return "\n".join(lines) if len(lines) > 1 else ""
