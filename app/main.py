from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="News Analysis App", lifespan=lifespan)
