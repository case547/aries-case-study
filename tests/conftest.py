import os

# Set dummy env vars before any `app` import — required so app.config.Settings()
# doesn't KeyError, and so app.db's module-level engine (bound to this dummy
# URL) is a syntactically valid SQLAlchemy URL. Tests use their own separate
# in-memory engine below and never touch this one.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GNEWS_API_KEY", "test-gnews-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
