"""Outbound webhooks: sign + POST events to an org's configured CRM URL.

Single-process delivery (fire-and-forget task) with a few retries. Correct for
a single-VPS / single uvicorn-worker setup. To scale to multiple workers, move
delivery onto a shared queue (e.g. Redis/RQ, Celery) — only `schedule()` and
the trigger call sites change; the sign/payload format stays identical.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timezone

import httpx

from app.db.base import SessionLocal
from app.db.models import Organization

logger = logging.getLogger(__name__)

_RETRY_DELAYS = [0, 3, 10]  # seconds before each of 3 attempts


def generate_secret() -> str:
    return "whsec_" + secrets.token_hex(24)


def sign(secret: str, body: str) -> str:
    digest = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _build(event: str, data: dict) -> str:
    payload = {
        "event": event,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    return json.dumps(payload, separators=(",", ":"))


async def _post_with_retry(url: str, body: str, headers: dict) -> bool:
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt, delay in enumerate(_RETRY_DELAYS, 1):
            if delay:
                await asyncio.sleep(delay)
            try:
                r = await client.post(url, content=body, headers=headers)
                if 200 <= r.status_code < 300:
                    return True
                logger.warning("webhook %s attempt %d -> HTTP %s", url, attempt, r.status_code)
            except Exception as e:
                logger.warning("webhook %s attempt %d error: %s", url, attempt, e)
    return False


async def deliver(org_id: str, event: str, data: dict) -> bool:
    """Deliver one event to the org's webhook, if enabled. Returns success."""
    with SessionLocal() as db:
        org = db.get(Organization, org_id)
        if not org or not org.webhook_enabled or not org.webhook_url or not org.webhook_secret:
            return False
        url, secret = org.webhook_url, org.webhook_secret

    body = _build(event, data)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": event,
        "X-Webhook-Signature": sign(secret, body),
    }
    ok = await _post_with_retry(url, body, headers)
    if not ok:
        logger.error("webhook delivery FAILED org=%s event=%s url=%s", org_id, event, url)
    return ok


def schedule(org_id: str, event: str, data: dict) -> None:
    """Fire-and-forget from within a running event loop (e.g. the WS handler)."""
    try:
        asyncio.create_task(deliver(org_id, event, data))
    except RuntimeError:
        logger.warning("no event loop to schedule webhook %s", event)


async def deliver_test(org_id: str) -> bool:
    """Send a ping event so the org can verify their endpoint + signature."""
    return await deliver(
        org_id,
        "ping",
        {"message": "Test webhook from your chatbot platform."},
    )
