import json
import logging
from typing import cast

from openai import APIConnectionError, APIStatusError, OpenAI
from openai.types.shared_params import ResponseFormatJSONSchema
from sqlalchemy.orm import Session

from app.config import settings
from app.models.article import Article
from app.services import article_repository

logger = logging.getLogger(__name__)

_client = OpenAI(api_key=settings.openai_api_key)

_SYSTEM_PROMPT = (
    "You analyse news articles. Given a title, description, and content, "
    "produce a 2-3 sentence summary and classify the overall sentiment as "
    "exactly one of: positive, neutral, negative."
)

_RESPONSE_SCHEMA: ResponseFormatJSONSchema = {
    "type": "json_schema",
    "json_schema": {
        "name": "article_analysis",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "sentiment": {
                    "type": "string",
                    "enum": ["positive", "neutral", "negative"],
                },
            },
            "required": ["summary", "sentiment"],
            "additionalProperties": False,
        },
    },
}

_STATUS_MESSAGES = {
    401: "Analysis is temporarily unavailable",
    403: "Country, region, or territory not supported",
    429: "Too many requests -- please wait a moment and try again",
    500: "Analysis failed -- please try again",
    503: "Analysis failed -- please try again",
}


class AnalysisError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def analyse_article(title: str, description: str | None, content: str | None) -> dict:
    """Summarise an article and classify its sentiment via a single OpenAI call.

    Returns {"summary": str, "sentiment": "positive"|"neutral"|"negative"}.
    Raises AnalysisError (never the raw OpenAI exception, and never an
    unhandled crash on a refused or malformed response) on any failure.
    """
    user_content = (
        f"Title: {title}\nDescription: {description or ''}\nContent: {content or ''}"
    )

    try:
        response = _client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format=_RESPONSE_SCHEMA,
        )
    except APIStatusError as exc:
        status_code = exc.status_code
        if status_code in (401, 403):
            logger.error("OpenAI auth error (status %s): %s", status_code, exc)
        message = _STATUS_MESSAGES.get(
            status_code, "Analysis failed -- please try again"
        )
        raise AnalysisError(message, status_code=status_code) from exc
    except APIConnectionError as exc:
        raise AnalysisError("Analysis failed -- please try again") from exc

    try:
        result = json.loads(cast(str, response.choices[0].message.content))
        return {"summary": result["summary"], "sentiment": result["sentiment"]}
    except (TypeError, ValueError, KeyError) as exc:
        raise AnalysisError("Analysis failed -- please try again") from exc


def analyse_and_store(db: Session, request_data: dict) -> Article:
    """Analyse and persist an article, or return its existing row if already analysed.

    Checks for an existing row by URL *before* calling OpenAI, so a previously-analysed
    article never triggers a second (wasted) API call. This is a first line of defense,
    and not the only one -- `insert_article`'s own unique-constraint handling covers the
    remaining race window.
    """
    existing = article_repository.get_by_url(db, request_data["url"])
    if existing is not None:
        return existing

    analysis = analyse_article(
        title=request_data["title"],
        description=request_data.get("description"),
        content=request_data.get("content"),
    )

    return article_repository.insert_article(
        db,
        {
            **request_data,
            "summary": analysis["summary"],
            "sentiment": analysis["sentiment"],
        },
    )
