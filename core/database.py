from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy import event
from config.settings import settings
from config.routes import DEFAULT_MONITORED_ROUTES
from core.models import Route

# Create SQLite engine with appropriate timeout for cross-filesystem compatibility
connect_args = {"check_same_thread": False, "timeout": 30}
engine = create_engine(f"sqlite:///{settings.DB_PATH}", connect_args=connect_args)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=DELETE")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=10000")
    cursor.close()

def init_db():
    SQLModel.metadata.create_all(engine)
    seed_default_routes()

def get_session():
    with Session(engine) as session:
        yield session

def seed_default_routes():
    with Session(engine) as session:
        for r in DEFAULT_MONITORED_ROUTES:
            stmt = select(Route).where(Route.origin == r["origin"], Route.destination == r["destination"])
            existing = session.exec(stmt).first()
            if not existing:
                route = Route(
                    origin=r["origin"],
                    destination=r["destination"],
                    priority=r["priority"],
                    active=True
                )
                session.add(route)
        session.commit()
