from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.article import Article


def get_by_url(db: Session, url: str) -> Article | None:
    """Look up a stored article by its source URL, or None if never analysed."""
    return db.execute(select(Article).where(Article.url == url)).scalar_one_or_none()


def get_by_id(db: Session, article_id: int) -> Article | None:
    """Look up a stored article by its primary key, or None if it doesn't exist."""
    return db.get(Article, article_id)


def insert_article(db: Session, data: dict) -> Article:
    """Insert a newly-analysed article, or return the existing row if it's already there.

    `data` must contain: url, title, source_name, published_at, summary, sentiment, and
    optionally description, content, image_url.

    Safe under concurrent calls for the same URL: relies on the `url` unique constraint
    rather than a check-then-insert, since a caller-side existence check can never fully
    close the race on its own. If the insert collides, the existing row is fetched and
    returned instead of raising.
    """
    article = Article(
        url=data["url"],
        title=data["title"],
        description=data.get("description"),
        content=data.get("content"),
        image_url=data.get("image_url"),
        source_name=data["source_name"],
        published_at=data["published_at"],
        summary=data["summary"],
        sentiment=data["sentiment"],
        analysed_at=datetime.now(timezone.utc),
    )
    db.add(article)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = get_by_url(db, data["url"])
        if existing is not None:
            return existing
        raise
    db.refresh(article)
    return article


def list_all(db: Session, sentiment: str | None = None) -> list[Article]:
    """Return all analysed articles, newest first, optionally filtered by sentiment."""
    query = select(Article).order_by(Article.analysed_at.desc())
    if sentiment is not None:
        query = query.where(Article.sentiment == sentiment)
    return list(db.execute(query).scalars().all())


def enrich_with_analysis_state(db: Session, articles: list[dict]) -> list[dict]:
    """Tag each raw gnews.io search result with whether it's already been analysed.

    Adds `already_analysed`, `id`, `summary`, and `sentiment` (from the stored row
    if one exists, else False/None) to each dict, by URL. Lets the search UI show a
    result's existing analysis instead of re-triggering it.
    """
    enriched = []
    for item in articles:
        existing = get_by_url(db, item["url"])
        enriched.append(
            {
                **item,
                "already_analysed": existing is not None,
                "id": existing.id if existing else None,
                "summary": existing.summary if existing else None,
                "sentiment": existing.sentiment if existing else None,
            }
        )
    return enriched
