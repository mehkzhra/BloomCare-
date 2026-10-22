from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def create_database_engine(url):
    return create_engine(
        url,
        pool_pre_ping=True,
        # Bound attempts to open a new PostgreSQL connection. Without this, a
        # stopped local Docker database can leave login waiting on OS timeouts.
        **(
            {"connect_args": {"check_same_thread": False}}
            if url.startswith("sqlite")
            else {"connect_args": {"connect_timeout": 3}, "pool_timeout": 3}
        ),
    )


engine = create_database_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session
