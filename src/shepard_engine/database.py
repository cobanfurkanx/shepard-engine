from importlib.resources import files
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


def sql_file(name: str) -> str:
    installed = files("shepard_engine").joinpath("sql", name)
    if installed.is_file():
        return installed.read_text(encoding="utf-8")
    return (Path(__file__).resolve().parents[2] / "sql" / name).read_text(encoding="utf-8")


def connect_database(url):
    return psycopg.connect(
        url,
        row_factory=dict_row,
        connect_timeout=5,
        options="-c statement_timeout=10000 -c lock_timeout=5000",
    )


def migrate(url):
    with connect_database(url) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(777001)")
        connection.execute(sql_file("001_init.sql"))


if __name__ == "__main__":
    from shepard_engine.settings import get_settings

    migrate(get_settings().database_url.get_secret_value())
