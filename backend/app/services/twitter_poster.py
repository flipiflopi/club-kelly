"""
Twitter / X posting via GetXAPI (third-party, pay-per-call).
Uses the account session auth_token instead of OAuth credentials.
Cost: $0.002 per tweet.
"""

from __future__ import annotations

import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.getxapi.com/twitter/tweet/create"


def post_tweet(text: str, getxapi_key: str, auth_token: str, ct0: str = "", twid: str = "") -> bool:
    """
    Post a tweet via GetXAPI. Returns True on success, False on failure.
    Silently skips if credentials are missing.
    """
    if not getxapi_key or not auth_token:
        logger.debug("GetXAPI credentials not configured — skipping tweet")
        return False

    payload: dict = {"text": text, "auth_token": auth_token}
    if ct0:
        payload["ct0"] = ct0
    if twid:
        payload["twid"] = twid

    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(ENDPOINT, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {getxapi_key}")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read())
            tweet_id = body.get("data", {}).get("id_str") or body.get("id_str") or "?"
            logger.info("Tweet posted via GetXAPI: id=%s", tweet_id)
            return True

    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        logger.error("GetXAPI HTTP %s: %s", e.code, body)
        return False
    except Exception:
        logger.exception("Failed to post tweet via GetXAPI")
        return False
