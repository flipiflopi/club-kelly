"""
Twitter / X posting via API v2 (OAuth 1.0a user context).
Credentials are read from Settings; if any are missing the call is silently skipped.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def post_tweet(text: str, api_key: str, api_secret: str, access_token: str, access_token_secret: str) -> bool:
    """
    Post a tweet. Returns True on success, False on failure.
    Silently skips if any credential is empty.
    """
    if not all([api_key, api_secret, access_token, access_token_secret]):
        logger.debug("Twitter credentials not configured — skipping tweet")
        return False

    try:
        import tweepy  # type: ignore[import-untyped]

        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        response = client.create_tweet(text=text)
        tweet_id = response.data["id"] if response.data else "?"
        logger.info("Tweet posted: id=%s", tweet_id)
        return True
    except Exception:
        logger.exception("Failed to post tweet")
        return False
