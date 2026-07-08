"""
Billing layer — subscription-ready with usage metering.

Design: plan quotas enforced locally (works with zero Stripe config for dev and
free tier). When STRIPE_SECRET_KEY is set, checkout + webhook endpoints upgrade
users to paid plans. Usage records double as Stripe metered-billing events.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import get_settings
from .database import UsageRecord, User

settings = get_settings()

PLANS = {
    "free":  {"listings_per_month": settings.free_tier_listings_per_month, "price_usd": 0},
    "pro":   {"listings_per_month": settings.pro_tier_listings_per_month, "price_usd": 29},
    "scale": {"listings_per_month": 10_000, "price_usd": 99},
}


def month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def listings_used_this_month(db: Session, user: User) -> int:
    return (
        db.query(func.count(UsageRecord.id))
        .filter(
            UsageRecord.user_id == user.id,
            UsageRecord.kind == "listing_generation",
            UsageRecord.created_at >= month_start(),
        )
        .scalar() or 0
    )


def check_quota(db: Session, user: User) -> tuple[bool, dict]:
    plan = PLANS.get(user.plan, PLANS["free"])
    used = listings_used_this_month(db, user)
    remaining = max(plan["listings_per_month"] - used, 0)
    return remaining > 0, {
        "plan": user.plan,
        "used": used,
        "limit": plan["listings_per_month"],
        "remaining": remaining,
    }


def record_usage(db: Session, user: User, listing_id: str, usage: dict) -> None:
    db.add(UsageRecord(
        user_id=user.id,
        kind="listing_generation",
        listing_id=listing_id,
        tokens_in=usage.get("tokens_in", 0),
        tokens_out=usage.get("tokens_out", 0),
    ))
    db.commit()


# --- Stripe integration (activated when keys are configured) ----------------

def stripe_enabled() -> bool:
    return bool(settings.stripe_secret_key)


def create_checkout_session(user: User, plan: str, success_url: str, cancel_url: str) -> str:
    """Returns a Stripe Checkout URL. Requires `pip install stripe` + keys."""
    if not stripe_enabled():
        raise RuntimeError("Stripe is not configured. Set STRIPE_SECRET_KEY.")
    import stripe  # deferred import so dev works without the dependency
    stripe.api_key = settings.stripe_secret_key
    prices = {"pro": "price_pro_placeholder", "scale": "price_scale_placeholder"}
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=user.email,
        line_items=[{"price": prices[plan], "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user.id, "plan": plan},
    )
    return session.url


def handle_webhook_event(db: Session, event: dict) -> None:
    """Minimal webhook handler: upgrades/downgrades plans from Stripe events."""
    etype = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    if etype == "checkout.session.completed":
        user_id = data.get("metadata", {}).get("user_id")
        plan = data.get("metadata", {}).get("plan", "pro")
        user = db.get(User, user_id)
        if user:
            user.plan = plan
            user.stripe_customer_id = data.get("customer")
            db.commit()
    elif etype in ("customer.subscription.deleted", "invoice.payment_failed"):
        customer = data.get("customer")
        user = db.query(User).filter(User.stripe_customer_id == customer).first()
        if user:
            user.plan = "free"
            db.commit()
