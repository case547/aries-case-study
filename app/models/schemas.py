from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnalyseRequest(BaseModel):
    """Input to trigger analysis of an article.

    Mirrors a gnews.io search result's shape, since that's the only data available before a row
    exists. Used for both the JSON API body (POST /api/articles/analyse) and the HTML form fields
    (POST /articles/analyse).
    """

    url: str
    title: str
    description: str | None = None
    content: str | None = None
    image_url: str | None = None
    source_name: str
    published_at: datetime


class ArticleOut(BaseModel):
    """Response shape for a persisted, analysed article.

    Serialises directly from a SQLAlchemy `Article` instance (see `model_config` below) -- used
    as the response model for POST /api/articles/analyse, GET /api/results, GET /api/results/{id},
    and what the HTML templates render from once an article is analysed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: str
    description: str | None
    content: str | None
    image_url: str | None
    source_name: str
    published_at: datetime
    summary: str | None
    sentiment: str | None
    analysed_at: datetime | None
    created_at: datetime
