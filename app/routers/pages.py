"""The HTML/HTMX UI: search page, results page, and their HTMX fragment endpoints.

Calls the exact same service-layer functions as `app/routers/api.py` -- this router
exists only because HTMX needs pre-rendered HTML to swap into the DOM; the business
logic doesn't differ from the JSON API in any way.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.schemas import AnalyseRequest
from app.services import article_repository
from app.services.analysis_service import AnalysisError, analyse_and_store
from app.services.news_service import NewsAPIError, search_articles

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def search_page(request: Request):
    """Render the search page shell. No results yet -- those are fetched via HTMX."""
    return templates.TemplateResponse(request, "search.html", {})


@router.get("/search-results")
async def search_results(request: Request, q: str, db: Session = Depends(get_db)):
    """HTMX fragment for the search form: gnews.io results tagged with analysis state.

    Renders an error banner instead of raising if gnews.io fails, so a bad search never
    crashes the page.
    """
    try:
        raw_articles = await search_articles(q)
        articles = article_repository.enrich_with_analysis_state(db, raw_articles)
        context = {"articles": articles, "query": q, "error": None}
    except NewsAPIError as exc:
        context = {"articles": [], "query": q, "error": exc.message}
    return templates.TemplateResponse(request, "partials/search_results.html", context)


@router.post("/articles/analyse")
def analyse_card(
    request: Request,
    url: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    content: str = Form(""),
    image_url: str = Form(""),
    source_name: str = Form(...),
    published_at: str = Form(...),
    db: Session = Depends(get_db),
):
    """HTMX fragment for the "Analyse" button: re-renders the card with its result.

    On success, the card renders in its analysed state (summary + badge). On failure,
    it re-renders in its unanalysed state (form still present) with an inline error
    message instead of crashing the page.
    """
    analyse_request = AnalyseRequest(
        url=url,
        title=title,
        description=description or None,
        content=content or None,
        image_url=image_url or None,
        source_name=source_name,
        published_at=datetime.fromisoformat(published_at),
    )
    try:
        article = analyse_and_store(db, analyse_request.model_dump())
        context = {"article": article, "results_page": False}
    except AnalysisError as exc:
        context = {
            "article": {
                **analyse_request.model_dump(),
                "sentiment": None,
                "summary": None,
                "id": None,
                "error": exc.message,
            },
            "results_page": False,
        }
    return templates.TemplateResponse(request, "partials/article_card.html", context)


@router.get("/results")
def results_page(request: Request, db: Session = Depends(get_db)):
    """Render the results page -- every analysed article, newest first."""
    articles = article_repository.list_all(db)
    return templates.TemplateResponse(
        request, "results.html", {"articles": articles, "results_page": True}
    )
