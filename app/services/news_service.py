import logging
from datetime import datetime

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GNEWS_SEARCH_URL = "https://gnews.io/api/v4/search"

_STATUS_MESSAGES = {
    400: "Invalid search -- try a different query",
    401: "News search is temporarily unavailable",
    403: "Daily news search limit reached -- try again after midnight UTC",
    429: "Searching too quickly -- please wait a moment and try again",
    500: "News service is temporarily unavailable -- try again shortly",
    503: "News service is temporarily unavailable -- try again shortly",
}


class NewsAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _map_error(status_code: int) -> NewsAPIError:
    """Translate a gnews.io HTTP status code into a friendly NewsAPIError.

    401 additionally logs loudly server-side (it means our own GNEWS_API_KEY is
    invalid, not something the end user caused or can fix), while still returning
    the same generic user-facing message as any other outage.
    """
    if status_code == 401:
        logger.error("gnews.io returned 401 Unauthorized -- check GNEWS_API_KEY")
    message = _STATUS_MESSAGES.get(
        status_code, "News service is temporarily unavailable -- try again shortly"
    )
    return NewsAPIError(message, status_code)


def _parse_gnews_datetime(value: str) -> datetime:
    """Parse gnews.io's `publishedAt` timestamp (UTC, trailing "Z") into a datetime.

    `datetime.fromisoformat` doesn't accept a bare "Z" suffix, so it's normalized
    to the "+00:00" form first.
    """
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _map_gnews_article(item: dict) -> dict:
    """Map one raw gnews.io article to this app's internal shape.

    Drops fields we never use (gnews's own `id`, `lang`, `source.id`,
    `source.url`, `source.country`) and renames `image` -> `image_url`.
    """
    source: dict = item.get("source", {})
    return {
        "url": item["url"],
        "title": item["title"],
        "description": item.get("description"),
        "content": item.get("content"),
        "image_url": item.get("image"),
        "source_name": source.get("name", "Unknown"),
        "published_at": _parse_gnews_datetime(item["publishedAt"]),
    }


async def search_articles(query: str) -> list[dict]:
    """Search gnews.io for `query` and return results in this app's internal shape.

    Raises NewsAPIError (never the raw httpx exception) on any network-level or
    HTTP-level failure, so callers only ever need to handle one error type.
    """
    params = {"q": query, "apikey": settings.gnews_api_key, "lang": "en"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(GNEWS_SEARCH_URL, params=params)
    except httpx.RequestError as exc:
        raise NewsAPIError(
            "News service is temporarily unavailable -- try again shortly"
        ) from exc  # keep the real network error visible in logs, under the friendly message

    if response.status_code != 200:
        raise _map_error(response.status_code)

    payload: dict = response.json()
    return [_map_gnews_article(item) for item in payload.get("articles", [])]
