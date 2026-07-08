"""Notification service — one funnel for every user-facing event."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .database import Notification


def notify(db: Session, user_id: str, kind: str, title: str,
           body: str = "", link: str | None = None) -> Notification:
    n = Notification(user_id=user_id, kind=kind, title=title, body=body, link=link)
    db.add(n)
    db.commit()
    return n


def notify_generation(db: Session, user_id: str, listing_id: str,
                      listing_title: str, ok: bool, error: str | None = None):
    if ok:
        notify(db, user_id, "generation", "Listing generated",
               f"“{listing_title[:60]}” is ready to review.", listing_id)
    else:
        notify(db, user_id, "generation", "Generation failed",
               f"“{listing_title[:60]}”: {error or 'unknown error'}", listing_id)


def notify_publish(db: Session, user_id: str, listing_id: str,
                   ok: bool, etsy_url: str = "", error: str | None = None):
    if ok:
        notify(db, user_id, "publish", "Published to Etsy", etsy_url, listing_id)
    else:
        notify(db, user_id, "publish", "Publishing failed", error or "", listing_id)


def notify_low_credits(db: Session, user_id: str, remaining: int, limit: int):
    # fire once per threshold crossing: skip if an unread credits notice exists
    exists = (db.query(Notification)
              .filter(Notification.user_id == user_id,
                      Notification.kind == "credits",
                      Notification.read.is_(False)).first())
    if exists is None:
        notify(db, user_id, "credits", "Credits running low",
               f"{remaining} of {limit} listing generations left this cycle.")


def notify_batch(db: Session, user_id: str, batch_id: str, done: int, failed: int):
    notify(db, user_id, "batch", "Bulk generation finished",
           f"{done} listings generated" + (f", {failed} failed" if failed else "") + ".",
           f"batch:{batch_id}")


def notify_optimization(db: Session, user_id: str, listing_id: str, summary: str):
    notify(db, user_id, "optimization", "Optimization opportunity", summary, listing_id)
