"""Thin client for the Facebook Graph API endpoints the tracker needs."""

import json
import logging
import time
from datetime import datetime

import requests

log = logging.getLogger("reels_tracker.graph")

# https://developers.facebook.com/docs/graph-api/overview/rate-limiting
RATE_LIMIT_CODES = {4, 17, 32, 613, 80001}
TOKEN_ERROR_CODES = {102, 190}
USAGE_HEADERS = ("X-App-Usage", "X-Page-Usage", "X-Business-Use-Case-Usage")


class GraphAPIError(Exception):
    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code


class RateLimitError(GraphAPIError):
    pass


class TokenError(GraphAPIError):
    pass


def parse_fb_time(value):
    if not value:
        return None
    # Graph API returns e.g. "2026-10-17T08:00:00+0000"
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")


def _max_usage_percent(header_value):
    """Largest percentage found anywhere in a Graph usage header."""
    try:
        data = json.loads(header_value)
    except (TypeError, ValueError):
        return 0
    stack, best = [data], 0
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                if isinstance(value, (int, float)) and key != "estimated_time_to_regain_access":
                    best = max(best, value)
                else:
                    stack.append(value)
        elif isinstance(item, list):
            stack.extend(item)
    return best


class GraphClient:
    def __init__(self, version, session=None, retries=3, backoff_seconds=2.0, sleep=time.sleep):
        self.base = f"https://graph.facebook.com/{version}"
        self.session = session or requests.Session()
        self.retries = retries
        self.backoff_seconds = backoff_seconds
        self.sleep = sleep
        self.usage_percent = 0
        self._preferred_metric = None

    def _request(self, url, params=None):
        for attempt in range(self.retries):
            try:
                resp = self.session.get(url, params=params, timeout=30)
                data = resp.json()
            except (requests.RequestException, ValueError) as e:
                if attempt == self.retries - 1:
                    raise GraphAPIError(None, f"network error: {e}") from e
                self.sleep(self.backoff_seconds * 2**attempt)
                continue
            self._record_usage(resp)
            if "error" in data:
                err = data["error"]
                code, msg = err.get("code"), err.get("message")
                if code in RATE_LIMIT_CODES:
                    raise RateLimitError(code, msg)
                if code in TOKEN_ERROR_CODES:
                    raise TokenError(code, msg)
                raise GraphAPIError(code, msg)
            return data

    def _record_usage(self, resp):
        headers = getattr(resp, "headers", None) or {}
        usage = max((_max_usage_percent(headers.get(h)) for h in USAGE_HEADERS), default=0)
        self.usage_percent = usage
        if usage >= 80:
            log.warning("Graph API usage at %d%% of the rate limit", usage)

    def get(self, path, token, **params):
        params["access_token"] = token
        return self._request(f"{self.base}/{path}", params)

    def _paginate(self, data):
        while True:
            yield from data.get("data", [])
            next_url = data.get("paging", {}).get("next")
            if not next_url:
                return
            data = self._request(next_url)

    def page_tokens_from_user_token(self, user_token):
        """Map page_id -> (page name, page access token) for every Page the user manages."""
        data = self.get("me/accounts", user_token, fields="id,name,access_token", limit=100)
        return {p["id"]: (p.get("name", p["id"]), p["access_token"]) for p in self._paginate(data)}

    def page_name(self, page_id, token):
        return self.get(page_id, token, fields="name").get("name", page_id)

    def recent_reels(self, page_id, token, since):
        """Reels on a Page created after `since` (newest first)."""
        data = self.get(
            f"{page_id}/video_reels",
            token,
            fields="id,description,permalink_url,created_time",
            limit=50,
        )
        reels = []
        for reel in self._paginate(data):
            created = parse_fb_time(reel.get("created_time"))
            if created and created < since:
                break
            reels.append(reel)
        return reels

    def reel_views(self, reel_id, token, metrics):
        """Return the view count of a Reel, or None if no metric is available."""
        ordered = sorted(metrics, key=lambda m: m != self._preferred_metric)
        for metric in ordered:
            try:
                data = self.get(f"{reel_id}/video_insights", token, metric=metric)
            except (RateLimitError, TokenError):
                raise
            except GraphAPIError as e:
                log.debug("Metric %s unavailable for %s: %s", metric, reel_id, e)
                continue
            for item in data.get("data", []):
                values = item.get("values") or []
                if values and isinstance(values[0].get("value"), (int, float)):
                    self._preferred_metric = metric
                    return int(values[0]["value"])
        return None

    def token_expires_at(self, token):
        """Expiry of a token as a UTC timestamp, 0 if it never expires, None if unknown."""
        try:
            data = self.get("debug_token", token, input_token=token).get("data", {})
        except GraphAPIError as e:
            log.debug("debug_token failed: %s", e)
            return None
        if not data.get("is_valid", True):
            raise TokenError(190, "access token is invalid or expired")
        return data.get("expires_at")
