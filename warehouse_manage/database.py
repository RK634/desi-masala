import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

# Load the backend .env file when running locally. Environment variables already
# provided by the host take precedence.
load_dotenv()

def get_connection():
    """Open a PostgreSQL connection using DB_* environment variables."""
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"Missing database configuration: {', '.join(missing)}")

    kwargs = {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ["DB_PORT"]),
        "dbname": os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "row_factory": dict_row,
    }
    # Empty DB_PASSWORD is allowed only when PostgreSQL is configured for it.
    password = os.getenv("DB_PASSWORD", "")
    if password:
        kwargs["password"] = password
    return psycopg.connect(**kwargs)
