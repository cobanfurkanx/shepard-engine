"""Create a separate local test DB; never runs against a remote server."""

from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from shepard_engine.settings import get_settings

settings = get_settings()
url = settings.database_url.get_secret_value()
params = conninfo_to_dict(url)
if params.get("host") not in {"localhost", "127.0.0.1"} or params.get("dbname") != "engine":
    raise SystemExit("Only the isolated local engine database is supported")
with psycopg.connect(url, autocommit=True) as connection:
    if not connection.execute("SELECT 1 FROM pg_database WHERE datname='engine_test'").fetchone():
        connection.execute("CREATE DATABASE engine_test")
params["dbname"] = "engine_test"
target = Path(".env.local")
if "TEST_DATABASE_URL=" not in target.read_text(encoding="utf-8"):
    with target.open("a", encoding="utf-8") as stream:
        stream.write(f"TEST_DATABASE_URL={make_conninfo(**params)}\n")
print("Separate test database ready.")
