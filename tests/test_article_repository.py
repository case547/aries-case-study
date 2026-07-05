from datetime import datetime, timezone

from app.services.article_repository import get_by_url, insert_article, list_all

SAMPLE_ARTICLE = {
    "url": "https://example.com/article-1",
    "title": "Example Title",
    "description": "Example description",
    "content": "Example content",
    "image_url": "https://example.com/image.jpg",
    "source_name": "Example Source",
    "published_at": datetime(2026, 7, 1, tzinfo=timezone.utc),
    "summary": "Example summary",
    "sentiment": "positive",
}


def test_insert_article_creates_new_row(db_session):
    article = insert_article(db_session, SAMPLE_ARTICLE)

    assert article.id is not None
    assert article.url == SAMPLE_ARTICLE["url"]
    assert len(list_all(db_session)) == 1


def test_insert_article_is_idempotent_by_url(db_session):
    first = insert_article(db_session, SAMPLE_ARTICLE)
    second = insert_article(db_session, SAMPLE_ARTICLE)

    assert first.id == second.id
    assert len(list_all(db_session)) == 1


def test_get_by_url_returns_none_when_not_found(db_session):
    assert get_by_url(db_session, "https://example.com/missing") is None
