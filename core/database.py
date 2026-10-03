from pathlib import Path
from datetime import datetime
from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy import event, update
from sqlalchemy.dialects.sqlite import insert
from config.settings import settings
from config.routes import DEFAULT_MONITORED_ROUTES
from core.models import Route, Deal, RouteStats
from core.snapshots import SearchSnapshot, TaskLease, RadarMigration

Path(settings.DB_PATH).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{settings.DB_PATH}",
                       connect_args={"check_same_thread": False, "timeout": 30})


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=DELETE")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=10000")
    cursor.close()


def init_db():
    SQLModel.metadata.create_all(engine)
    # One additive migration. Preserve raw records and sent-alert history.
    with Session(engine) as session:
        claimed = session.execute(insert(RadarMigration).values(
            name="search-snapshots-v1", applied_at=datetime.utcnow()
        ).on_conflict_do_nothing(index_elements=["name"]))
        if claimed.rowcount == 1:
            session.execute(update(Deal).where(Deal.status == "active").values(status="expired"))
            session.execute(update(RouteStats).values(
                sample_count=0, avg_7d=None, avg_30d=None, avg_90d=None,
                min_historical=None, max_historical=None,
            ))
        session.commit()
    seed_default_routes()


def get_session():
    with Session(engine) as session:
        yield session


def seed_default_routes():
    with Session(engine) as session:
        for route in DEFAULT_MONITORED_ROUTES:
            session.execute(insert(Route).values(**route, active=True, country="日本", created_at=datetime.utcnow()).on_conflict_do_nothing(
                index_elements=["origin", "destination"]))
        session.commit()
