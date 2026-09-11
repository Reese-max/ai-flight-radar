"""All tests use a disposable database and disabled external notifications."""
import os
from tempfile import TemporaryDirectory
import pytest

_temp = TemporaryDirectory(prefix="radar-tests-")
os.environ["DB_PATH"] = os.path.join(_temp.name, "test.db")
os.environ["NTFY_ENABLED"] = "false"
os.environ["TELEGRAM_ENABLED"] = "false"
os.environ["API_KEY"] = ""


@pytest.fixture
def db():
    from sqlmodel import SQLModel
    from core.database import engine, init_db
    SQLModel.metadata.drop_all(engine)
    init_db()
    yield engine
    SQLModel.metadata.drop_all(engine)
