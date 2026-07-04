from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.base import Base
from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    from app.models import article  # noqa: F401 — registers Article on Base.metadata

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
