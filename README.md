# Aries Engineering Case Study 

For the case study brief, see brief.md

---

## Walkthrough

A user searches for a news topic; the app queries gnews.io and shows the matching articles
as cards (image, title, source, date, description). Clicking **Analyse** on a card sends it
to OpenAI (`gpt-4.1-nano`) for a short summary and a positive/neutral/negative sentiment
label, in a single structured-output call. The result is stored in Postgres and the card
updates in place to show the summary and a colour-coded sentiment badge, with no page
reload. A separate **Results** page lists everything that's ever been analysed, newest
first.

Searching again for a topic you've already analysed an article from shows that article's
existing summary/sentiment immediately instead of a bare "Analyse" button -- articles are
deduplicated by URL, so the same article is never sent to OpenAI twice.

Errors from either external API (rate limits, quota, outages) surface as a small inline
message rather than a crash -- the "Analyse" button stays clickable so the user can just
retry.

## Architecture overview

One FastAPI app exposes the same functionality two ways from the same service layer:

```
app/
  main.py              FastAPI() app: mounts static files, includes both routers
  config.py            Loads DATABASE_URL / GNEWS_API_KEY / OPENAI_API_KEY from .env
  db.py                SQLAlchemy engine, session, init_db()
  base.py              The SQLAlchemy declarative Base (its own module to avoid a
                       db.py <-> models/article.py import cycle)
  models/
    article.py           The Article table (one table: analysed articles)
    schemas.py            Pydantic request/response shapes for the REST API
  services/
    news_service.py        Calls gnews.io, maps its response, maps its errors
    analysis_service.py     Calls OpenAI, maps its errors, dedup-gates the call
    article_repository.py   All DB reads/writes, including URL-based dedup
  routers/
    api.py                JSON REST API  (/api/search, /api/articles/analyse, /api/results, ...)
    pages.py               HTML/HTMX UI  (/, /search-results, /articles/analyse, /results)
  templates/, static/    Jinja2 templates + CSS for the HTML UI
```

- **`routers/api.py`** and **`routers/pages.py`** call the *exact same* functions in
  `services/` -- the JSON API isn't a decorative layer next to the UI, it's the same
  business logic serialised as JSON instead of rendered as HTML fragments for HTMX to
  swap into the page.
- **Dedup is defense-in-depth**: `analysis_service.analyse_and_store` checks for an
  existing row by URL *before* calling OpenAI (saves the API call in the common case),
  and `article_repository.insert_article` also relies on the DB's `url` unique constraint
  to safely handle the rare case of two requests analysing the same new article at once.
- **No Alembic**: a single table with `Base.metadata.create_all()` on startup
  was enough for this scope; plain SQLAlchemy + separate Pydantic schemas were chosen,
  although SQLModel could also have been viable.
- **One automated test**: `tests/test_article_repository.py` covers the dedup behaviour,
  since a bug there is the one thing that would silently waste OpenAI/gnews.io quota.
  Everything else was verified manually against the real APIs during development.

## Local development

Prerequisites: `uv`, Docker (for local Postgres).

### Starting up

```bash
uv sync
cp .env.example .env   # fill in GNEWS_API_KEY and OPENAI_API_KEY
docker compose up -d   # starts local Postgres on port 5432
uv run fastapi dev app/main.py
```

Visit `http://localhost:8000`.

### Tearing down

Stop the dev server with `Ctrl+C`, then:

```bash
docker compose down      # stops and removes the Postgres container; data is kept
docker compose down -v   # add -v to also delete the data volume for a clean slate
```

## Running tests

```bash
uv run pytest
```

## Deploying to Render

1. Push this repo to GitHub.
2. In Render, create a **new Web Service** from the repo:
   - Build command: `uv sync`
   - Start command: `uv run fastapi run app/main.py --port $PORT`
3. In Render, create a **new PostgreSQL** instance (free tier).
4. On the web service, set environment variables:
   - `DATABASE_URL` -- the connection string from the Render Postgres instance
   - `GNEWS_API_KEY`
   - `OPENAI_API_KEY`
5. Deploy. Note: Render's free web service spins down after 15 minutes of inactivity -- the first request after idle takes about a minute to wake back up. The free Postgres instance expires 30 days after creation (plus a 14-day grace period before deletion).