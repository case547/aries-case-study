from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.routers import api


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="News Analysis App", lifespan=lifespan)
app.include_router(api.router)
