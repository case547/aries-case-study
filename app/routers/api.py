"""The JSON REST API: search, analyse, and list results.

Calls the exact same service-layer functions as `app/routers/pages.py`-- this
router is not a decorative layer alongside the HTML UI; it's the same business
logic serialised as JSON instead of rendered HTML.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.article import Article
from app.models.schemas import AnalyseRequest, ArticleOut
from app.services import article_repository
from app.services.analysis_service import AnalysisError, analyse_and_store
from app.services.news_service import NewsAPIError, search_articles


def _upstream_status(exc: NewsAPIError | AnalysisError) -> int:
    if exc.status_code in (400, 429):
        return exc.status_code
    return 502


router = APIRouter(prefix="/api")


@router.get("/search")
async def search(q: str, db: Session = Depends(get_db)) -> list[dict]:
    """Search gnews.io for `q`, tagging each result with its existing analysis if any.

    Raises a 502 if gnews.io is unreachable or errors.
    """
    try:
        raw_articles = await search_articles(q)
    except NewsAPIError as exc:
        raise HTTPException(status_code=_upstream_status(exc), detail=exc.message) from exc

    return article_repository.enrich_with_analysis_state(db, raw_articles)


@router.post("/articles/analyse", response_model=ArticleOut)
def analyse(request: AnalyseRequest, db: Session = Depends(get_db)) -> Article:
    """Summarise and score an article's sentiment, storing (or reusing) the result.

    Idempotent by URL: analysing an already-analysed article returns its
    existing row instead of calling OpenAI again. Raises a 502 if OpenAI is
    unreachable or errors.
    """
    try:
        return analyse_and_store(db, request.model_dump())
    except AnalysisError as exc:
        raise HTTPException(status_code=_upstream_status(exc), detail=exc.message) from exc


@router.get("/results", response_model=list[ArticleOut])
def results(
    sentiment: str | None = None, db: Session = Depends(get_db)
) -> list[Article]:
    """List all analysed articles, newest first, optionally filtered by sentiment."""
    return article_repository.list_all(db, sentiment=sentiment)


@router.get("/results/{article_id}", response_model=ArticleOut)
def result_detail(article_id: int, db: Session = Depends(get_db)) -> Article:
    """Fetch a single analysed article by id, or 404 if it doesn't exist."""
    article = article_repository.get_by_id(db, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
