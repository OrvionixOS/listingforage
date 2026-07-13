"""
Etsy Open API v3 client.

Implements the real Etsy integration surface:
  - OAuth 2.0 with PKCE (Etsy's required flow): connect URL, code exchange,
    refresh
  - Shop lookup (getMe → shop id)
  - createDraftListing / updateListing
  - uploadListingImage (multipart, ordered by rank)
  - publish (state draft → active)
  - listing stats (views, favorites) for the analytics loop
  - active-listing search for the competitive advantage system

Transport is injectable so the publisher and tests run against a fake Etsy;
production uses httpx. Requires ETSY_API_KEY (keystring) + ETSY_REDIRECT_URI.
Scopes: listings_r listings_w shops_r transactions_r.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from typing import Any, Protocol

API = "https://api.etsy.com/v3/application"
OAUTH_CONNECT = "https://www.etsy.com/oauth/connect"
OAUTH_TOKEN = "https://api.etsy.com/v3/public/oauth/token"
SCOPES = "listings_r listings_w shops_r transactions_r"


class Transport(Protocol):
    def request(self, method: str, url: str, *, headers: dict | None = None,
                params: dict | None = None, data: dict | None = None,
                json: dict | None = None, files: dict | None = None) -> dict: ...


class HttpxTransport:
    def request(self, method: str, url: str, **kw) -> dict:
        import httpx
        resp = httpx.request(method, url, timeout=60, **kw)
        if resp.status_code >= 400:
            raise EtsyAPIError(resp.status_code, resp.text[:500])
        return resp.json() if resp.content else {}


class EtsyAPIError(RuntimeError):
    def __init__(self, status: int, body: str):
        self.status = status
        super().__init__(f"Etsy API {status}: {body}")


class EtsyClient:
    def __init__(self, api_key: str | None = None, transport: Transport | None = None):
        self.api_key = api_key or os.getenv("ETSY_API_KEY", "")
        self.redirect_uri = os.getenv("ETSY_REDIRECT_URI", "http://localhost:8000/api/etsy/callback")
        self.transport = transport or HttpxTransport()

    # ---- OAuth 2.0 PKCE -----------------------------------------------------

    def build_connect_url(self) -> tuple[str, str, str]:
        """Returns (authorize_url, state, code_verifier)."""
        state = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        url = (f"{OAUTH_CONNECT}?response_type=code"
               f"&redirect_uri={self.redirect_uri}"
               f"&scope={SCOPES.replace(' ', '%20')}"
               f"&client_id={self.api_key}"
               f"&state={state}"
               f"&code_challenge={challenge}"
               f"&code_challenge_method=S256")
        return url, state, verifier

    def exchange_code(self, code: str, code_verifier: str) -> dict:
        return self.transport.request("POST", OAUTH_TOKEN, json={
            "grant_type": "authorization_code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "code": code,
            "code_verifier": code_verifier,
        })

    def refresh(self, refresh_token: str) -> dict:
        return self.transport.request("POST", OAUTH_TOKEN, json={
            "grant_type": "refresh_token",
            "client_id": self.api_key,
            "refresh_token": refresh_token,
        })

    def _headers(self, access_token: str) -> dict:
        return {"x-api-key": self.api_key, "Authorization": f"Bearer {access_token}"}

    # ---- Shop ----------------------------------------------------------------

    def get_me(self, token: str) -> dict:
        return self.transport.request("GET", f"{API}/users/me", headers=self._headers(token))

    def get_shop(self, token: str, user_id: int | str) -> dict:
        return self.transport.request("GET", f"{API}/users/{user_id}/shops",
                                      headers=self._headers(token))

    # ---- Listings ------------------------------------------------------------

    def create_draft_listing(self, token: str, shop_id: str, payload: dict) -> dict:
        return self.transport.request(
            "POST", f"{API}/shops/{shop_id}/listings",
            headers=self._headers(token), data=payload)

    def update_listing(self, token: str, shop_id: str, listing_id: str, payload: dict) -> dict:
        return self.transport.request(
            "PATCH", f"{API}/shops/{shop_id}/listings/{listing_id}",
            headers=self._headers(token), data=payload)

    def upload_listing_image(self, token: str, shop_id: str, listing_id: str,
                             image_bytes: bytes, rank: int, filename: str) -> dict:
        return self.transport.request(
            "POST", f"{API}/shops/{shop_id}/listings/{listing_id}/images",
            headers=self._headers(token),
            data={"rank": rank},
            files={"image": (filename, image_bytes, "image/png")})

    def publish(self, token: str, shop_id: str, listing_id: str) -> dict:
        return self.update_listing(token, shop_id, listing_id, {"state": "active"})

    def get_listing(self, token: str, listing_id: str) -> dict:
        return self.transport.request(
            "GET", f"{API}/listings/{listing_id}",
            headers=self._headers(token), params={"includes": "Images"})

    # ---- Analytics + competitive search ---------------------------------------

    def get_listing_stats(self, token: str, listing_id: str) -> dict:
        """views + num_favorers come back on the listing resource."""
        data = self.get_listing(token, listing_id)
        return {"views": data.get("views", 0),
                "favorites": data.get("num_favorers", 0),
                "raw": data}

    def search_active_listings(self, token: str, keywords: str, limit: int = 10) -> list[dict]:
        data = self.transport.request(
            "GET", f"{API}/listings/active",
            headers=self._headers(token),
            params={"keywords": keywords, "limit": limit, "sort_on": "score"})
        return data.get("results", [])

    def search_active_public(self, keywords: str, limit: int = 25) -> list[dict]:
        """Active-listing search with ONLY the app keystring — no OAuth token.
        Etsy's /listings/active endpoint is public-scope, so generation-time
        market research works for every user once ETSY_API_KEY is configured,
        even before any shop is connected."""
        data = self.transport.request(
            "GET", f"{API}/listings/active",
            headers={"x-api-key": self.api_key},
            params={"keywords": keywords, "limit": limit, "sort_on": "score"})
        return data.get("results", [])

    def get_listing_public(self, listing_id: str) -> dict:
        """Single-listing fetch (title, description, price, tags, images) with
        only the app keystring — powers Beat-the-Best-Seller teardowns."""
        return self.transport.request(
            "GET", f"{API}/listings/{listing_id}",
            headers={"x-api-key": self.api_key},
            params={"includes": "Images"})

    def get_listing_reviews_public(self, listing_id: str, limit: int = 25) -> list[dict]:
        """Recent reviews for a listing (public scope) — review language feeds
        the competitor weakness analysis."""
        data = self.transport.request(
            "GET", f"{API}/listings/{listing_id}/reviews",
            headers={"x-api-key": self.api_key},
            params={"limit": limit})
        return data.get("results", [])


def token_expired(expires_at) -> bool:
    if expires_at is None:
        return True
    return time.time() >= expires_at.timestamp() - 120
