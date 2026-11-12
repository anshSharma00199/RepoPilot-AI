from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initializes the database schema if tables do not exist."""
    # Import all models here so that Base.metadata has registered them
    import app.models.repository  # noqa: F401
    import app.models.scan_job    # noqa: F401
    import app.models.repository_file  # noqa: F401
    import app.models.execution_job   # noqa: F401
    import app.models.diagnostic_report  # noqa: F401
    import app.models.validation_run     # noqa: F401

    Base.metadata.create_all(bind=engine)
