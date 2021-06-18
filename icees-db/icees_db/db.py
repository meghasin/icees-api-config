"""Database tools."""
from contextlib import contextmanager
import os
from pathlib import Path
from time import sleep

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.exc import OperationalError

db = os.environ.get("ICEES_DB", "sqlite")

engine = None


def get_db_connection():
    """Get database connection."""
    global engine
    if engine is None:
        if db == "sqlite":
            DB_PATH = Path(os.environ["DB_PATH"])
            engine = create_engine(
                f"sqlite:///{DB_PATH / 'example.db'}?check_same_thread=False",
            )
        elif db == "postgres":
            serv_host = os.environ["ICEES_HOST"]
            serv_port = os.environ["ICEES_PORT"]
            engine = create_engine(
                f"postgresql+psycopg2://icees_dbuser:icees_dbpass@{serv_host}:{serv_port}/icees_database",
                pool_size=int(os.environ.get("POOL_SIZE", 10)),
                max_overflow=int(os.environ.get("MAX_OVERFLOW", 0)),
            )
        else:
            raise ValueError(f"Unsupported database '{db}'")

    return engine


@contextmanager
def DBConnection() -> Connection:
    """Database connection."""
    engine = get_db_connection()
    sleep_sec = 0.5
    while True:
        try:
            conn: Connection = engine.connect()
            break
        except OperationalError as err:
            sleep_sec *= 2
            if sleep_sec > 16:
                raise err
            print(
                "Failed to connect to PostgreSQL. "
                f"Retrying in {sleep_sec} seconds..."
            )
            sleep(sleep_sec)
    try:
        yield conn
    finally:
        conn.close()
