"""Connection wrapper for SYWI Lance databases."""

from __future__ import annotations

import os
import re
from pathlib import Path

import duckdb
from dotenv import find_dotenv, load_dotenv

DEFAULT_LANCE_URI = "./data/lance"


class ConnectionError(Exception):
    """Raised when connecting to the Lance databases fails."""

    pass


def _sql_str(value: str) -> str:
    """Quote a value as a SQL string literal."""
    return "'" + value.replace("'", "''") + "'"


def _remote_uris() -> dict[str, str]:
    """Remote databases from LANCE_REMOTE_URI, as {name: uri}.

    One plain URI is attached as `remote`. Several are written as comma separated
    `name=uri` pairs, for example
    `ikariam=s3://ikariam/ikariam.lancedb,hackernews=s3://hackernews/lance`.
    """
    remotes: dict[str, str] = {}
    for part in (p.strip() for p in os.getenv("LANCE_REMOTE_URI", "").split(",")):
        if not part:
            continue
        name, separator, uri = part.partition("=")
        if not separator:
            name, uri = "remote", part
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or name == "local" or name in remotes:
            raise ConnectionError(f"Invalid or duplicate remote name '{name}' in LANCE_REMOTE_URI")
        remotes[name] = uri
    return remotes


def _s3_secret_sql(bucket: str) -> str:
    """CREATE SECRET for one bucket, with credentials from the AWS_* variables."""
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        if not os.getenv(name):
            raise ConnectionError(f"Required environment variable {name} is not set")

    options = [
        "TYPE lance",
        "PROVIDER config",
        f"aws_access_key_id {_sql_str(os.environ['AWS_ACCESS_KEY_ID'])}",
        f"aws_secret_access_key {_sql_str(os.environ['AWS_SECRET_ACCESS_KEY'])}",
        f"aws_region {_sql_str(os.getenv('AWS_REGION', 'us-east-1'))}",
        "aws_virtual_hosted_style_request 'false'",
        f"SCOPE {_sql_str(f's3://{bucket}/')}",
    ]
    if os.getenv("AWS_ENDPOINT_URL"):
        options.append(f"aws_endpoint {_sql_str(os.environ['AWS_ENDPOINT_URL'])}")

    return f"CREATE SECRET lance_{bucket.replace('-', '_')} ({', '.join(options)})"


def connect() -> duckdb.DuckDBPyConnection:
    """
    Create a DuckDB connection with the SYWI Lance databases attached.

    Automatically loads environment from .env and .env.local and attaches:
    - `local`: your local Lance database (LANCE_URI, default ./data/lance)
    - the remote Lance databases from LANCE_REMOTE_URI: a single URI is attached as
      `remote`, several `name=uri` pairs (comma separated) under their names

    Requires DuckDB 2.0 or newer (the lance extension is a core extension there).

    Returns:
        DuckDB connection with `local` (and `remote`) attached.

    Raises:
        ConnectionError: If S3 credentials are missing or attaching fails.

    Example:
        >>> import sywi_duckdb as duckdb
        >>> conn = duckdb.connect()
        >>> conn.execute("SELECT * FROM local.my_table").fetchdf()
        >>> conn.execute("SELECT * FROM remote.my_table").fetchdf()
    """
    load_dotenv(find_dotenv(".env"))
    load_dotenv(find_dotenv(".env.local"), override=True)

    local_uri = os.getenv("LANCE_URI") or DEFAULT_LANCE_URI
    remotes = _remote_uris()

    if not local_uri.startswith("s3://"):
        Path(local_uri).mkdir(parents=True, exist_ok=True)

    buckets: list[str] = []
    for uri in (local_uri, *remotes.values()):
        if uri.startswith("s3://") and uri.split("/")[2] not in buckets:
            buckets.append(uri.split("/")[2])

    statements = ["INSTALL lance", "LOAD lance"]
    statements.extend(_s3_secret_sql(bucket) for bucket in buckets)
    statements.append(f"ATTACH {_sql_str(local_uri)} AS local (TYPE lance)")
    for name, uri in remotes.items():
        statements.append(f"ATTACH {_sql_str(uri)} AS {name} (TYPE lance)")

    conn = duckdb.connect()
    try:
        for statement in statements:
            conn.execute(statement)
    except duckdb.Error as e:
        conn.close()
        raise ConnectionError(f"Failed to connect to the Lance databases: {e}") from e

    return conn
